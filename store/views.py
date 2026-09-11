from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, ReviewRating, ProductGallery
from category.models import Category
from carts.models import CartItem
from carts.views import _cart_id
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import ReviewForm
from django.contrib import messages
from orders.models import OrderProduct

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


def store(request, category_slug=None):
    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True).select_related('category').order_by('id')
        product_count = products.count()
    else:
        products = Product.objects.filter(is_available=True).select_related('category').order_by('id')
        product_count = products.count()

    paged_products, page_range = _paginate(request, products)

    context =  {
        'products' : paged_products,
        'product_count': product_count,
        'page_range': page_range,
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
    products = Product.objects.none()
    product_count = 0
    page_range = []
    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products = Product.objects.filter(
                Q(description__icontains=keyword) | Q(product_name__icontains=keyword),
                is_available=True,
            ).select_related('category').order_by('-created_date')
            product_count = products.count()
            products, page_range = _paginate(request, products)
    context = {
        'products': products,
        'product_count': product_count,
        'page_range': page_range,
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
