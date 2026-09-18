import json

from django.shortcuts import render

from category.models import Category
from store.catalog_concurrent import CSV_BY_SLUG, _query_csv
from store.models import Product

from .forms import AssistantForm


USE_CASE_KEYWORDS = {
    'gaming': {
        'video-card': ['rtx', 'gtx', 'gaming', 'fps', 'graphics', 'nvidia', 'amd'],
        'cpu': ['ryzen', 'intel', 'core', 'gaming', 'fps'],
        'motherboard': ['amd', 'intel', 'b550', 'x570', 'gaming'],
        'memory': ['ddr4', 'ddr5', '32gb', 'gaming', 'rgb'],
        'monitor': ['144hz', '240hz', 'gaming', '4k', 'curved'],
        'power-supply': ['850w', '750w', 'gold', '80+', 'gaming'],
        'case': ['airflow', 'rgb', 'gaming', 'temperado'],
        'internal-hard-drive': ['nvme', 'ssd', 'm2', 'gaming'],
    },
    'trabajo': {
        'video-card': ['workstation', 'design', 'creator', 'studio'],
        'cpu': ['office', 'productivity', 'core', 'i7', 'ryzen', 'work'],
        'motherboard': ['business', 'stable', 'broadcom'],
        'memory': ['32gb', '16gb', 'multitask', 'ram'],
        'monitor': ['4k', 'office', 'professional', 'ultrawide'],
        'power-supply': ['efficiency', 'reliable', '750w'],
        'case': ['compact', 'quiet', 'professional'],
        'internal-hard-drive': ['ssd', 'nvme', 'fast boot'],
    },
    'estudio': {
        'video-card': ['integrated', 'light', 'web'],
        'cpu': ['student', 'office', 'essential', 'i5', 'ryzen'],
        'motherboard': ['compact', 'value', 'budget'],
        'memory': ['8gb', '16gb', 'office'],
        'monitor': ['ips', 'full hd', 'office', 'student'],
        'power-supply': ['reliable', 'efficient'],
        'case': ['compact', 'minimal'],
        'internal-hard-drive': ['ssd', 'read', 'write'],
    },
    'streaming': {
        'video-card': ['streaming', 'creator', 'encoders', 'rtx', '4k'],
        'cpu': ['streaming', 'encoding', 'content', 'production'],
        'motherboard': ['creator', 'streaming', 'stable'],
        'memory': ['32gb', '64gb', 'streaming', 'creator'],
        'monitor': ['4k', 'streaming', 'ips', 'ultrawide'],
        'power-supply': ['850w', '1000w', 'efficient', 'streaming'],
        'case': ['expandable', 'cooling', 'creator'],
        'internal-hard-drive': ['ssd', 'nvme', '2tb', 'streaming'],
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


def _text_from_product(product):
    parts = [
        getattr(product, 'product_name', ''),
        getattr(product, 'description', ''),
        getattr(product, 'part_type', ''),
    ]
    category = getattr(product, 'category', None)
    parts.append(getattr(category, 'category_name', getattr(product, 'category_slug', '')))
    specs = getattr(product, 'specs', {})
    if hasattr(product, 'get_specs_dict'):
        specs = product.get_specs_dict()
    elif isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except (TypeError, ValueError):
            specs = {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values())
    return ' '.join(str(part or '') for part in parts).lower()


def _score_product(product, budget, use_case, category_slug):
    score = 0
    text = _text_from_product(product)

    if product.price and product.price > 0:
        delta = abs(product.price - budget)
        score += max(0, 1200 - (delta / 18))
    product_category_slug = _product_category_slug(product)
    if category_slug and product_category_slug == category_slug:
        score += 250

    keywords = USE_CASE_KEYWORDS.get(use_case, {}).get(product_category_slug, [])
    score += sum(80 for keyword in keywords if keyword in text)
    if any(keyword in text for keyword in ('ryzen', 'intel', 'nvidia', 'amd')):
        score += 30
    if getattr(product, 'is_available', True):
        score += 50
    if product.price and product.price <= budget * 1.15:
        score += 60
    return score


def _explain_recommendation(product, use_case):
    labels = {
        'gaming': 'ideal para gaming y rendimiento',
        'trabajo': 'muy buena opción para trabajo y productividad',
        'estudio': 'equilibrio práctico para estudio y oficina',
        'streaming': 'sólido para streaming y contenido',
    }
    category = getattr(product, 'category', None)
    category_name = getattr(
        category,
        'category_name',
        CSV_BY_SLUG.get(_product_category_slug(product), ('', 'Componente'))[1],
    )
    return f'{category_name} · {labels.get(use_case, "recomendado")}'


def _product_category_slug(product):
    category = getattr(product, 'category', None)
    return getattr(category, 'slug', getattr(product, 'category_slug', ''))


def _build_recommendations(budget, use_case, category_slug=None):
    queryset = Product.objects.filter(
        is_available=True,
        price__gt=0,
    ).select_related('category')
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)
    products = list(queryset.order_by('price')[:200])

    if not products:
        products = _query_csv(category_slug, None).get('products', [])

    products = [product for product in products if product.price and product.price > 0]
    results = []
    for product in sorted(products, key=lambda item: item.price)[:200]:
        results.append({
            'product': product,
            'score': round(_score_product(product, budget, use_case, category_slug), 2),
            'reason': _explain_recommendation(product, use_case),
        })
    return sorted(results, key=lambda item: item['score'], reverse=True)[:3]


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

    context = {
        'form': form,
        'recommendations': _build_recommendations(
            selected_budget, selected_use_case, selected_category,
        ),
        'selected_use_case': selected_use_case,
        'selected_category': selected_category,
        'selected_budget': selected_budget,
    }
    return render(request, 'assistant/assistant.html', context)
