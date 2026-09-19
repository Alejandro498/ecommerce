import json
import re

from django.db.models import F, IntegerField, Value
from django.db.models.functions import Abs
from django.shortcuts import render

from category.models import Category
from store.catalog_concurrent import CSV_BY_SLUG, _query_csv
from store.models import Product

from .forms import AssistantForm

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

USE_CASE_KEYWORDS = {
    'gaming': {
        'video-card': ('rtx', 'gtx', 'radeon', 'geforce', 'nvidia', 'amd', 'gaming'),
        'cpu': ('ryzen', 'x3d', 'intel'),
        'motherboard': ('b550', 'b650', 'x570', 'x670', 'z790', 'gaming'),
        'memory': ('ddr5', 'rgb'),
        'power-supply': ('gold', 'platinum', 'gaming'),
        'case': ('airflow', 'rgb', 'mesh'),
        'internal-hard-drive': ('nvme', 'ssd'),
    },
    'trabajo': {
        'video-card': ('quadro', 'workstation', 'creator', 'studio', 'pro'),
        'cpu': ('i7', 'i9', 'ryzen'),
        'motherboard': ('stable', 'business'),
        'memory': ('ecc',),
        'power-supply': ('gold', 'platinum'),
        'case': ('quiet', 'compact'),
        'internal-hard-drive': ('nvme', 'ssd'),
    },
    'estudio': {
        'video-card': ('integrated',),
        'cpu': ('i5', 'ryzen'),
        'motherboard': ('micro', 'budget'),
        'memory': (),
        'power-supply': ('bronze', 'gold'),
        'case': ('compact', 'mini'),
        'internal-hard-drive': ('ssd', 'nvme'),
    },
    'streaming': {
        'video-card': ('rtx', 'nvenc', 'creator'),
        'cpu': ('ryzen', 'i7', 'i9'),
        'motherboard': ('creator',),
        'memory': ('ddr5',),
        'power-supply': ('gold', 'platinum'),
        'case': ('airflow', 'cooling'),
        'internal-hard-drive': ('nvme', 'ssd'),
    },
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


def _to_number(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            number = _to_number(item)
            if number is not None:
                return number
        return None
    text = re.sub(r'[^0-9.\-]+', '', str(value).strip())
    if text in ('', '-', '.', '-.'):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _add_reason(reasons, label):
    if label and label not in reasons:
        reasons.append(label)


def _ram_capacity_gb(specs):
    count = _to_number(specs.get('module_count'))
    cap = _to_number(specs.get('module_capacity_gb'))
    if count and cap:
        return count * cap
    return None


def _ddr_generation(specs):
    speed = specs.get('speed')
    if isinstance(speed, (list, tuple)) and speed:
        gen = _to_number(speed[0])
        if gen in (4, 5):
            return int(gen)
    return None


def _score_gpu(specs, text, use_case, reasons):
    score = 0
    chipset = str(specs.get('chipset') or '').lower()
    brand = str(specs.get('gpu_brand') or '').lower()
    haystack = f'{chipset} {brand} {text}'
    vram = _to_number(specs.get('memory'))

    is_rtx = _has_token(haystack, 'rtx')
    is_gtx = _has_token(haystack, 'gtx')
    is_radeon = _has_token(haystack, 'radeon')
    is_workstation = any(
        _has_token(haystack, token)
        for token in ('quadro', 'workstation', 'studio', 'creator')
    ) or 'radeon pro' in haystack

    if use_case == 'gaming':
        if is_rtx:
            score += 220
            _add_reason(reasons, 'chipset RTX')
        elif is_gtx or is_radeon:
            score += 140
            _add_reason(reasons, 'GPU gamer')
        if is_workstation:
            score -= 60
        if vram:
            score += min(vram, 24) * 10
            if vram >= 8:
                _add_reason(reasons, f'{int(vram)} GB VRAM')
    elif use_case == 'trabajo':
        if is_workstation:
            score += 240
            _add_reason(reasons, 'GPU para trabajo')
        elif is_rtx:
            score += 90
        if vram:
            score += min(vram, 24) * 8
            if vram >= 8:
                _add_reason(reasons, f'{int(vram)} GB VRAM')
    elif use_case == 'estudio':
        if vram is None:
            score += 40
        elif vram <= 8:
            score += 170
            _add_reason(reasons, 'GPU ligera')
        elif vram <= 12:
            score += 80
        else:
            score += 15
        if _has_token(haystack, 'integrated'):
            score += 100
    elif use_case == 'streaming':
        if is_rtx:
            score += 240
            _add_reason(reasons, 'RTX / NVENC')
        elif is_radeon:
            score += 100
        if vram:
            score += min(vram, 24) * 10
            if vram >= 12:
                _add_reason(reasons, f'{int(vram)} GB VRAM')
    if brand in ('nvidia', 'amd'):
        score += 30
    return score


def _score_cpu(product, specs, use_case, reasons):
    score = 0
    name = (getattr(product, 'product_name', '') or '').lower()
    cores = _to_number(specs.get('core_count')) or _to_number(specs.get('cores'))
    tdp = _to_number(specs.get('tdp'))
    boost = _to_number(specs.get('boost_clock'))

    if use_case == 'gaming':
        if 'x3d' in name:
            score += 200
            _add_reason(reasons, 'caché 3D')
        if cores:
            score += min(cores, 16) * 12
            if cores >= 6:
                _add_reason(reasons, f'{int(cores)} núcleos')
        if boost:
            score += min(boost, 6.0) * 20
    elif use_case == 'trabajo':
        if cores:
            score += min(cores, 24) * 16
            if cores >= 8:
                _add_reason(reasons, f'{int(cores)} núcleos')
        if any(token in name for token in ('i7', 'i9', 'ryzen 7', 'ryzen 9')):
            score += 80
            _add_reason(reasons, 'CPU de productividad')
    elif use_case == 'estudio':
        if any(token in name for token in ('i3', 'i5', 'ryzen 3', 'ryzen 5')):
            score += 130
            _add_reason(reasons, 'CPU de estudio')
        if tdp and tdp <= 65:
            score += 90
            _add_reason(reasons, f'TDP {int(tdp)}W')
        if cores:
            if 4 <= cores <= 8:
                score += 100
            elif cores > 12:
                score += 15
    elif use_case == 'streaming':
        if cores:
            score += min(cores, 24) * 18
            if cores >= 8:
                _add_reason(reasons, f'{int(cores)} núcleos para encoding')
        if tdp and tdp >= 105:
            score += 40
    return score


def _score_memory(specs, use_case, reasons):
    score = 0
    gb = _ram_capacity_gb(specs)
    ddr = _ddr_generation(specs)
    if gb:
        if use_case == 'estudio':
            if 8 <= gb <= 16:
                score += 180
            elif gb <= 32:
                score += 80
            else:
                score += 20
        elif use_case == 'streaming':
            score += 200 if gb >= 32 else 80 if gb >= 16 else 30
        else:
            score += 180 if gb >= 32 else 120 if gb >= 16 else 40
        _add_reason(reasons, f'{int(gb)} GB RAM')
    if ddr == 5 and use_case in ('gaming', 'streaming', 'trabajo'):
        score += 80
        _add_reason(reasons, 'DDR5')
    elif ddr == 4 and use_case == 'estudio':
        score += 40
    return score


def _score_psu(specs, use_case, reasons):
    score = 0
    wattage = _to_number(specs.get('wattage'))
    efficiency = str(specs.get('efficiency') or '').lower()
    targets = {'estudio': 550, 'trabajo': 650, 'gaming': 750, 'streaming': 850}
    target = targets.get(use_case, 650)
    if wattage:
        score += max(0, 160 - abs(wattage - target) / 4)
        _add_reason(reasons, f'{int(wattage)}W')
    if any(token in efficiency for token in ('gold', 'platinum', 'titanium')):
        score += 80
        _add_reason(reasons, efficiency or 'alta eficiencia')
    return score


def _score_storage(specs, use_case, reasons):
    score = 0
    kind = str(specs.get('type') or '').lower()
    interface = str(specs.get('interface') or '').lower()
    form = str(specs.get('form_factor') or '').lower()
    capacity = _to_number(specs.get('capacity'))
    is_nvme = 'nvme' in interface or 'pcie' in interface or 'nvme' in kind
    is_ssd = is_nvme or 'ssd' in kind or 'm.2' in form
    if is_nvme:
        score += 180
        _add_reason(reasons, 'SSD NVMe')
    elif is_ssd:
        score += 140
        _add_reason(reasons, 'SSD')
    elif use_case == 'estudio':
        score += 30
    if capacity:
        if use_case == 'streaming' and capacity >= 2000:
            score += 90
            _add_reason(reasons, f'{int(round(capacity / 1000))} TB')
        elif capacity >= 1000:
            score += 50
    return score


def _score_motherboard(product, specs, use_case, reasons):
    score = 0
    name = (getattr(product, 'product_name', '') or '').lower()
    form = str(specs.get('form_factor') or '').lower()
    max_memory = _to_number(specs.get('max_memory'))
    if use_case == 'gaming' and any(
        token in name for token in ('b550', 'b650', 'x570', 'x670', 'z790', 'b760', 'gaming')
    ):
        score += 150
        _add_reason(reasons, 'chipset gaming')
    if use_case == 'estudio' and 'micro' in form:
        score += 70
        _add_reason(reasons, 'formato compacto')
    if max_memory and max_memory >= 128:
        score += 40
    return score


def _score_case(product, specs, use_case, reasons):
    score = 0
    name = (getattr(product, 'product_name', '') or '').lower()
    side = str(specs.get('side_panel') or '').lower()
    volume = _to_number(specs.get('external_volume'))
    if use_case in ('gaming', 'streaming'):
        if 'airflow' in name or 'mesh' in side:
            score += 120
            _add_reason(reasons, 'airflow')
        if 'rgb' in name or 'argb' in name:
            score += 30
    if use_case == 'estudio' and volume and volume <= 40:
        score += 80
        _add_reason(reasons, 'compacto')
    return score


def _score_cooler(specs, use_case, reasons):
    score = 0
    radiator = _to_number(specs.get('radiator_size'))
    cooler_type = str(specs.get('cooler_type') or '').lower()
    if use_case in ('gaming', 'streaming') and radiator and radiator >= 240:
        score += 110
        _add_reason(reasons, f'radiador {int(radiator)} mm')
    if use_case == 'estudio' and 'air' in cooler_type:
        score += 60
    return score


def _score_specs(product, use_case, reasons):
    slug = _product_category_slug(product)
    specs = _specs_from_product(product)
    text = _text_from_product(product)
    if slug == 'video-card':
        return _score_gpu(specs, text, use_case, reasons)
    if slug == 'cpu':
        return _score_cpu(product, specs, use_case, reasons)
    if slug == 'memory':
        return _score_memory(specs, use_case, reasons)
    if slug == 'power-supply':
        return _score_psu(specs, use_case, reasons)
    if slug == 'internal-hard-drive':
        return _score_storage(specs, use_case, reasons)
    if slug == 'motherboard':
        return _score_motherboard(product, specs, use_case, reasons)
    if slug == 'case':
        return _score_case(product, specs, use_case, reasons)
    if slug == 'cpu-cooler':
        return _score_cooler(specs, use_case, reasons)
    return 0


def _matching_keywords(product, use_case):
    slug = _product_category_slug(product)
    text = _text_from_product(product)
    keywords = USE_CASE_KEYWORDS.get(use_case, {}).get(slug, ())
    return [keyword for keyword in keywords if _has_token(text, keyword)]


def _score_keywords(product, use_case, reasons):
    hits = _matching_keywords(product, use_case)
    if hits:
        _add_reason(reasons, 'coincide con el uso')
    return 35 * len(hits)


def _score_price(product, budget, reasons):
    price = getattr(product, 'price', 0) or 0
    if price <= 0 or budget <= 0:
        return 0
    delta = abs(price - budget)
    score = 280 * (1 - min(1, delta / max(budget * 0.5, 1)))
    if price <= budget * 1.15:
        score += 40
    if delta / budget <= 0.12:
        _add_reason(reasons, 'cerca de tu presupuesto')
    return score


def _evaluate_product(product, budget, use_case):
    reasons = []
    keyword_hits = _matching_keywords(product, use_case)
    score_price = _score_price(product, budget, reasons)
    score_specs = _score_specs(product, use_case, reasons)
    score_keywords = _score_keywords(product, use_case, reasons)
    score = score_price + score_specs + score_keywords
    parts = {
        'precio': round(score_price, 2),
        'specs': round(score_specs, 2),
        'keywords': round(score_keywords, 2),
        'keyword_hits': keyword_hits,
    }
    return score, reasons, parts


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
            '6. Score = precio + specs de la categoria + keywords del uso.',
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
        'formula': 'score = score_precio + score_specs + score_keywords',
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
