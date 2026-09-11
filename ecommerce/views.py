from django.shortcuts import render
from store.models import Product

FEATURED_CATEGORY_SLUGS = [
    'cpu',
    'video-card',
    'motherboard',
    'memory',
    'internal-hard-drive',
    'power-supply',
    'case',
    'monitor',
]

def home(request):
    products = []
    for slug in FEATURED_CATEGORY_SLUGS:
        product = (
            Product.objects.filter(category__slug=slug, is_available=True, price__gt=0)
            .select_related('category')
            .order_by('-price')
            .first()
        )
        if product:
            products.append(product)

    context = {
        'products': products,
    }

    return render(request, 'home.html', context)
