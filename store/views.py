from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from .models import Product, ReviewRating, ProductGallery
from category.models import Category
from carts.models import CartItem
from carts.views import _cart_id
from django.core.paginator import Paginator
from .forms import ReviewForm
from django.contrib import messages
from orders.models import OrderProduct
from .catalog_concurrent import CSV_BY_SLUG, fetch_catalog_concurrent

PRODUCTS_PER_PAGE = 12


def _page_numbers(num_pages):
    if num_pages <= 6:
        return list(range(1, num_pages + 1))
    first = [1, 2, 3]
    last = [num_pages - 2, num_pages - 1, num_pages]
    if first[-1] + 1 >= last[0]:
        return list(range(1, num_pages + 1))
    return first + ['jump'] + last


def _paginate(request, queryset, per_page=PRODUCTS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    return page_obj, _page_numbers(paginator.num_pages)


def _parse_price_param(raw):
    if raw in (None, ''):
        return None
    try:
        val = int(float(str(raw).replace('$', '').replace(',', '').strip()))
        return max(0, val)
    except (ValueError, TypeError):
        return None


def store(request, category_slug=None):
    if category_slug is not None:
        try:
            Category.objects.get(slug=category_slug)
        except Category.DoesNotExist:
            if category_slug not in CSV_BY_SLUG:
                raise Http404('No Category matches the given query.')
        except Exception:
            # DB caída: seguimos si el slug existe en el mapa CSV.
            if category_slug not in CSV_BY_SLUG:
                raise

    raw_min = request.GET.get('min_price')
    raw_max = request.GET.get('max_price')
    min_price = _parse_price_param(raw_min)
    max_price = _parse_price_param(raw_max)

    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    from .spec_filters import extract_spec_filters_from_request
    spec_filters = extract_spec_filters_from_request(request, category_slug)

    products, product_count, catalog_trace, min_bound, max_bound, spec_filter_definitions = fetch_catalog_concurrent(
        category_slug=category_slug,
        keyword=None,
        min_price=min_price,
        max_price=max_price,
        spec_filters=spec_filters,
    )

    # Ordenamiento por precio
    sort_by = request.GET.get('sort_by', '')
    if sort_by == 'price_asc':
        products = sorted(products, key=lambda p: (p.price if p.price else 0))
    elif sort_by == 'price_desc':
        products = sorted(products, key=lambda p: (p.price if p.price else 0), reverse=True)

    paged_products, page_range = _paginate(request, products)

    selected_min = min_price if min_price is not None else min_bound
    selected_max = max_price if max_price is not None else max_bound
    has_price_filter = bool(raw_min not in (None, '') or raw_max not in (None, ''))
    has_spec_filter = bool(spec_filters)
    is_filtered = has_price_filter or has_spec_filter

    query_params = request.GET.copy()
    query_params.pop('page', None)
    pagination_query = query_params.urlencode()

    active_filters = []
    if has_price_filter:
        active_filters.append({
            'label': f"Precio: ${selected_min} - ${selected_max}",
        })
    for defn in spec_filter_definitions:
        for opt in defn['options']:
            if opt['is_selected']:
                active_filters.append({
                    'label': f"{defn['title']}: {opt['label']}",
                })

    context = {
        'products': paged_products,
        'product_count': product_count,
        'page_range': page_range,
        'catalog_trace': catalog_trace,
        'category_slug': category_slug,
        'min_price_bound': min_bound,
        'max_price_bound': max_bound,
        'selected_min_price': selected_min,
        'selected_max_price': selected_max,
        'spec_filter_definitions': spec_filter_definitions,
        'active_filters': active_filters,
        'is_filtered': is_filtered,
        'pagination_query': pagination_query,
        'sort_by': sort_by,
    }

    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.select_related('category').get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
    except Exception as e:
        raise e

    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(user=request.user, product_id=single_product.id).exists()
        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None


    reviews = ReviewRating.objects.filter(product_id=single_product.id, status=True)

    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
        'product_specs': single_product.formatted_specs(),
    }

    return render(request, 'store/product_detail.html', context)


def search(request):
    products = []
    product_count = 0
    page_range = []
    catalog_trace = None
    min_bound = 0
    max_bound = 1000
    selected_min = 0
    selected_max = 1000
    spec_filter_definitions = []
    raw_min = request.GET.get('min_price')
    raw_max = request.GET.get('max_price')
    min_price = _parse_price_param(raw_min)
    max_price = _parse_price_param(raw_max)

    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    sort_by = request.GET.get('sort_by', '')

    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products, product_count, catalog_trace, min_bound, max_bound, spec_filter_definitions = fetch_catalog_concurrent(
                category_slug=None,
                keyword=keyword,
                min_price=min_price,
                max_price=max_price,
            )
            # Ordenamiento por precio
            if sort_by == 'price_asc':
                products = sorted(products, key=lambda p: (p.price if p.price else 0))
            elif sort_by == 'price_desc':
                products = sorted(products, key=lambda p: (p.price if p.price else 0), reverse=True)
            products, page_range = _paginate(request, products)
            selected_min = min_price if min_price is not None else min_bound
            selected_max = max_price if max_price is not None else max_bound

    has_price_filter = bool(raw_min not in (None, '') or raw_max not in (None, ''))
    is_filtered = has_price_filter

    query_params = request.GET.copy()
    query_params.pop('page', None)
    pagination_query = query_params.urlencode()

    active_filters = []
    if has_price_filter:
        active_filters.append({
            'label': f"Precio: ${selected_min} - ${selected_max}",
        })

    context = {
        'products': products,
        'product_count': product_count,
        'page_range': page_range,
        'catalog_trace': catalog_trace,
        'category_slug': None,
        'min_price_bound': min_bound,
        'max_price_bound': max_bound,
        'selected_min_price': selected_min,
        'selected_max_price': selected_max,
        'spec_filter_definitions': spec_filter_definitions,
        'active_filters': active_filters,
        'is_filtered': is_filtered,
        'pagination_query': pagination_query,
        'sort_by': sort_by,
    }

    return render(request, 'store/store.html', context)


def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Muchas gracias!, tu comentario ha sido actualizado')
            return redirect(url)
        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Muchas gracias, tu comentario fue enviado con exito!')
                return redirect(url)
