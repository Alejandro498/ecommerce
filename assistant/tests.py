from django.test import TestCase
from django.urls import reverse

from category.models import Category
from store.models import Product


class AssistantViewTests(TestCase):
    def test_assistant_page_loads_with_default_recommendations(self):
        category = Category.objects.create(category_name='Procesadores', slug='cpu', description='CPU')
        Product.objects.create(
            product_name='CPU para prueba gaming',
            slug='cpu-para-prueba-gaming',
            description='Muy buena para gaming y rendimiento',
            price=15000,
            stock=5,
            is_available=True,
            category=category,
            part_type='cpu',
            specs='{"cores": 8}',
        )

        response = self.client.get(reverse('assistant'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Encuentra tu setup ideal')
        self.assertContains(response, 'CPU para prueba gaming')

    def test_assistant_page_accepts_filters(self):
        category = Category.objects.create(category_name='Procesadores', slug='cpu', description='CPU')
        Product.objects.create(
            product_name='CPU filtro gaming',
            slug='cpu-filtro-gaming',
            description='gaming',
            price=12000,
            stock=10,
            is_available=True,
            category=category,
            part_type='cpu',
            specs='{"cores": 8}',
        )

        response = self.client.get(reverse('assistant'), {'use_case': 'gaming', 'budget': 15000, 'category': 'cpu'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CPU filtro gaming')
