from django.test import TestCase
from django.urls import reverse

from assistant.views import _build_recommendations, _has_token
from category.models import Category
from store.models import Product


class AssistantViewTests(TestCase):
    def category(self, slug, name=None):
        label = name or slug.replace('-', ' ').title()
        obj, _created = Category.objects.get_or_create(
            slug=slug,
            defaults={'category_name': label, 'description': label},
        )
        return obj

    def make_product(
        self,
        name,
        price,
        category='cpu',
        stock=5,
        specs=None,
        part_type=None,
        is_available=True,
    ):
        category_obj = self.category(category)
        slug = name.lower().replace(' ', '-').replace('/', '-')[:80]
        suffix = 2
        while Product.objects.filter(slug=slug).exists():
            slug = f'{slug[:70]}-{suffix}'
            suffix += 1
        return Product.objects.create(
            product_name=name,
            slug=slug,
            description=name,
            price=price,
            stock=stock,
            is_available=is_available,
            category=category_obj,
            part_type=part_type or category,
            specs=specs or {},
        )

    def names(self, recommendations):
        return [item['product'].product_name for item in recommendations]

    def test_assistant_page_loads_with_default_recommendations(self):
        self.make_product('CPU para prueba gaming', 15000, specs={'core_count': 8})
        response = self.client.get(reverse('assistant'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Encuentra tu setup ideal')
        self.assertContains(response, 'CPU para prueba gaming')

    def test_assistant_page_accepts_filters(self):
        self.make_product('CPU filtro gaming', 12000, specs={'core_count': 6})
        response = self.client.get(
            reverse('assistant'),
            {'use_case': 'gaming', 'budget': 15000, 'category': 'cpu'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CPU filtro gaming')

    def test_keyword_matching_uses_word_boundaries(self):
        self.assertFalse(_has_token('18gb ddr4', '8gb'))
        self.assertTrue(_has_token('8gb ddr4', '8gb'))
        self.assertTrue(_has_token('GeForce RTX 3060', 'rtx'))

    def test_pool_prefers_budget_over_cheapest(self):
        self.make_product(
            'GPU barata RTX',
            400,
            category='video-card',
            specs={'chipset': 'GeForce RTX 3060', 'memory': 12, 'gpu_brand': 'NVIDIA'},
        )
        target = self.make_product(
            'GPU presupuesto RTX',
            14900,
            category='video-card',
            specs={'chipset': 'GeForce RTX 4070', 'memory': 12, 'gpu_brand': 'NVIDIA'},
        )
        recommendations = _build_recommendations(15000, 'gaming', 'video-card')
        self.assertEqual(self.names(recommendations), [target.product_name])

    def test_specs_outrank_generic_card_at_same_price(self):
        generic = self.make_product(
            'GPU generica sin specs',
            15000,
            category='video-card',
            specs={'chipset': 'Unknown 9001', 'memory': 4, 'gpu_brand': 'Other'},
        )
        rtx = self.make_product(
            'GPU RTX 4070 16GB',
            15100,
            category='video-card',
            specs={'chipset': 'GeForce RTX 4070', 'memory': 16, 'gpu_brand': 'NVIDIA'},
        )
        recommendations = _build_recommendations(15000, 'gaming', 'video-card')
        names = self.names(recommendations)
        self.assertEqual(names[0], rtx.product_name)
        self.assertIn(generic.product_name, names)

    def test_use_cases_rank_cpus_differently(self):
        x3d = self.make_product(
            'AMD Ryzen 7 7800X3D',
            8000,
            specs={'core_count': 8, 'tdp': 120, 'boost_clock': 5.0, 'brand': 'AMD'},
        )
        study = self.make_product(
            'Intel Core i5-12400',
            7900,
            specs={'core_count': 6, 'tdp': 65, 'boost_clock': 4.4, 'brand': 'Intel'},
        )
        gaming = self.names(_build_recommendations(8000, 'gaming', 'cpu'))
        estudio = self.names(_build_recommendations(8000, 'estudio', 'cpu'))
        self.assertEqual(gaming[0], x3d.product_name)
        self.assertEqual(estudio[0], study.product_name)

    def test_zero_stock_is_excluded(self):
        self.make_product(
            'GPU sin stock',
            15000,
            category='video-card',
            stock=0,
            specs={'chipset': 'GeForce RTX 4070', 'memory': 16, 'gpu_brand': 'NVIDIA'},
        )
        available = self.make_product(
            'GPU con stock',
            14800,
            category='video-card',
            stock=3,
            specs={'chipset': 'GeForce RTX 4060', 'memory': 8, 'gpu_brand': 'NVIDIA'},
        )
        recommendations = _build_recommendations(15000, 'gaming', 'video-card')
        self.assertEqual(self.names(recommendations), [available.product_name])

    def test_reason_mentions_specs_not_only_price(self):
        self.make_product(
            'Sapphire PULSE RTX',
            15000,
            category='video-card',
            specs={'chipset': 'GeForce RTX 4070', 'memory': 16, 'gpu_brand': 'NVIDIA'},
        )
        recommendations = _build_recommendations(15000, 'gaming', 'video-card')
        reason = recommendations[0]['reason'].lower()
        self.assertTrue('rtx' in reason or 'vram' in reason)

    def test_debug_payload_explains_ranking(self):
        self.make_product(
            'GPU RTX debug',
            15000,
            category='video-card',
            specs={'chipset': 'GeForce RTX 4070', 'memory': 16, 'gpu_brand': 'NVIDIA'},
        )
        recommendations, debug = _build_recommendations(
            15000, 'gaming', 'video-card', with_debug=True,
        )
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(debug['origen_pool'], 'db')
        self.assertEqual(debug['categorias_evaluadas'], ['video-card'])
        self.assertEqual(debug['pool_size'], 1)
        row = debug['top'][0]
        self.assertEqual(row['nombre'], 'GPU RTX debug')
        self.assertEqual(
            round(row['score_precio'] + row['score_specs'] + row['score_keywords'], 2),
            row['score_total'],
        )
        self.assertIn('rtx', row['keywords'])

    def test_assistant_page_embeds_console_debug(self):
        self.make_product('CPU consola', 15000, specs={'core_count': 8})
        response = self.client.get(reverse('assistant'))
        self.assertContains(response, 'assistant-debug-data')
        self.assertContains(response, 'score_precio')
        self.assertContains(response, 'Asistente de compras')
