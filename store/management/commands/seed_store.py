import os

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from category.models import Category
from store.models import Product, Variation


class Command(BaseCommand):
    help = 'Create sample categories and products matching the item images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing categories and products before seeding',
        )

    def handle(self, *args, **options):
        if Product.objects.exists() and not options['reset']:
            self.stdout.write(self.style.WARNING('Products already exist. Use --reset to replace them.'))
            return

        if options['reset']:
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write('Existing store data removed.')

        static_images = settings.BASE_DIR / 'ecommerce' / 'static' / 'images' / 'items'

        # Names match what is actually in each image file.
        categories_data = [
            ('Ropa', 'ropa', 'Ropa y moda'),
            ('Zapatos', 'zapatos', 'Calzado y sneakers'),
            ('Accesorios', 'accesorios', 'Bolsos y complementos'),
            ('Hogar', 'hogar', 'Muebles y hogar'),
            ('Electronica', 'electronica', 'Gadgets y tecnologia'),
        ]

        products_data = [
            ('Camisa Moderna', 'camisa-moderna', 120, 'ropa', 25, '1.jpg'),
            ('Chaqueta Invierno', 'chaqueta-invierno', 499, 'ropa', 12, '2.jpg'),
            ('Shorts Denim', 'shorts-denim', 250, 'ropa', 18, '3.jpg'),
            ('Camisa Estampada', 'camisa-estampada', 135, 'ropa', 20, '900.jpg'),
            ('Camisa Azul Corta', 'camisa-azul-corta', 110, 'ropa', 22, '1000.jpg'),
            ('Zapatillas High Top', 'zapatillas-high-top', 159, 'zapatos', 15, '12.jpg'),
            ('Sneakers Cuero Azul', 'sneakers-cuero-azul', 189, 'zapatos', 12, '12-1.jpg'),
            ('Mochila Azul', 'mochila-azul', 350, 'accesorios', 20, '4.jpg'),
            ('Funda para Laptop', 'funda-para-laptop', 180, 'accesorios', 15, '5.jpg'),
            ('Sillon Gris', 'sillon-gris', 1299, 'hogar', 6, '6.jpg'),
            ('Silla Plegable', 'silla-plegable', 45, 'hogar', 30, '1003.jpg'),
            ('Silla Gaming RESPAWN', 'silla-gaming-respawn', 299, 'hogar', 10, '1004.jpg'),
            ('Silla Oficina Mesh', 'silla-oficina-mesh', 189, 'hogar', 14, '1005.jpg'),
            ('Apple Watch', 'apple-watch', 999, 'electronica', 10, '7.jpg'),
            ('Apple Watch Rose Gold', 'apple-watch-rose-gold', 399, 'electronica', 8, '1001.jpg'),
            ('AirPods', 'airpods', 199, 'electronica', 30, '8.jpg'),
            ('AirPods Pro', 'airpods-pro', 249, 'electronica', 25, '700.jpg'),
            ('AirPods Max', 'airpods-max', 549, 'electronica', 12, '800.jpg'),
            ('Auriculares Premium', 'auriculares-premium', 299, 'electronica', 22, '9.jpg'),
            ('Termostato Inteligente', 'termostato-inteligente', 349, 'electronica', 14, '10.jpg'),
            ('GoPro Hero', 'gopro-hero', 399, 'electronica', 18, '11.jpg'),
            ('Logitech M720 Mouse', 'logitech-m720-mouse', 89, 'electronica', 40, '500.jpg'),
            ('Sistema Bocinas 2.1', 'sistema-bocinas-2-1', 179, 'electronica', 16, '400.jpg'),
            ('Monitor MSI Gaming', 'monitor-msi-gaming', 329, 'electronica', 11, '600.jpg'),
            ('iPad Pro', 'ipad-pro', 1099, 'electronica', 7, '1002.jpg'),
            ('HP Laptop 14 i3', 'hp-laptop-14-i3', 649, 'electronica', 9, '100.jpg'),
            ('HP Laptop 15 i5 Touch', 'hp-laptop-15-i5-touch', 899, 'electronica', 8, '200.jpg'),
            ('Lenovo Laptop i5 16GB', 'lenovo-laptop-i5-16gb', 949, 'electronica', 7, '300.jpg'),
            ('MacBook Air', 'macbook-air', 999, 'electronica', 6, '1006.jpg'),
            ('Lenovo Desktop Ryzen 5', 'lenovo-desktop-ryzen-5', 799, 'electronica', 5, '1007.jpg'),
        ]

        colors = ['Azul', 'Rojo', 'Verde', 'Negro']
        sizes = ['S', 'M', 'L', 'XL']
        shoe_sizes = ['38', '39', '40', '41', '42', '43']

        categories = {}
        for category_name, slug, description in categories_data:
            category = Category.objects.create(
                category_name=category_name,
                slug=slug,
                description=description,
            )
            categories[slug] = category
            self.stdout.write(f'Created category: {category.category_name}')

        for product_name, slug, price, category_slug, stock, image_name in products_data:
            image_path = static_images / image_name
            if not image_path.exists():
                self.stdout.write(self.style.ERROR(f'Missing image: {image_name}'))
                continue

            product = Product(
                product_name=product_name,
                slug=slug,
                description=f'Descripcion de {product_name}',
                price=price,
                stock=stock,
                is_available=True,
                category=categories[category_slug],
            )
            with open(image_path, 'rb') as image_file:
                product.images.save(
                    f'{slug}-{image_name}',
                    File(image_file),
                    save=False,
                )
            product.save()

            if category_slug == 'ropa':
                for color in colors:
                    Variation.objects.create(
                        product=product,
                        variation_category='color',
                        variation_value=color,
                        is_active=True,
                    )
                for size in sizes:
                    Variation.objects.create(
                        product=product,
                        variation_category='talla',
                        variation_value=size,
                        is_active=True,
                    )
            elif category_slug == 'zapatos':
                for size in shoe_sizes:
                    Variation.objects.create(
                        product=product,
                        variation_category='talla',
                        variation_value=size,
                        is_active=True,
                    )

            self.stdout.write(f'Created product: {product.product_name} -> {image_name}')

        self.stdout.write(self.style.SUCCESS('Store seeded successfully.'))
