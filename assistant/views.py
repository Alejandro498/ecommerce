import json
import re

from django.db.models import F, IntegerField, Value
from django.db.models.functions import Abs
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from store.catalog_concurrent import CSV_BY_SLUG, _query_csv
from store.models import Product

from .forms import AssistantForm
from .fuzzy import score_component
from .genetic import recommend_builds
from .interpreter import interpret_message
from .preferences import normalize_prefs

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


def _product_cart_id(product):
    """ID de tienda para meter la pieza al carrito (None si solo existe en CSV)."""
    product_id = getattr(product, 'id', None)
    if product_id:
        return int(product_id)
    slug = getattr(product, 'slug', None)
    if not slug:
        return None
    from store.models import Product

    found = Product.objects.filter(slug=slug, is_available=True).values_list('id', flat=True).first()
    return int(found) if found else None


def _attach_cart_ids(build):
    """Marca la build con product_ids usables por el carrito de la tienda."""
    product_ids = []
    for part in build.get('parts') or []:
        product_id = _product_cart_id(part.get('product'))
        part['cart_id'] = product_id
        if product_id:
            product_ids.append(product_id)
    build['product_ids'] = product_ids
    build['can_add_to_cart'] = bool(product_ids) and len(product_ids) == len(build.get('parts') or [])
    return build


def _product_image_url(product):
    getter = getattr(product, 'get_image_url', None)
    if not callable(getter):
        return ''
    try:
        return getter() or ''
    except Exception:
        return ''


def _serialize_build(build):
    enriched = _attach_cart_ids(dict(build))
    parts = []
    images = {}
    for part in enriched['parts']:
        product = part['product']
        product_id = part.get('cart_id')
        image = _product_image_url(product)
        slot = part['slot']
        if image and slot in ('case', 'cpu', 'video-card'):
            images[slot] = image
        parts.append({
            'slot': slot,
            'label': part['label'],
            'name': getattr(product, 'product_name', ''),
            'price': int(getattr(product, 'price', 0) or 0),
            'url': getattr(product, 'get_url', lambda: '#')(),
            'priority': part.get('priority'),
            'id': product_id,
            'image': image,
        })
    fitness = round(float(enriched.get('fitness') or 0), 2)
    return {
        'rank': enriched['rank'],
        'fitness': fitness,
        # Alias legible para la UI: aptitud del genético (0-100).
        'score': fitness,
        'total_price': enriched['total_price'],
        'summary': enriched['summary'],
        'product_ids': enriched['product_ids'],
        'can_add_to_cart': enriched['can_add_to_cart'],
        'images': images,
        'parts': parts,
    }


def _chat_reply(interpretation, result=None):
    if not interpretation.get('ready'):
        return interpretation.get('ask') or (
            'Cuéntame para qué la quieres y más o menos cuánto puedes gastar.'
        )

    summary = interpretation.get('summary') or 'lo que me pediste'
    if result is None:
        return f'Perfecto: {summary}. Dame un segundo, te armo unas opciones…'

    builds = result.get('builds') or []
    if not builds:
        return (
            f'Con {summary.lower()} no me alcanzó para una PC compatible. '
            '¿Probamos con un poco más de presupuesto?'
        )

    first = builds[0]
    count = len(builds)
    score = first.get('score', first.get('fitness'))
    score_txt = f' Score {score}/100.' if score is not None else ''
    if count == 1:
        opener = 'Te armé esta configuración'
    else:
        opener = f'Te armé {count} opciones'
    return (
        f'{opener} para {summary.lower()}. '
        f'La que mejor queda sale en ${first["total_price"]} MXN.{score_txt} '
        'Desliza entre las opciones abajo; si quieres, dime otro presupuesto o uso.'
    )


def assistant(request):
    """
    Pagina completa del asistente (sin enlace en el menu).
    Acceso solo por URL directa: /assistant/
    La burbuja flotante sigue disponible en todas las vistas.
    """
    defaults = {
        'use_case': 'gaming',
        'budget': 15000,
        'resolution': '1080p',
        'performance': 'medio',
        'experience': 'medio',
        'brand': 'any',
        'gpu_brand': 'any',
    }
    submitted = bool(request.GET)
    form = AssistantForm(request.GET or None, initial=defaults)
    selected_use_case = defaults['use_case']
    selected_budget = defaults['budget']
    prefs = normalize_prefs(defaults, use_case=selected_use_case)

    if submitted and form.is_valid():
        selected_use_case = form.cleaned_data['use_case']
        selected_budget = form.cleaned_data['budget']
        prefs = normalize_prefs(
            {
                'resolution': form.cleaned_data.get('resolution'),
                'performance': form.cleaned_data.get('performance'),
                'experience': form.cleaned_data.get('experience'),
                'brand': form.cleaned_data.get('brand'),
                'gpu_brand': form.cleaned_data.get('gpu_brand'),
            },
            use_case=selected_use_case,
        )
        result = recommend_builds(selected_budget, selected_use_case, prefs=prefs)
        for build in result.get('builds') or []:
            _attach_cart_ids(build)
    else:
        result = {
            'builds': [],
            'priorities': [],
            'prefs': prefs,
            'notice': 'Escribe en el chat o usa el formulario para armar una PC.',
            'debug': {'engine': 'mamdani+genetic', 'procedimiento': [], 'builds': []},
        }

    context = {
        'form': form,
        'builds': result['builds'],
        'priorities': result['priorities'],
        'prefs': result.get('prefs') or prefs,
        'notice': result.get('notice') or '',
        'assistant_debug': result['debug'],
        'selected_use_case': selected_use_case,
        'selected_budget': selected_budget,
    }
    return render(request, 'assistant/assistant.html', context)


@require_POST
def assistant_chat(request):
    """
    Chat en dos fases:
    - build=false (default en el front al interpretar): solo usa/presupuesto.
    - build=true: arma la PC con Mamdani + genetico (sin volver a llamar al LLM
      si ya mandan use_case y budget).
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (TypeError, ValueError, UnicodeDecodeError):
        payload = {}

    message = (payload.get('message') or '').strip()
    do_build = bool(payload.get('build'))
    history = payload.get('history') or []
    if not isinstance(history, list):
        history = []
    history = [
        {'role': item.get('role'), 'content': item.get('content')}
        for item in history[-6:]
        if isinstance(item, dict)
    ]

    # Segunda fase: ya interpretado, solo armar.
    preset_use = payload.get('use_case')
    preset_budget = payload.get('budget')
    if do_build and preset_use and preset_budget:
        from assistant.interpreter import _natural_summary
        from assistant.preferences import prefs_summary

        prefs = normalize_prefs(payload.get('prefs') or payload, use_case=str(preset_use))
        interpretation = {
            'use_case': preset_use,
            'budget': int(preset_budget),
            'ready': True,
            'ask': None,
            'summary': (
                f'{_natural_summary(str(preset_use), int(preset_budget))} '
                f'({prefs_summary(prefs)})'
            ),
            'source': payload.get('interpreter') or 'preset',
            'prefs': prefs,
        }
    else:
        if not message:
            return JsonResponse(
                {
                    'ok': False,
                    'reply': 'Escribe qué PC necesitas y tu presupuesto.',
                    'ready': False,
                },
                status=400,
            )
        try:
            interpretation = interpret_message(message, history)
        except Exception as exc:
            return JsonResponse(
                {
                    'ok': False,
                    'reply': f'No pude interpretar el mensaje: {exc}',
                    'ready': False,
                },
                status=502,
            )

    reply = _chat_reply(interpretation)
    # Los avisos tecnicos van en llm_error / console, no en el globo del chat.
    response = {
        'ok': True,
        'ready': interpretation['ready'],
        'use_case': interpretation.get('use_case'),
        'budget': interpretation.get('budget'),
        'summary': interpretation.get('summary') or '',
        'interpreter': interpretation.get('source'),
        'llm_error': interpretation.get('llm_error'),
        'prefs': interpretation.get('prefs') or normalize_prefs(
            interpretation, use_case=interpretation.get('use_case') or 'gaming',
        ),
        'reply': reply,
        'builds': [],
        'priorities': [],
        'debug': None,
    }

    if not interpretation['ready'] or not do_build:
        if interpretation['ready'] and not do_build:
            response['reply'] = _chat_reply(interpretation)
        return JsonResponse(response)

    prefs = response['prefs']
    result = recommend_builds(
        interpretation['budget'],
        interpretation['use_case'],
        prefs=prefs,
    )
    response['reply'] = _chat_reply(interpretation, result)
    response['builds'] = [_serialize_build(build) for build in result.get('builds') or []]
    response['priorities'] = result.get('priorities') or []
    response['prefs'] = result.get('prefs') or prefs
    response['debug'] = result.get('debug')
    return JsonResponse(response)
