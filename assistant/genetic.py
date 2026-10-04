"""
Algoritmo genético para armar una PC completa.

Cromosoma: CPU, GPU, RAM, motherboard, almacenamiento, fuente, gabinete y cooler.
La selección es por ruleta (el torneo queda disponible). El cruce intercambia
piezas entre dos padres y la mutación cambia una pieza por otra compatible.
El filtro de socket, TDP y tamaño corre antes de calcular la aptitud.
La calidad de cada gen sale del segundo Mamdani (assistant/quality_mamdani.py).
"""

from __future__ import annotations

import random
import threading
import zlib
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from assistant.compatibility import (
    BUILD_SLOTS,
    DDR_BY_SOCKET,
    SLOT_LABELS,
    case_clearance,
    case_max_rank,
    compatibility_summary,
    cooler_limits,
    cpu_tdp,
    diagnose,
    form_factor_rank,
    gpu_length_mm,
    gpu_tdp,
    is_compatible,
    power_need,
    psu_watts,
    ram_profile,
    socket_of,
    specs_of,
    to_float,
)
from assistant.mamdani import infer_priorities, priority_rows
from assistant.quality_mamdani import component_quality

POPULATION_SIZE = 20
GENERATIONS = 12
ELITE_COUNT = 2
MUTATION_RATE = 0.35
POOL_LIMIT = 36
BUDGET_HARD_CAP = 1.12

_PRICE_CAP = {
    'cpu': 0.42,
    'video-card': 0.58,
    'memory': 0.28,
    'motherboard': 0.32,
    'internal-hard-drive': 0.28,
    'power-supply': 0.24,
    'case': 0.22,
    'cpu-cooler': 0.18,
}

_CSV_POOLS = None
_CSV_LOCK = threading.Lock()


def roulette_select(rng: random.Random, scored: Sequence[tuple]) -> Dict[str, Any]:
    """Selección proporcional a la aptitud. Los individuos con aptitud 0 no entran."""
    viable = [(fitness, build) for fitness, build in scored if fitness > 0]
    if not viable:
        return copy_build(rng.choice(list(scored))[1])
    total = sum(fitness for fitness, _build in viable)
    ticket = rng.random() * total
    running = 0.0
    for fitness, build in viable:
        running += fitness
        if running >= ticket:
            return copy_build(build)
    return copy_build(viable[-1][1])


def tournament_select(rng: random.Random, scored: Sequence[tuple], k: int = 3) -> Dict[str, Any]:
    """Selección por torneo. Disponible como alternativa a la ruleta."""
    group_size = min(k, len(scored))
    group = [scored[rng.randrange(len(scored))] for _ in range(group_size)]
    _fitness, winner = max(group, key=lambda item: item[0])
    return copy_build(winner)


def crossover(rng: random.Random, parent_a: Dict[str, Any], parent_b: Dict[str, Any]) -> Dict[str, Any]:
    """Cruce uniforme: cada gen se toma de uno de los dos padres."""
    child = {}
    for slot in BUILD_SLOTS:
        donor = parent_a if rng.random() < 0.5 else parent_b
        child[slot] = donor[slot]
    return child


def copy_build(build: Dict[str, Any]) -> Dict[str, Any]:
    return {slot: build[slot] for slot in BUILD_SLOTS}


def total_price(build: Dict[str, Any]) -> int:
    return sum(int(getattr(build[slot], 'price', 0) or 0) for slot in BUILD_SLOTS)


def _part_slug(product: Any) -> str:
    slug = getattr(product, 'part_type', None) or ''
    if slug:
        return slug
    category = getattr(product, 'category', None)
    return getattr(category, 'slug', getattr(product, 'category_slug', '')) or ''


def _usable(slot: str, product: Any) -> bool:
    if not getattr(product, 'price', 0):
        return False
    if slot == 'cpu':
        return bool(socket_of(product))
    if slot == 'motherboard':
        specs = specs_of(product)
        return bool(socket_of(product)) and form_factor_rank(specs.get('form_factor')) is not None
    if slot == 'memory':
        generation, _modules, total = ram_profile(product)
        return generation is not None and total > 0
    if slot == 'power-supply':
        return psu_watts(product) > 0
    if slot == 'case':
        return case_max_rank(product) is not None
    return True


def _stride_sample(items: Sequence[Any], limit: int) -> List[Any]:
    chosen = sorted(items, key=lambda product: (int(product.price or 0), getattr(product, 'product_name', '')))
    if len(chosen) <= limit:
        return chosen
    step = len(chosen) / float(limit)
    return [chosen[int(index * step)] for index in range(limit)]


def _annotate_quality(product: Any, use_case: str) -> float:
    cached = getattr(product, '_recommend_quality', None)
    cached_use = getattr(product, '_recommend_use', None)
    if cached is not None and cached_use == use_case:
        return float(cached)
    quality = component_quality(product, use_case)
    try:
        setattr(product, '_recommend_quality', quality)
        setattr(product, '_recommend_use', use_case)
    except AttributeError:
        pass
    return quality


def _diverse_quality_pool(items: Sequence[Any], use_case: str, limit: int = POOL_LIMIT) -> List[Any]:
    """En cada banda de precio se queda con las piezas de mejor spec para el uso."""
    pool = list(items)
    if len(pool) > 420:
        pool = _stride_sample(pool, 420)
    if len(pool) <= limit:
        for product in pool:
            _annotate_quality(product, use_case)
        return pool
    ranked = [(_annotate_quality(product, use_case), int(product.price or 0), product) for product in pool]
    ranked.sort(key=lambda item: item[1])
    bands = 4
    per_band = max(1, limit // bands)
    selected = []
    step = len(ranked) / float(bands)
    for band in range(bands):
        window = ranked[int(band * step):int((band + 1) * step)] or ranked[-1:]
        window.sort(key=lambda item: item[0], reverse=True)
        selected.extend(product for _quality, _price, product in window[:per_band])
    unique = []
    seen = set()
    for product in selected:
        marker = id(product)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(product)
    return unique[:limit]


def _apply_price_cap(slot: str, items: Sequence[Any], budget: float) -> List[Any]:
    cap = budget * _PRICE_CAP.get(slot, 0.4)
    priced = [product for product in items if 0 < int(product.price or 0) <= cap]
    if priced:
        return priced
    return [product for product in items if 0 < int(product.price or 0) < budget]


class PoolIndex:
    def __init__(self, pools: Dict[str, Sequence[Any]]):
        self.pools = {slot: list(pools.get(slot) or []) for slot in BUILD_SLOTS}
        self.mb_by_socket = defaultdict(list)
        for board in self.pools['motherboard']:
            self.mb_by_socket[socket_of(board)].append(board)
        self.cases_for_rank = {rank: [] for rank in range(1, 6)}
        for case in self.pools['case']:
            rank = case_max_rank(case) or 0
            for needed in range(1, rank + 1):
                self.cases_for_rank[needed].append(case)
        self.ram_by_gen = defaultdict(list)
        for memory in self.pools['memory']:
            generation, _modules, _total = ram_profile(memory)
            if generation is not None:
                self.ram_by_gen[generation].append(memory)

    def ready(self) -> bool:
        return all(self.pools[slot] for slot in BUILD_SLOTS)


def _pick(rng: random.Random, items: Sequence[Any], target: float) -> Optional[Any]:
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    contenders = [items[rng.randrange(len(items))] for _ in range(min(8, len(items)))]

    def _key(product: Any) -> float:
        quality = float(getattr(product, '_recommend_quality', 0) or 0)
        price = int(product.price or 0)
        distance = abs(price - target) / max(target, 1.0)
        return (quality / 100.0) - min(distance, 2.0) * 0.45

    return max(contenders, key=_key)


def _shares(budget: float, priorities: Dict[str, dict]) -> Dict[str, float]:
    # El cuadrado abre la diferencia entre "Muy alta" y "Baja"; si no, el presupuesto se reparte parejo.
    weights = {slot: max(float(priorities[slot]['score']), 8.0) ** 2 for slot in BUILD_SLOTS}
    total = sum(weights.values()) or 1.0
    return {slot: budget * weights[slot] / total for slot in BUILD_SLOTS}


def _within_budget(build: Dict[str, Any], budget: float) -> bool:
    return total_price(build) <= budget * BUDGET_HARD_CAP


def _slot_floors(index: PoolIndex) -> Dict[str, int]:
    floors = {}
    for slot in BUILD_SLOTS:
        prices = [int(product.price or 0) for product in index.pools[slot]]
        floors[slot] = min(prices) if prices else 0
    return floors


def _price_ceiling(budget: float, floors: Dict[str, int], spent: int, chosen: Sequence[str], slot: str) -> float:
    reserve = sum(floors[other] for other in BUILD_SLOTS if other != slot and other not in chosen)
    return budget * BUDGET_HARD_CAP - spent - reserve


def _pick_within(rng: random.Random, items: Sequence[Any], target: float, ceiling: float) -> Optional[Any]:
    affordable = [product for product in items if int(product.price or 0) <= ceiling]
    if not affordable:
        return None
    return _pick(rng, affordable, min(target, max(ceiling, 1.0)))


def random_compatible(
    rng: random.Random,
    index: PoolIndex,
    shares: Dict[str, float],
    budget: float,
) -> Optional[Dict[str, Any]]:
    floors = _slot_floors(index)
    for _attempt in range(28):
        spent = 0
        chosen: List[str] = []
        cpu = _pick_within(
            rng, index.pools['cpu'], shares['cpu'],
            _price_ceiling(budget, floors, spent, chosen, 'cpu'),
        )
        if cpu is None:
            return None
        spent += int(cpu.price or 0)
        chosen.append('cpu')

        boards = index.mb_by_socket.get(socket_of(cpu)) or []
        motherboard = _pick_within(
            rng, boards, shares['motherboard'],
            _price_ceiling(budget, floors, spent, chosen, 'motherboard'),
        )
        if motherboard is None:
            continue
        rank = form_factor_rank(specs_of(motherboard).get('form_factor'))
        if rank is None:
            continue
        spent += int(motherboard.price or 0)
        chosen.append('motherboard')

        case = _pick_within(
            rng, index.cases_for_rank.get(rank) or [], shares['case'],
            _price_ceiling(budget, floors, spent, chosen, 'case'),
        )
        if case is None:
            continue
        spent += int(case.price or 0)
        chosen.append('case')

        allowed = DDR_BY_SOCKET.get(socket_of(cpu))
        ram_pool: List[Any] = []
        if allowed:
            for gen in allowed:
                ram_pool.extend(index.ram_by_gen.get(gen) or [])
        else:
            ram_pool = list(index.pools['memory'])
        ram_pool = [memory for memory in ram_pool if _ram_fits(memory, motherboard)]
        memory = _pick_within(
            rng, ram_pool, shares['memory'],
            _price_ceiling(budget, floors, spent, chosen, 'memory'),
        )
        if memory is None:
            continue
        spent += int(memory.price or 0)
        chosen.append('memory')

        max_gpu, _max_rad = case_clearance(case)
        gpus = [gpu for gpu in index.pools['video-card'] if gpu_length_mm(gpu) <= max_gpu]
        gpu = _pick_within(
            rng, gpus, shares['video-card'],
            _price_ceiling(budget, floors, spent, chosen, 'video-card'),
        )
        if gpu is None:
            continue
        spent += int(gpu.price or 0)
        chosen.append('video-card')

        need = cpu_tdp(cpu) + gpu_tdp(gpu) + 100
        psus = [psu for psu in index.pools['power-supply'] if psu_watts(psu) >= need]
        psu = _pick_within(
            rng, psus, shares['power-supply'],
            _price_ceiling(budget, floors, spent, chosen, 'power-supply'),
        )
        if psu is None:
            continue
        spent += int(psu.price or 0)
        chosen.append('power-supply')

        coolers = [cooler for cooler in index.pools['cpu-cooler'] if _cooler_fits(cooler, case, cpu)]
        cooler = _pick_within(
            rng, coolers, shares['cpu-cooler'],
            _price_ceiling(budget, floors, spent, chosen, 'cpu-cooler'),
        )
        if cooler is None:
            continue
        spent += int(cooler.price or 0)
        chosen.append('cpu-cooler')

        storage = _pick_within(
            rng, index.pools['internal-hard-drive'], shares['internal-hard-drive'],
            _price_ceiling(budget, floors, spent, chosen, 'internal-hard-drive'),
        )
        if storage is None:
            continue
        build = {
            'cpu': cpu,
            'video-card': gpu,
            'memory': memory,
            'motherboard': motherboard,
            'internal-hard-drive': storage,
            'power-supply': psu,
            'case': case,
            'cpu-cooler': cooler,
        }
        if is_compatible(build) and _within_budget(build, budget):
            return build
    return None


def _ram_fits(memory: Any, motherboard: Any) -> bool:
    _generation, modules, total = ram_profile(memory)
    specs = specs_of(motherboard)
    slot_count = to_float(specs.get('memory_slots'))
    max_gb = to_float(specs.get('max_memory'))
    if slot_count is not None and modules > slot_count:
        return False
    if max_gb is not None and total > max_gb:
        return False
    return True


def _cooler_fits(cooler: Any, case: Any, cpu: Any) -> bool:
    _watts, radiator = cooler_limits(cooler)
    _gpu, max_radiator = case_clearance(case)
    capacity, _radiator = cooler_limits(cooler)
    return radiator <= max_radiator and capacity >= cpu_tdp(cpu)


def _replacement_ok(build: Dict[str, Any], slot: str, candidate: Any, budget: float) -> bool:
    trial = copy_build(build)
    trial[slot] = candidate
    return is_compatible(trial) and _within_budget(trial, budget)


def mutate(
    rng: random.Random,
    build: Dict[str, Any],
    index: PoolIndex,
    budget: float,
    rate: float = MUTATION_RATE,
) -> Dict[str, Any]:
    """Cambia un gen por otro componente que deje la build compatible."""
    if rng.random() > rate:
        return build
    child = copy_build(build)
    slot = BUILD_SLOTS[rng.randrange(len(BUILD_SLOTS))]
    pool = index.pools[slot]
    if len(pool) < 2:
        return child
    for _try in range(10):
        candidate = pool[rng.randrange(len(pool))]
        if candidate is child[slot]:
            continue
        if _replacement_ok(child, slot, candidate, budget):
            child[slot] = candidate
            return child
    return child


def _repair(
    rng: random.Random,
    build: Dict[str, Any],
    index: PoolIndex,
    shares: Dict[str, float],
    budget: float,
) -> Optional[Dict[str, Any]]:
    child = copy_build(build)
    for _pass in range(2):
        issues = set(diagnose(child))
        if not issues and _within_budget(child, budget):
            return child
        if 'socket' in issues or 'form_factor' in issues:
            boards = index.mb_by_socket.get(socket_of(child['cpu'])) or []
            motherboard = _pick(rng, boards, shares['motherboard'])
            if motherboard is not None:
                child['motherboard'] = motherboard
            rank = form_factor_rank(specs_of(child['motherboard']).get('form_factor'))
            cases = index.cases_for_rank.get(rank or 0) or []
            case = _pick(rng, cases, shares['case'])
            if case is not None:
                child['case'] = case
        if 'ram' in issues:
            allowed = DDR_BY_SOCKET.get(socket_of(child['cpu']))
            ram_pool = []
            if allowed:
                for gen in allowed:
                    ram_pool.extend(index.ram_by_gen.get(gen) or [])
            else:
                ram_pool = list(index.pools['memory'])
            ram_pool = [memory for memory in ram_pool if _ram_fits(memory, child['motherboard'])]
            memory = _pick(rng, ram_pool, shares['memory'])
            if memory is not None:
                child['memory'] = memory
        if 'gpu_size' in issues:
            max_gpu, _rad = case_clearance(child['case'])
            gpus = [gpu for gpu in index.pools['video-card'] if gpu_length_mm(gpu) <= max_gpu]
            gpu = _pick(rng, gpus, shares['video-card'])
            if gpu is not None:
                child['video-card'] = gpu
        if 'power' in issues:
            need = power_need(child)
            psus = [psu for psu in index.pools['power-supply'] if psu_watts(psu) >= need]
            psu = _pick(rng, psus, shares['power-supply'])
            if psu is not None:
                child['power-supply'] = psu
        if 'cooler' in issues:
            coolers = [
                cooler for cooler in index.pools['cpu-cooler']
                if _cooler_fits(cooler, child['case'], child['cpu'])
            ]
            cooler = _pick(rng, coolers, shares['cpu-cooler'])
            if cooler is not None:
                child['cpu-cooler'] = cooler
    if is_compatible(child) and _within_budget(child, budget):
        return child
    return None


def _quality_cache(pools: Dict[str, Sequence[Any]], shares: Dict[str, float], use_case: str) -> Dict[tuple, float]:
    del shares
    cache = {}
    for slot in BUILD_SLOTS:
        for product in pools[slot]:
            cache[(id(product), slot)] = _annotate_quality(product, use_case)
    return cache


def fitness(
    build: Dict[str, Any],
    budget: float,
    priorities: Dict[str, dict],
    quality: Dict[tuple, float],
) -> float:
    if not is_compatible(build):
        return 0.0
    shares = _shares(budget, priorities)
    weighted = 0.0
    weight_sum = 0.0
    for slot in BUILD_SLOTS:
        score = max(float(priorities[slot]['score']), 8.0)
        weight = score ** 2
        raw = quality.get((id(build[slot]), slot), 0.0)
        price = int(getattr(build[slot], 'price', 0) or 0)
        share = shares[slot]
        price_fit = 1.0
        if share > 0 and price > share * 1.65:
            price_fit = (share * 1.65) / price
        elif share > 0 and score >= 60 and price < share * 0.35:
            price_fit = 0.45 + 0.55 * (price / (share * 0.35))
        weighted += weight * (min(raw, 100.0) / 100.0) * price_fit
        weight_sum += weight
    quality_score = weighted / weight_sum if weight_sum else 0.0
    ratio = total_price(build) / float(budget) if budget else 1.0
    if ratio > 1:
        price_score = max(0.0, 1.0 - (ratio - 1.0) * 6.0)
    elif ratio < 0.62:
        price_score = (ratio / 0.62) * 0.75
    else:
        price_score = max(0.55, min(1.0, 1.0 - abs(0.97 - ratio) / 0.5))
    return round(100.0 * (0.8 * quality_score + 0.2 * price_score), 4)


def _signature(build: Dict[str, Any]) -> tuple:
    return tuple(getattr(build[slot], 'product_name', id(build[slot])) for slot in BUILD_SLOTS)


def _prepare_pools(
    raw: Dict[str, Sequence[Any]],
    budget: float,
    use_case: str,
) -> Dict[str, List[Any]]:
    prepared = {}
    for slot in BUILD_SLOTS:
        usable = [product for product in raw.get(slot) or [] if _usable(slot, product)]
        capped = _apply_price_cap(slot, usable, budget)
        prepared[slot] = _diverse_quality_pool(capped, use_case)
    return prepared


def _load_db_pools() -> Optional[Dict[str, List[Any]]]:
    from store.models import Product

    buckets = {slot: [] for slot in BUILD_SLOTS}
    queryset = Product.objects.filter(
        is_available=True,
        stock__gt=0,
        price__gt=0,
    ).select_related('category')
    for product in queryset:
        slot = _part_slug(product)
        if slot in buckets:
            buckets[slot].append(product)
    if all(buckets[slot] for slot in BUILD_SLOTS):
        return buckets
    return None


def _load_csv_pools() -> Dict[str, List[Any]]:
    global _CSV_POOLS
    if _CSV_POOLS is not None:
        return _CSV_POOLS
    with _CSV_LOCK:
        if _CSV_POOLS is None:
            from store.catalog_concurrent import _query_csv

            buckets = {slot: [] for slot in BUILD_SLOTS}
            payload = _query_csv(None, None)
            for product in payload.get('products') or []:
                slot = getattr(product, 'category_slug', '')
                if slot in buckets and product.price and product.is_available:
                    buckets[slot].append(product)
            _CSV_POOLS = buckets
        return _CSV_POOLS


def load_catalog() -> tuple:
    database = _load_db_pools()
    if database is not None:
        return database, 'db'
    return _load_csv_pools(), 'csv'


def _empty_result(priorities: Dict[str, dict], message: str, source: str) -> dict:
    return {
        'builds': [],
        'priorities': priority_rows(priorities),
        'notice': message,
        'debug': {
            'engine': 'mamdani+genetic',
            'seleccion': 'ruleta',
            'origen_pool': source,
            'prioridades': priority_rows(priorities),
            'notice': message,
            'builds': [],
        },
    }


def _present(build: Dict[str, Any], rank: int, score: float, priorities: Dict[str, dict]) -> dict:
    parts = []
    for slot in BUILD_SLOTS:
        product = build[slot]
        parts.append({
            'slot': slot,
            'label': SLOT_LABELS[slot],
            'product': product,
            'priority': priorities[slot]['label'],
            'priority_score': priorities[slot]['score'],
        })
    return {
        'rank': rank,
        'fitness': round(score, 2),
        'total_price': total_price(build),
        'summary': compatibility_summary(build),
        'parts': parts,
    }


def recommend_builds(
    budget: float,
    use_case: str,
    pools: Optional[Dict[str, Sequence[Any]]] = None,
    *,
    selection: str = 'ruleta',
    population_size: int = POPULATION_SIZE,
    generations: int = GENERATIONS,
    seed: Optional[int] = None,
) -> dict:
    budget = float(budget or 0) or 15000.0
    priorities = infer_priorities(budget, use_case)
    if seed is None:
        seed = zlib.adler32(f'{use_case}:{int(budget)}:{selection}'.encode('utf-8'))
    rng = random.Random(seed)
    source = 'provided'
    if pools is None:
        pools, source = load_catalog()
    prepared = _prepare_pools(pools, budget, use_case)
    index = PoolIndex(prepared)
    if not index.ready():
        return _empty_result(
            priorities,
            'No hay suficientes componentes con precio para armar una PC con ese presupuesto.',
            source,
        )

    shares = _shares(budget, priorities)
    population: List[Dict[str, Any]] = []
    attempts = 0
    while len(population) < population_size and attempts < population_size * 6:
        attempts += 1
        individual = random_compatible(rng, index, shares, budget)
        if individual is not None:
            population.append(individual)
    if not population:
        return _empty_result(
            priorities,
            'No encontramos una configuración compatible (socket, energía y tamaño) para ese presupuesto.',
            source,
        )
    while len(population) < population_size:
        population.append(copy_build(rng.choice(population)))

    quality = _quality_cache(prepared, shares, use_case)
    select = tournament_select if selection == 'torneo' else roulette_select
    history = []

    for _generation in range(generations):
        scored = [
            (fitness(individual, budget, priorities, quality), individual)
            for individual in population
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        history.append(round(scored[0][0], 2))
        next_population = [copy_build(item[1]) for item in scored[:ELITE_COUNT]]
        while len(next_population) < population_size:
            parent_a = select(rng, scored)
            parent_b = select(rng, scored)
            child = crossover(rng, parent_a, parent_b)
            if not is_compatible(child) or not _within_budget(child, budget):
                child = _repair(rng, child, index, shares, budget) or parent_a
            child = mutate(rng, child, index, budget)
            if not is_compatible(child):
                child = parent_a
            next_population.append(child)
        population = next_population

    scored = [
        (fitness(individual, budget, priorities, quality), individual)
        for individual in population
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    unique = []
    seen = set()
    for score, individual in scored:
        if score <= 0 or not is_compatible(individual):
            continue
        key = _signature(individual)
        if key in seen:
            continue
        seen.add(key)
        unique.append((score, individual))
    unique.sort(key=lambda item: (total_price(item[1]) <= budget, item[0]), reverse=True)
    under_budget = [item for item in unique if total_price(item[1]) <= budget]
    chosen = (under_budget or unique)[:3]
    builds = [
        _present(individual, rank, score, priorities)
        for rank, (score, individual) in enumerate(chosen, start=1)
    ]
    debug_builds = [
        {
            'rank': build['rank'],
            'aptitud': build['fitness'],
            'total_mxn': build['total_price'],
            'resumen': build['summary'],
            'piezas': [
                {
                    'pieza': part['label'],
                    'nombre': part['product'].product_name,
                    'precio_mxn': int(part['product'].price or 0),
                    'prioridad': part['priority'],
                }
                for part in build['parts']
            ],
        }
        for build in builds
    ]
    return {
        'builds': builds,
        'priorities': priority_rows(priorities),
        'notice': '' if builds else 'No encontramos una configuración compatible para ese presupuesto.',
        'debug': {
            'engine': 'mamdani+genetic',
            'defuzzificacion': 'centroide',
            'seleccion': 'torneo' if selection == 'torneo' else 'ruleta',
            'cruce': 'uniforme por componente',
            'mutacion': 'reemplazo por componente compatible',
            'filtro': 'socket, TDP/fuente/cooler y tamaño (placa, GPU, radiador) antes de la aptitud',
            'origen_pool': source,
            'poblacion': population_size,
            'generaciones': generations,
            'historial_mejor_aptitud': history,
            'prioridades': priority_rows(priorities),
            'builds': debug_builds,
            'procedimiento': [
                '1. Difuminar presupuesto y caso de uso.',
                '2. Inferencia Mamdani: reglas if-then y centroide -> prioridad de cada pieza.',
                '3. Armar cromosomas (CPU, GPU, RAM, motherboard, almacenamiento, fuente, gabinete, cooler).',
                '4. Filtrar incompatibles (socket, energia, tamaño) antes de evaluar.',
                '5. Seleccion por ruleta, cruce de componentes y mutacion compatible.',
                '6. Devolver hasta 3 configuraciones distintas, priorizando las que caben en el presupuesto.',
            ],
        },
    }
