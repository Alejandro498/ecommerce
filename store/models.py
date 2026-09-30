import json

from django.db import models
from category.models import Category
from django.urls import reverse
from django.templatetags.static import static
from accounts.models import Account
from django.db.models import Avg, Count

# Create your models here.
class Product(models.Model):
    product_name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    price = models.IntegerField()
    images = models.ImageField(upload_to='photos/products', blank=True)
    stock = models.IntegerField()
    is_available = models.BooleanField(default=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    part_type = models.CharField(max_length=40, blank=True, db_index=True)
    specs = models.JSONField(default=dict, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])

    def get_image_url(self):
        try:
            if self.images and 'pc-part-placeholder' not in self.images.name:
                return self.images.url
        except (ValueError, AttributeError):
            pass

        placeholders = {
            'cpu-intel': 'images/placeholders/cpu-intel.jpg',
            'cpu-amd': 'images/placeholders/cpu-amd.jpg',
            'video-card-intel': 'images/placeholders/video-card-intel.jpg',
            'video-card-amd': 'images/placeholders/video-card-amd.jpg',
            'video-card-nvidia': 'images/placeholders/video-card-nvidia.jpg',
            'motherboard-intel': 'images/placeholders/motherboard-intel.jpg',
            'motherboard-asus': 'images/placeholders/motherboard-asus.jpg',
            'motherboard-asrock': 'images/placeholders/motherboard-asrock.jpg',
            'motherboard-nzxt': 'images/placeholders/motherboard-nzxt.jpg',
            'motherboard-gigabyte': 'images/placeholders/motherboard-gigabyte.jpg',
            'motherboard-msi': 'images/placeholders/motherboard-msi.jpg',
            'memory': 'images/placeholders/memory.jpg',
            'internal-hard-drive': 'images/placeholders/internal-hard-drive.jpg',
            'power-supply': 'images/placeholders/power-supply.jpg',
            'cpu-cooler': 'images/placeholders/cpu-cooler.jpg',
            'case': 'images/placeholders/case.jpg',
        }

        part = (self.part_type or '').strip().lower()
        
        # CPU: distinguir Intel y AMD
        if part == 'cpu':
            brand = (self.specs.get('brand') or '').strip().lower()

            if brand == 'intel':
                return static(placeholders['cpu-intel'])

            if brand == 'amd':
                return static(placeholders['cpu-amd'])

            # CPU sin marca reconocida
            return static('images/placeholders/cpu.jpg')
        
        # GPU: distinguir Intel AMD y Nvidia
        if part == 'video-card':
            brand = (self.specs.get('gpu_brand') or '').strip().lower()

            if brand == 'intel':
                return static(placeholders['video-card-intel'])

            if brand == 'amd':
                return static(placeholders['video-card-amd'])
            
            if brand == 'nvidia':
                return static(placeholders['video-card-nvidia'])

            # GPU sin marca reconocida
            return static('images/placeholders/video-card.jpg')
        
        # MOTHERBOARD: distinguir entre marcas
        if part == 'motherboard':
                brand = (self.specs.get('brand') or '').strip().lower()
    
                if brand == 'intel':
                    return static(placeholders['motherboard-intel'])
    
                if brand == 'asus':
                    return static(placeholders['motherboard-asus'])
                
                if brand == 'asrock':
                    return static(placeholders['motherboard-asrock'])
                
                if brand == 'msi':
                    return static(placeholders['motherboard-msi'])
                
                if brand == 'nzxt':
                    return static(placeholders['motherboard-nzxt'])
                
                if brand == 'gigabyte':
                    return static(placeholders['motherboard-gigabyte'])
    
                # MOTHERBOARD sin marca reconocida
                return static('images/placeholders/motherboard.jpg')
        
        if part in placeholders:
            return static(placeholders[part])

        if self.category:
            cat_slug = (self.category.slug or '').strip().lower()
            if cat_slug in placeholders:
                return static(placeholders[cat_slug])

            cat_name = (self.category.category_name or '').strip().lower()
            if cat_name in placeholders:
                return static(placeholders[cat_name])

        # 3. Fallback genérico por si no coincide ninguno
        return static('images/pc-part-placeholder.png')

    def get_specs_dict(self):
        specs = self.specs or {}
        if isinstance(specs, str):
            try:
                specs = json.loads(specs)
            except (TypeError, ValueError):
                return {}
        return specs if isinstance(specs, dict) else {}

    def formatted_specs(self):
        items = []
        for key, value in self.get_specs_dict().items():
            if value in (None, '', [], {}):
                continue
            items.append((_spec_label(key), _format_spec_value(key, value)))
        return items

    def __str__(self):
        return self.product_name

    def averageReview(self):
        reviews = ReviewRating.objects.filter(product=self, status=True).aggregate(average=Avg('rating'))
        avg=0
        if reviews['average'] is not None:
            avg = float(reviews['average'])
        return avg

    def countReview(self):
        reviews = ReviewRating.objects.filter(product=self, status=True).aggregate(count=Count('id'))
        count=0
        if reviews['count'] is not None:
            count = int(reviews['count'])

        return count


def _spec_label(key):
    labels = {
        'tdp': 'TDP',
        'rpm': 'RPM',
        'rpm_min': 'RPM min',
        'rpm_max': 'RPM max',
        'cas_latency': 'CAS Latency',
        'price_per_gb': 'Price / GB',
        'smt': 'SMT',
        'pwm': 'PWM',
        'snr': 'SNR',
        'fov': 'FOV',
        'os': 'OS',
        'gpu_brand': 'GPU',
        'module_count': 'Modulos',
        'module_capacity_gb': 'Capacidad por modulo (GB)',
        'radiator_size': 'Radiador (mm)',
        'cooler_type': 'Tipo de cooler',
        'included_psu_wattage': 'Fuente incluida (W)',
        'has_included_psu': 'Incluye fuente',
        'max_motherboard_form_factor': 'Formato max. motherboard',
        'noise_min_db': 'Ruido min (dB)',
        'noise_max_db': 'Ruido max (dB)',
        'internal_35_bays': 'Bahias 3.5"',
    }
    return labels.get(key, key.replace('_', ' ').title())


def _format_spec_value(key, value):
    if isinstance(value, bool):
        return 'Sí' if value else 'No'
    if key == 'speed' and isinstance(value, (list, tuple)) and len(value) == 2:
        return f'DDR{value[0]}-{value[1]}'
    if key == 'modules' and isinstance(value, (list, tuple)) and len(value) == 2:
        return f'{value[0]} x {value[1]} GB'
    if key == 'resolution' and isinstance(value, (list, tuple)) and len(value) == 2:
        return f'{value[0]} x {value[1]}'
    if isinstance(value, (list, tuple)):
        return ' / '.join(str(item) for item in value)
    return str(value)


class VariationManager(models.Manager):
    def colors(self):
        return super(VariationManager, self).filter(variation_category='color', is_active=True)

    def tallas(self):
        return super(VariationManager, self).filter(variation_category='talla', is_active=True)


variation_category_choice = (
    ('color', 'color'),
    ('talla', 'talla'),
)

class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation_category = models.CharField(max_length=100, choices=variation_category_choice)
    variation_value = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now=True)

    objects = VariationManager()

    def __str__(self):
        return  self.variation_category + ' : ' +self.variation_value


class ReviewRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100, blank=True)
    review = models.CharField(max_length=500, blank=True)
    rating = models.FloatField()
    ip = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject


class ProductGallery(models.Model):
    product = models.ForeignKey(Product, default=None, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='store/products', max_length=255)

    def __str__(self):
        return self.product.product_name
