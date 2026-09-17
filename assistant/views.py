from django.shortcuts import render
from django.db.models import Q

from category.models import Category
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
        'storage': ['nvme', 'ssd', 'm2', 'gaming'],
    },
    'trabajo': {
        'video-card': ['workstation', 'design', 'creator', 'studio'],
        'cpu': ['office', 'productivity', 'core', 'i7', 'ryzen', 'work'],
        'motherboard': ['business', 'stable', 'broadcom'],
        'memory': ['32gb', '16gb', 'multitask', 'ram'],
        'monitor': ['4k', 'office', 'professional', 'ultrawide'],
        'power-supply': ['efficiency', 'reliable', '750w'],
        'case': ['compact', 'quiet', 'professional'],
        'storage': ['ssd', 'nvme', 'fast boot'],
    },
    'estudio': {
        'video-card': ['integrated', 'light', 'web'],
        'cpu': ['student', 'office', 'essential', 'i5', 'ryzen'],
        'motherboard': ['compact', 'value', 'budget'],
        'memory': ['8gb', '16gb', 'office'],
        'monitor': ['ips', 'full hd', 'office', 'student'],
        'power-supply': ['reliable', 'efficient'],
        'case': ['compact', 'minimal'],
        'storage': ['ssd', 'read', 'write'],
    },
    'streaming': {
        'video-card': ['streaming', 'creator', 'encoders', 'rtx', '4k'],
        'cpu': ['streaming', 'encoding', 'content', 'production'],
        'motherboard': ['creator', 'streaming', 'stable'],
        'memory': ['32gb', '64gb', 'streaming', 'creator'],
        'monitor': ['4k', 'streaming', 'ips', 'ultrawide'],
        'power-supply': ['850w', '1000w', 'efficient', 'streaming'],
        'case': ['expandable', 'cooling', 'creator'],
        'storage': ['ssd', 'nvme', '2tb', 'streaming'],
    },
}


def _category_choices():
    categories = Category.objects.all().order_by('category_name')
    return [('', 'Cualquier categoría')] + [(category.slug, category.category_name) for category in categories]


def _text_from_product(product):
    parts = [
        product.product_name,
        product.description,
        product.category.category_name,
        product.part_type,
    ]
    specs = product.get_specs_dict() if hasattr(product, 'get_specs_dict') else {}
    if isinstance(specs, dict):
        parts.extend(str(value) for value in specs.values())
    return ' '.join(parts).lower()


def _score_product(product, budget, use_case, category_slug):
    score = 0
    text = _text_from_product(product)

    if product.price and product.price > 0:
        delta = abs(product.price - budget)
        score += max(0, 1200 - (delta / 18))

    if category_slug and product.category.slug == category_slug:
        score += 250

    keywords = USE_CASE_KEYWORDS.get(use_case, {}).get(product.category.slug, [])
    matches = sum(1 for keyword in keywords if keyword in text)
    score += matches * 80

    if 'ryzen' in text or 'intel' in text or 'nvidia' in text or 'amd' in text:
        score += 30

    if product.is_available:
        score += 50

    if product.price and product.price <= budget * 1.15:
        score += 60

    return score


def _build_recommendations(budget, use_case, category_slug=None):
    queryset = Product.objects.filter(is_available=True, price__gt=0).select_related('category')
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    results = []
    for product in queryset.order_by('price')[:200]:
        product_score = _score_product(product, budget, use_case, category_slug)
        results.append({
            'product': product,
            'score': round(product_score, 2),
            'reason': _explain_recommendation(product, use_case),
        })

    results = sorted(results, key=lambda item: item['score'], reverse=True)
    return results[:3]


def _explain_recommendation(product, use_case):
    use_case_labels = {
        'gaming': 'ideal para gaming y rendimiento',
        'trabajo': 'muy buena opción para trabajo y productividad',
        'estudio': 'equilibrio práctico para estudio y oficina',
        'streaming': 'sólido para streaming y contenido',
    }
    return f'{product.category.category_name} · {use_case_labels.get(use_case, "recomendado")}'


def _default_assistant_state():
    return {
        'selected_use_case': 'gaming',
        'selected_category': '',
        'selected_budget': 15000,
    }


def assistant(request):
    defaults = _default_assistant_state()
    form = AssistantForm(
        request.GET or None,
        category_choices=_category_choices(),
        initial={
            'use_case': defaults['selected_use_case'],
            'budget': defaults['selected_budget'],
            'category': defaults['selected_category'],
        },
    )

    selected_use_case = defaults['selected_use_case']
    selected_category = defaults['selected_category']
    selected_budget = defaults['selected_budget']
    recommendations = []

    if request.GET:
        if form.is_valid():
            selected_use_case = form.cleaned_data.get('use_case', defaults['selected_use_case'])
            selected_category = form.cleaned_data.get('category', defaults['selected_category'])
            selected_budget = form.cleaned_data.get('budget', defaults['selected_budget'])
    else:
        form = AssistantForm(
            initial={
                'use_case': defaults['selected_use_case'],
                'budget': defaults['selected_budget'],
                'category': defaults['selected_category'],
            },
            category_choices=_category_choices(),
        )

    recommendations = _build_recommendations(selected_budget, selected_use_case, selected_category)

    context = {
        'form': form,
        'recommendations': recommendations,
        'selected_use_case': selected_use_case,
        'selected_category': selected_category,
        'selected_budget': selected_budget,
    }
    return render(request, 'assistant/assistant.html', context)
