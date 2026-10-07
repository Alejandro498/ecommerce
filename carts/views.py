from django.shortcuts import render, redirect, get_object_or_404
from store.models import Product, Variation
from .models import Cart, CartItem
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

# Create your views here.

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


def _session_cart(request):
    try:
        return Cart.objects.get(cart_id=_cart_id(request))
    except Cart.DoesNotExist:
        cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()
        return cart


def _variations_from_post(request, product):
    product_variation = []
    if request.method != 'POST':
        return product_variation
    for key in request.POST:
        value = request.POST[key]
        try:
            variation = Variation.objects.get(
                product=product,
                variation_category__iexact=key,
                variation_value__iexact=value,
            )
            product_variation.append(variation)
        except Exception:
            pass
    return product_variation


def _add_product_to_cart(request, product, product_variation=None):
    """Agrega 1 unidad del producto al carrito (usuario o sesion)."""
    product_variation = list(product_variation or [])
    current_user = request.user

    if current_user.is_authenticated:
        cart_items = CartItem.objects.filter(product=product, user=current_user)
        if cart_items.exists():
            ex_var_list = []
            ids = []
            for item in cart_items:
                ex_var_list.append(list(item.variations.all()))
                ids.append(item.id)
            if product_variation in ex_var_list:
                item = CartItem.objects.get(product=product, id=ids[ex_var_list.index(product_variation)])
                item.quantity += 1
                item.save()
                return item
            item = CartItem.objects.create(product=product, quantity=1, user=current_user)
        else:
            item = CartItem.objects.create(product=product, quantity=1, user=current_user)
        if product_variation:
            item.variations.clear()
            item.variations.add(*product_variation)
        item.save()
        return item

    cart = _session_cart(request)
    cart_items = CartItem.objects.filter(product=product, cart=cart)
    if cart_items.exists():
        ex_var_list = []
        ids = []
        for item in cart_items:
            ex_var_list.append(list(item.variations.all()))
            ids.append(item.id)
        if product_variation in ex_var_list:
            item = CartItem.objects.get(product=product, id=ids[ex_var_list.index(product_variation)])
            item.quantity += 1
            item.save()
            return item
        item = CartItem.objects.create(product=product, quantity=1, cart=cart)
    else:
        item = CartItem.objects.create(product=product, quantity=1, cart=cart)
    if product_variation:
        item.variations.clear()
        item.variations.add(*product_variation)
    item.save()
    return item


def add_cart(request, product_id):
    product = Product.objects.get(id=product_id)
    _add_product_to_cart(request, product, _variations_from_post(request, product))
    return redirect('cart')


@require_POST
def add_build_cart(request):
    """Agrega al carrito todos los componentes de una configuracion del asistente."""
    raw_ids = request.POST.getlist('product_id')
    if not raw_ids and request.POST.get('product_ids'):
        raw_ids = [
            piece.strip()
            for piece in str(request.POST.get('product_ids')).split(',')
            if piece.strip()
        ]

    product_ids = []
    for value in raw_ids:
        try:
            product_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    # Mantener orden y quitar duplicados
    seen = set()
    ordered_ids = []
    for product_id in product_ids:
        if product_id in seen:
            continue
        seen.add(product_id)
        ordered_ids.append(product_id)

    products = Product.objects.filter(id__in=ordered_ids, is_available=True)
    by_id = {product.id: product for product in products}
    for product_id in ordered_ids:
        product = by_id.get(product_id)
        if product is None:
            continue
        _add_product_to_cart(request, product, [])

    return redirect('cart')


def remove_cart(request, product_id, cart_item_id):

    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except:
        pass
    return redirect('cart')


def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)

    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(
                product=product, user=request.user, id=cart_item_id,
            )
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(
                product=product, cart=cart, id=cart_item_id,
            )
        cart_item.delete()
    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        # Doble clic / enlace viejo: el item ya no está en el carrito.
        pass
    return redirect('cart')


def cart(request, total=0, quantity=0, cart_items=None):
    tax = 0
    grand_total = 0
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity
        tax = (2*total)/100
        grand_total = total + tax

    except ObjectDoesNotExist:
        pass ## solo ignora la exception

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax' : tax,
        'grand_total': grand_total
    }

    return render(request, 'store/cart.html', context)


@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    tax = 0
    grand_total = 0
    try:

        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)



        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)
            quantity += cart_item.quantity
        tax = (2*total)/100
        grand_total = total + tax

    except ObjectDoesNotExist:
        pass ## solo ignora la exception

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax' : tax,
        'grand_total': grand_total
    }

    return render(request, 'store/checkout.html', context)
