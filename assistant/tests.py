from django.test import TestCase
from django.urls import reverse

from category.models import Category
from store.models import Product


class AssistantViewTests(TestCase):
    def create_product(self, name, price):
        category = Category.objects.create(
            category_name='Procesadores', slug='cpu', description='CPU',
        )
        return Product.objects.create(
            product_name=name,
            slug=name.lower().replace(' ', '-'),
            description='Muy buena para gaming y rendimiento',
            price=price,
            stock=5,
            is_available=True,
            category=category,
            part_type='cpu',
            specs={'cores': 8},
        )

    def test_assistant_page_loads_with_default_recommendations(self):
        self.create_product('CPU para prueba gaming', 15000)
        response = self.client.get(reverse('assistant'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Encuentra tu setup ideal')
        self.assertContains(response, 'CPU para prueba gaming')

    def test_assistant_page_accepts_filters(self):
        self.create_product('CPU filtro gaming', 12000)
        response = self.client.get(
            reverse('assistant'),
            {'use_case': 'gaming', 'budget': 15000, 'category': 'cpu'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CPU filtro gaming')