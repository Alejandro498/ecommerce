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
    specs = models.TextField(default='{}', blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def get_specs_dict(self):
        value = self.specs
        if isinstance(value, dict):
            return value
        if value in (None, '', 'null'):
            return {}
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except (TypeError, ValueError):
            return {}

    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])

    def get_image_url(self):
        try:
            if self.images:
                return self.images.url
        except ValueError:
            pass
        return static('images/pc-part-placeholder.png')

    def formatted_specs(self):
        items = []
        for key, value in self.get_specs_dict().items():
            if value in (None, '', [], {}):
                continue
            items.append((_spec_label(key), _format_spec_value(key, value)))
        return items

    def save(self, *args, **kwargs):
        if isinstance(self.specs, dict):
            self.specs = json.dumps(self.specs, ensure_ascii=False)
        super().save(*args, **kwargs)

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
        'cas_latency': 'CAS Latency',
        'price_per_gb': 'Price / GB',
        'smt': 'SMT',
        'pwm': 'PWM',
        'snr': 'SNR',
        'fov': 'FOV',
        'os': 'OS',
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
