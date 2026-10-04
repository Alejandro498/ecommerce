import random
from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse

from assistant.compatibility import diagnose, is_compatible
from assistant.fuzzy import score_component, sugeno, trimf, trapmf
from assistant.genetic import (
    BUILD_SLOTS,
    crossover,
    mutate,
    recommend_builds,
    roulette_select,
    tournament_select,
)
from assistant.mamdani import infer_priorities
from assistant.quality_mamdani import component_quality
from assistant.views import _build_recommendations, _has_token
from category.models import Category
from store.models import Product


class FuzzyEngineTests(TestCase):
    def test_membership_helpers(self):
        self.assertEqual(trimf(5, 0, 5, 10), 1.0)
        self.assertEqual(trimf(0, 0, 5, 10), 0.0)
        self.assertEqual(trapmf(5, 0, 4, 6, 10), 1.0)
        self.assertAlmostEqual(sugeno([(1.0, 100.0), (1.0, 0.0)]), 50.0)

    def test_fuzzy_scores_gpu_for_gaming(self):
        category, _ = Category.objects.get_or_create(
            slug='video-card',
            defaults={'category_name': 'GPU', 'description': 'GPU'},
        )
        product = Product(
            product_name='GeForce RTX 4070',
            slug='geforce-rtx-4070-fuzzy',
            description='RTX',
            price=15000,
            stock=3,
            is_available=True,
            category=category,
            part_type='video-card',
            specs={'chipset': 'GeForce RTX 4070', 'memory': 12, 'gpu_brand': 'NVIDIA'},
        )
        score, reasons, parts = score_component(product, 15000, 'gaming')
        self.assertGreater(score, 0)
        self.assertEqual(parts['engine'], 'fuzzy-sugeno')
        self.assertTrue(any('RTX' in r or 'VRAM' in r for r in reasons))


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

    def make_compatible_catalog(self):
        self.make_product(
            'Ryzen 5 5600',
            3000,
            category='cpu',
            specs={'core_count': 6, 'tdp': 65, 'socket': 'AM4', 'brand': 'AMD', 'boost_clock': 4.4},
        )
        self.make_product(
            'Intel i3 LGA1150',
            2800,
            category='cpu',
            specs={'core_count': 4, 'tdp': 54, 'socket': 'LGA1150', 'brand': 'Intel'},
        )
        self.make_product(
            'MSI B550 ATX',
            2000,
            category='motherboard',
            specs={'socket': 'AM4', 'form_factor': 'ATX', 'max_memory': 128, 'memory_slots': 4, 'brand': 'MSI'},
        )
        self.make_product(
            'Corsair Vengeance 16 GB',
            1000,
            category='memory',
            specs={'speed': [4, 3200], 'module_count': 2, 'module_capacity_gb': 8, 'brand': 'Corsair'},
        )
        self.make_product(
            'MSI GeForce RTX 3060 corta',
            4000,
            category='video-card',
            specs={'chipset': 'GeForce RTX 3060', 'memory': 12, 'length': 200, 'gpu_brand': 'NVIDIA'},
        )
        self.make_product(
            'MSI GeForce RTX 3060 larga',
            4500,
            category='video-card',
            specs={'chipset': 'GeForce RTX 3060', 'memory': 12, 'length': 500, 'gpu_brand': 'NVIDIA'},
        )
        self.make_product(
            'Samsung 980 1 TB',
            800,
            category='internal-hard-drive',
            specs={'capacity': 1000, 'type': 'SSD', 'interface': 'M.2 PCIe 4.0 X4', 'brand': 'Samsung'},
        )
        self.make_product(
            'MSI MAG 550W',
            900,
            category='power-supply',
            specs={'wattage': 550, 'efficiency': 'bronze', 'type': 'ATX', 'brand': 'MSI'},
        )
        self.make_product(
            'Fuente 200W insuficiente',
            400,
            category='power-supply',
            specs={'wattage': 200, 'efficiency': 'bronze', 'type': 'ATX'},
        )
        self.make_product(
            'NZXT ATX Mid Tower',
            1000,
            category='case',
            specs={'type': 'ATX Mid Tower', 'max_motherboard_form_factor': 'ATX', 'brand': 'NZXT'},
        )
        self.make_product(
            'Cooler aire 120',
            500,
            category='cpu-cooler',
            specs={'cooler_type': 'Air', 'brand': 'Cooler Master'},
        )

    def test_assistant_page_loads_with_default_recommendations(self):
        self.make_compatible_catalog()
        response = self.client.get(reverse('assistant'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Encuentra tu setup ideal')
        self.assertContains(response, 'Ryzen 5 5600')
        self.assertContains(response, 'Configuración 1')
        self.assertNotContains(response, 'Intel i3 LGA1150')
        self.assertNotContains(response, 'Fuente 200W insuficiente')
        self.assertNotContains(response, 'RTX 3060 larga')

    def test_assistant_page_accepts_filters(self):
        self.make_compatible_catalog()
        response = self.client.get(
            reverse('assistant'),
            {'use_case': 'gaming', 'budget': 15000},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ryzen 5 5600')
        self.assertContains(response, 'Pesos de prioridad')

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
        self.make_compatible_catalog()
        response = self.client.get(reverse('assistant'))
        self.assertContains(response, 'assistant-debug-data')
        self.assertContains(response, 'mamdani+genetic')
        self.assertContains(response, 'ruleta')
        self.assertContains(response, 'Asistente de compras')


def _part(name, price, slot, specs):
    return SimpleNamespace(
        product_name=name,
        price=price,
        specs=specs,
        part_type=slot,
        description=name,
        category=SimpleNamespace(slug=slot, category_name=slot),
        get_specs_dict=lambda specs=specs: specs,
    )


def _sample_pools():
    cpu = _part('Ryzen 5 5600', 3000, 'cpu', {'tdp': 65, 'socket': 'AM4', 'core_count': 6, 'brand': 'AMD'})
    wrong_cpu = _part('Intel i3 LGA1150', 2800, 'cpu', {'tdp': 54, 'socket': 'LGA1150', 'core_count': 4})
    board = _part(
        'MSI B550 ATX',
        2000,
        'motherboard',
        {'socket': 'AM4', 'form_factor': 'ATX', 'max_memory': 128, 'memory_slots': 4},
    )
    memory = _part(
        'Corsair 16 GB',
        1000,
        'memory',
        {'speed': [4, 3200], 'module_count': 2, 'module_capacity_gb': 8},
    )
    gpu = _part(
        'RTX 3060 corta',
        4000,
        'video-card',
        {'chipset': 'GeForce RTX 3060', 'memory': 12, 'length': 200, 'gpu_brand': 'NVIDIA'},
    )
    long_gpu = _part(
        'RTX 3060 larga',
        4500,
        'video-card',
        {'chipset': 'GeForce RTX 3060', 'memory': 12, 'length': 500, 'gpu_brand': 'NVIDIA'},
    )
    storage_a = _part('Samsung 980', 800, 'internal-hard-drive', {'capacity': 1000, 'type': 'SSD'})
    storage_b = _part('WD SN770', 850, 'internal-hard-drive', {'capacity': 1000, 'type': 'SSD'})
    psu = _part('Fuente 550W', 900, 'power-supply', {'wattage': 550, 'efficiency': 'bronze'})
    weak_psu = _part('Fuente 200W', 400, 'power-supply', {'wattage': 200, 'efficiency': 'bronze'})
    case = _part(
        'ATX Mid Tower',
        1000,
        'case',
        {'type': 'ATX Mid Tower', 'max_motherboard_form_factor': 'ATX'},
    )
    cooler = _part('Cooler aire', 500, 'cpu-cooler', {'cooler_type': 'Air'})
    pools = {
        'cpu': [cpu, wrong_cpu],
        'video-card': [gpu, long_gpu],
        'memory': [memory],
        'motherboard': [board],
        'internal-hard-drive': [storage_a, storage_b],
        'power-supply': [psu, weak_psu],
        'case': [case],
        'cpu-cooler': [cooler],
    }
    good = {
        'cpu': cpu,
        'video-card': gpu,
        'memory': memory,
        'motherboard': board,
        'internal-hard-drive': storage_a,
        'power-supply': psu,
        'case': case,
        'cpu-cooler': cooler,
    }
    return pools, good, storage_b


class MamdaniAndBuildTests(TestCase):
    def test_second_mamdani_ranks_parts_by_use(self):
        rtx = _part(
            'GeForce RTX 4070',
            8000,
            'video-card',
            {'chipset': 'GeForce RTX 4070', 'memory': 12, 'gpu_brand': 'NVIDIA'},
        )
        weak = _part(
            'GeForce GT 710',
            900,
            'video-card',
            {'chipset': 'GeForce GT 710', 'memory': 2, 'gpu_brand': 'NVIDIA'},
        )
        nvme = _part(
            'Samsung 980',
            900,
            'internal-hard-drive',
            {'type': 'SSD', 'capacity': 1000, 'interface': 'M.2 PCIe 4.0 X4'},
        )
        hdd = _part(
            'WD Blue',
            400,
            'internal-hard-drive',
            {'type': 'HDD', 'capacity': 1000, 'interface': 'SATA'},
        )
        ryzen = _part('AMD Ryzen 5 5600', 3000, 'cpu', {'core_count': 6, 'tdp': 65, 'boost_clock': 4.4})
        celeron = _part('Intel Celeron G6900', 1500, 'cpu', {'core_count': 2, 'tdp': 46, 'boost_clock': 3.4})

        self.assertGreater(component_quality(rtx, 'gaming'), component_quality(weak, 'gaming'))
        self.assertGreater(component_quality(weak, 'estudio'), component_quality(rtx, 'estudio'))
        self.assertGreater(component_quality(nvme, 'gaming'), component_quality(hdd, 'gaming'))
        self.assertGreater(component_quality(ryzen, 'gaming'), component_quality(celeron, 'gaming'))

    def test_mamdani_raises_gpu_priority_for_gaming(self):
        gaming = infer_priorities(60000, 'gaming')
        estudio = infer_priorities(8000, 'estudio')
        trabajo = infer_priorities(60000, 'trabajo')
        self.assertGreater(gaming['video-card']['score'], 80)
        self.assertEqual(gaming['video-card']['label'], 'Muy alta')
        self.assertLess(estudio['video-card']['score'], 35)
        self.assertIn(estudio['video-card']['label'], ('Muy baja', 'Baja'))
        self.assertGreater(trabajo['cpu']['score'], trabajo['video-card']['score'])

    def test_compatibility_filter_blocks_socket_power_and_size(self):
        _pools, good, _storage_b = _sample_pools()
        self.assertEqual(diagnose(good), [])
        self.assertTrue(is_compatible(good))

        wrong_socket = dict(good)
        wrong_socket['cpu'] = _pools['cpu'][1]
        self.assertIn('socket', diagnose(wrong_socket))

        weak_power = dict(good)
        weak_power['power-supply'] = _pools['power-supply'][1]
        self.assertIn('power', diagnose(weak_power))

        too_long = dict(good)
        too_long['video-card'] = _pools['video-card'][1]
        self.assertIn('gpu_size', diagnose(too_long))

    def test_genetic_search_returns_only_compatible_parts(self):
        pools, _good, _storage_b = _sample_pools()
        result = recommend_builds(15000, 'gaming', pools=pools, seed=7, generations=6, population_size=8)
        self.assertTrue(result['builds'])
        self.assertEqual(result['debug']['engine'], 'mamdani+genetic')
        self.assertEqual(result['debug']['seleccion'], 'ruleta')
        names = {
            part['product'].product_name
            for build in result['builds']
            for part in build['parts']
        }
        self.assertIn('Ryzen 5 5600', names)
        self.assertNotIn('Intel i3 LGA1150', names)
        self.assertNotIn('Fuente 200W', names)
        self.assertNotIn('RTX 3060 larga', names)
        for build in result['builds']:
            chromosome = {part['slot']: part['product'] for part in build['parts']}
            self.assertEqual(set(chromosome), set(BUILD_SLOTS))
            self.assertTrue(is_compatible(chromosome))
            self.assertLessEqual(build['total_price'], 15000 * 1.05)

    def test_crossover_exchanges_components(self):
        pools, good, storage_b = _sample_pools()
        other = dict(good)
        other['internal-hard-drive'] = storage_b
        mixed = False
        rng = random.Random(1)
        for _ in range(20):
            child = crossover(rng, good, other)
            for slot in BUILD_SLOTS:
                self.assertIn(child[slot], (good[slot], other[slot]))
            if child['internal-hard-drive'] is storage_b and child['cpu'] is good['cpu']:
                mixed = True
        self.assertTrue(mixed)

    def test_mutation_swaps_a_compatible_component(self):
        from assistant.genetic import PoolIndex

        pools, good, storage_b = _sample_pools()
        index = PoolIndex(pools)
        rng = random.Random(3)
        changed = False
        for _ in range(40):
            child = mutate(rng, good, index, 20000, rate=1)
            self.assertTrue(is_compatible(child))
            if child['internal-hard-drive'] is storage_b:
                changed = True
        self.assertTrue(changed)

    def test_roulette_ignores_zero_fitness_and_tournament_picks_the_best(self):
        _pools, good, storage_b = _sample_pools()
        other = dict(good)
        other['internal-hard-drive'] = storage_b
        scored = [(0, other), (0, other), (12, good)]
        rng = random.Random(5)
        for _ in range(15):
            self.assertIs(roulette_select(rng, scored)['cpu'], good['cpu'])
            self.assertIs(roulette_select(rng, scored)['internal-hard-drive'], good['internal-hard-drive'])

        ranked = [(1, other), (4, other), (9, good)]
        wins = 0
        for _ in range(40):
            winner = tournament_select(rng, ranked, k=3)
            if winner['internal-hard-drive'] is good['internal-hard-drive']:
                wins += 1
        self.assertGreater(wins, 20)
