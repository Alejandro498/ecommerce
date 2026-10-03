import json
import re

from django.db.models import F, IntegerField, Value
from django.db.models.functions import Abs
from django.shortcuts import render

from category.models import Category
from store.catalog_concurrent import CSV_BY_SLUG, _query_csv
from store.models import Product

from .forms import AssistantForm
from .fuzzy import score_component

POOL_LIMIT = 200
TOP_N = 3
PRICE_BANDS = (
    (0.50, 1.25),
    (0.30, 1.60),
    (0.15, 2.00),
    (None, None),
)

# Sin categoría, no mezclar todo el catálogo. Compatible con filtros SQL en RDS.
USE_CASE_CATEGORIES = {
    'gaming': ('video-card', 'cpu', 'memory', 'motherboard'),
    'trabajo': ('cpu', 'memory', 'internal-hard-drive', 'motherboard'),
    'estudio': ('cpu', 'memory', 'internal-hard-drive'),
    'streaming': ('video-card', 'cpu', 'memory', 'internal-hard-drive'),
}


def _category_choices():
    categories = Category.objects.all().order_by('category_name')
    choices = [('', 'Cualquier categoría')] + [
        (category.slug, category.category_name) for category in categories
    ]
    known_slugs = {slug for slug, _label in choices}
    choices.extend(
        (slug, label)
        for slug, (_filename, label) in CSV_BY_SLUG.items()
        if slug not in known_slugs
    )
    return choices


def _product_category_slug(product):
    category = getattr(product, 'category', None)
    return getattr(category, 'slug', getattr(product, 'category_slug', '')) or ''


def _specs_from_product(product):
    if hasattr(product, 'get_specs_dict'):
        specs = product.get_specs_dict()
        if isinstance(specs, dict):
            return specs
    specs = getattr(product, 'specs', {}) or {}
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except (TypeError, ValueError):
            return {}
    return specs if isinstance(specs, dict) else {}


def _text_from_product(product):
    specs = _specs_from_product(product)
    parts = [
        getattr(product, 'product_name', ''),
        getattr(product, 'description', ''),
        getattr(product, 'part_type', ''),
        _product_category_slug(product),
    ]
    category = getattr(product, 'category', None)
    parts.append(getattr(category, 'category_name', ''))
    for key, value in specs.items():
        parts.append(str(key))
        parts.append(str(value))
    return ' '.join(str(part or '') for part in parts).lower()


def _has_token(text, token):
    if not text or not token:
        return False
    return re.search(
        rf'(?<![a-z0-9]){re.escape(str(token).lower())}(?![a-z0-9])',
        str(text).lower(),
    ) is not None


def _evaluate_product(product, budget, use_case):
    """Scoring individual por lógica difusa (Sugeno) por componente."""
    return score_component(product, budget, use_case)


def _score_product(product, budget, use_case, category_slug=None):
    score, _reasons, _parts = _evaluate_product(product, budget, use_case)
    return score


def _category_label(product):
    category = getattr(product, 'category', None)
    return getattr(
        category,
        'category_name',
        CSV_BY_SLUG.get(_product_category_slug(product), ('', 'Componente'))[1],
    )


def _explain_recommendation(product, use_case, reasons=None):
    labels = {
        'gaming': 'alineado a gaming',
        'trabajo': 'alineado a trabajo',
        'estudio': 'alineado a estudio',
        'streaming': 'alineado a streaming',
    }
    details = [item for item in (reasons or []) if item]
    unique = []
    for item in details:
        if item not in unique:
            unique.append(item)
    suffix = ' · '.join(unique[:3]) if unique else labels.get(use_case, 'recomendado')
    return f'{_category_label(product)} · {suffix}'


def _allowed_slugs(use_case, category_slug=None):
    if category_slug:
        return [category_slug]
    return list(USE_CASE_CATEGORIES.get(use_case, ()))


def _in_stock(product):
    if not getattr(product, 'is_available', True):
        return False
    stock = getattr(product, 'stock', 1)
    if stock is None:
        return True
    return stock > 0


def _apply_price_band(products, budget, lo_ratio, hi_ratio):
    band = products
    if lo_ratio is not None:
        band = [product for product in band if product.price >= budget * lo_ratio]
    if hi_ratio is not None:
        band = [product for product in band if product.price <= budget * hi_ratio]
    return band


def _closest_by_budget(products, budget, limit=POOL_LIMIT):
    return sorted(products, key=lambda item: abs((item.price or 0) - budget))[:limit]


def _candidate_queryset(budget, use_case, category_slug, lo_ratio, hi_ratio):
    queryset = Product.objects.filter(
        is_available=True,
        stock__gt=0,
        price__gt=0,
    ).select_related('category')
    slugs = _allowed_slugs(use_case, category_slug)
    if slugs:
        queryset = queryset.filter(category__slug__in=slugs)
    if lo_ratio is not None:
        queryset = queryset.filter(price__gte=max(1, int(budget * lo_ratio)))
    if hi_ratio is not None:
        queryset = queryset.filter(price__lte=max(1, int(budget * hi_ratio)))
    return queryset.annotate(
        price_delta=Abs(
            F('price') - Value(int(budget), output_field=IntegerField()),
            output_field=IntegerField(),
        )
    ).order_by('price_delta')


def _price_band_debug(budget, lo_ratio, hi_ratio):
    if lo_ratio is None and hi_ratio is None:
        label = 'sin tope de precio (ultimo intento)'
    else:
        lo_pct = int(lo_ratio * 100) if lo_ratio is not None else 0
        hi_pct = int(hi_ratio * 100) if hi_ratio is not None else 0
        label = f'{lo_pct}% a {hi_pct}% del presupuesto'
    return {
        'lo_ratio': lo_ratio,
        'hi_ratio': hi_ratio,
        'precio_min': int(budget * lo_ratio) if lo_ratio is not None else None,
        'precio_max': int(budget * hi_ratio) if hi_ratio is not None else None,
        'label': label,
    }


def _products_from_db(budget, use_case, category_slug):
    for lo_ratio, hi_ratio in PRICE_BANDS:
        products = list(
            _candidate_queryset(budget, use_case, category_slug, lo_ratio, hi_ratio)[:POOL_LIMIT]
        )
        if products:
            return products, (lo_ratio, hi_ratio)
    return [], (None, None)


def _products_from_csv(budget, use_case, category_slug):
    slugs = _allowed_slugs(use_case, category_slug) or [None]
    items = []
    for slug in slugs:
        items.extend(_query_csv(slug, None).get('products') or [])
    items = [
        product for product in items
        if product.price and product.price > 0 and _in_stock(product)
    ]
    for lo_ratio, hi_ratio in PRICE_BANDS:
        band = _apply_price_band(items, budget, lo_ratio, hi_ratio)
        if band:
            return _closest_by_budget(band, budget), (lo_ratio, hi_ratio)
    return _closest_by_budget(items, budget), (None, None)


def _debug_row(product, score, reasons, parts, rank=None, selected=False):
    parts = parts or {}
    return {
        'rank': rank,
        'top': selected,
        'nombre': getattr(product, 'product_name', ''),
        'categoria': _category_label(product),
        'slug': _product_category_slug(product),
        'precio_mxn': getattr(product, 'price', 0) or 0,
        'score_total': round(score, 2),
        'score_precio': parts.get('precio', 0),
        'score_specs': parts.get('specs', 0),
        'score_keywords': parts.get('keywords', 0),
        'keywords': parts.get('keyword_hits') or [],
        'engine': parts.get('engine', 'fuzzy-sugeno'),
        'motivos': list(reasons or [])[:5],
    }


def _build_debug(budget, use_case, category_slug, products, source, band, ranked, top):
    lo_ratio, hi_ratio = band
    slugs = _allowed_slugs(use_case, category_slug)
    top_names = {item['product'].product_name for item in top}
    evaluados = []
    for index, item in enumerate(ranked, start=1):
        evaluados.append(
            _debug_row(
                item['product'],
                item['score'],
                item.get('reasons') or [],
                item.get('parts') or {},
                rank=index,
                selected=item['product'].product_name in top_names,
            )
        )
    return {
        'procedimiento': [
            '1. Leer uso, presupuesto y categoria (opcional). Defaults: gaming, 15000 MXN.',
            '2. Filtrar disponibles: is_available, stock > 0, price > 0.',
            '3. Recortar categorias: la elegida o el subconjunto del caso de uso.',
            '4. Buscar banda de precio (50-125%, luego 30-160%, 15-200%, sin tope).',
            '5. Ordenar por cercania al presupuesto y tomar hasta 200 candidatos.',
            '6. Evaluar cada componente con logica difusa (precio + specs + keywords).',
            '7. Ordenar por score descendente y devolver el top 3.',
        ],
        'filtros': {
            'uso': use_case,
            'presupuesto_mxn': budget,
            'categoria': category_slug or 'cualquier (subconjunto del uso)',
        },
        'categorias_evaluadas': slugs,
        'origen_pool': source,
        'banda_precio': _price_band_debug(budget, lo_ratio, hi_ratio),
        'pool_size': len(products),
        'pool_limit': POOL_LIMIT,
        'top_n': TOP_N,
        'formula': (
            'score fuzzy Sugeno = score_precio + score_specs + score_keywords '
            '(membresias triangulares/trapezoidales por componente)'
        ),
        'engine': 'fuzzy-sugeno',
        'top': [row for row in evaluados if row['top']],
        'evaluados': evaluados,
    }


def _build_recommendations(budget, use_case, category_slug=None, with_debug=False):
    products, band = _products_from_db(budget, use_case, category_slug)
    source = 'db'
    if not products:
        products, band = _products_from_csv(budget, use_case, category_slug)
        source = 'csv' if products else 'none'

    results = []
    for product in products:
        score, reasons, parts = _evaluate_product(product, budget, use_case)
        results.append({
            'product': product,
            'score': round(score, 2),
            'reason': _explain_recommendation(product, use_case, reasons),
            'reasons': reasons,
            'parts': parts,
        })
    ranked = sorted(results, key=lambda item: item['score'], reverse=True)
    top = ranked[:TOP_N]
    if with_debug:
        return top, _build_debug(
            budget, use_case, category_slug, products, source, band, ranked, top,
        )
    return top


def assistant(request):
    defaults = {'use_case': 'gaming', 'category': '', 'budget': 15000}
    form = AssistantForm(
        request.GET or None,
        category_choices=_category_choices(),
        initial=defaults,
    )
    selected_use_case = defaults['use_case']
    selected_category = defaults['category']
    selected_budget = defaults['budget']

    if form.is_valid():
        selected_use_case = form.cleaned_data['use_case']
        selected_category = form.cleaned_data['category']
        selected_budget = form.cleaned_data['budget']

    recommendations, debug = _build_recommendations(
        selected_budget, selected_use_case, selected_category, with_debug=True,
    )
    context = {
        'form': form,
        'recommendations': recommendations,
        'assistant_debug': debug,
        'selected_use_case': selected_use_case,
        'selected_category': selected_category,
        'selected_budget': selected_budget,
    }
    return render(request, 'assistant/assistant.html', context)
