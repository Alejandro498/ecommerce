"""
Segundo Mamdani: que tan adecuada es una pieza concreta para el uso.

La primera inferencia (assistant/mamdani.py) reparte prioridades y presupuesto.
Esta evalua el modelo (VRAM, nucleos, DDR, watts, etc.) y devuelve 0-100
por centroide. El genetico la usa como calidad de cada gen.
"""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

from assistant.compatibility import specs_of, to_float
from assistant.fuzzy import trapmf, trimf
from assistant.mamdani import _defuzzify

Fired = Tuple[float, str]


def _slug(product: Any) -> str:
    part = getattr(product, 'part_type', None) or ''
    if part:
        return part
    category = getattr(product, 'category', None)
    return getattr(category, 'slug', getattr(product, 'category_slug', '')) or ''


def _name(product: Any) -> str:
    return str(getattr(product, 'product_name', '') or '').lower()


def _and(*values: float) -> float:
    if not values:
        return 0.0
    return min(values)


def _clip(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return float(value)


def _gpu_class(product: Any, specs: dict) -> str:
    text = f"{_name(product)} {specs.get('chipset', '')} {specs.get('gpu_brand', '')}".lower()
    if any(token in text for token in ('quadro', 'workstation', 'radeon pro', 'rtx a')):
        return 'trabajo'
    if 'rtx' in text:
        return 'alto'
    if any(token in text for token in ('gtx', 'radeon', 'rx ')):
        return 'medio'
    return 'bajo'


def _gpu_rules(product: Any, specs: dict, use_case: str) -> List[Fired]:
    vram = to_float(specs.get('memory')) or 0.0
    vram_baja = trapmf(vram, -1, 0, 4, 8)
    vram_media = trimf(vram, 6, 10, 14)
    vram_alta = trapmf(vram, 12, 16, 64, 65)
    clase = _gpu_class(product, specs)
    alto = 1.0 if clase == 'alto' else 0.0
    medio = 1.0 if clase == 'medio' else 0.0
    bajo = 1.0 if clase == 'bajo' else 0.0
    trabajo = 1.0 if clase == 'trabajo' else 0.0
    vram_util = max(vram_media, vram_alta)

    if use_case == 'estudio':
        return [
            (_and(vram_baja, max(bajo, medio, 0.35)), 'alta'),
            (_and(bajo, vram_baja), 'muy_alta'),
            (_and(alto, vram_util), 'baja'),
            (vram_alta, 'muy_baja'),
        ]
    if use_case == 'trabajo':
        return [
            (_and(trabajo, vram_util), 'muy_alta'),
            (_and(alto, vram_util), 'alta'),
            (_and(medio, vram_media), 'media'),
            (bajo, 'baja'),
            (_and(trabajo, vram_baja), 'media'),
        ]
    if use_case == 'streaming':
        return [
            (_and(alto, vram_util), 'muy_alta'),
            (_and(medio, vram_util), 'alta'),
            (bajo, 'baja'),
            (trabajo, 'media'),
        ]
    return [
        (_and(alto, vram_util, 1.0 - trabajo), 'muy_alta'),
        (_and(medio, vram_util, 1.0 - trabajo), 'alta'),
        (_and(medio, vram_baja, 1.0 - trabajo), 'media'),
        (_and(bajo, 1.0 - trabajo), 'baja'),
        (trabajo, 'baja'),
    ]


def _cpu_rules(product: Any, specs: dict, use_case: str) -> List[Fired]:
    name = _name(product)
    cores = to_float(specs.get('core_count')) or to_float(specs.get('cores')) or 0.0
    tdp = to_float(specs.get('tdp')) or 0.0
    boost = to_float(specs.get('boost_clock')) or 0.0
    cores_bajos = trapmf(cores, -1, 0, 4, 6)
    cores_medios = trimf(cores, 4, 8, 12)
    cores_altos = trapmf(cores, 10, 16, 64, 65)
    tdp_bajo = trapmf(tdp, -1, 0, 45, 75) if tdp else 0.0
    boost_alto = trapmf(boost, 4.0, 5.0, 7.0, 7.1) if boost else 0.0
    x3d = 1.0 if 'x3d' in name else 0.0
    prod = 1.0 if any(token in name for token in ('i7', 'i9', 'ryzen 7', 'ryzen 9')) else 0.0

    if use_case == 'trabajo':
        return [
            (_and(cores_altos, max(prod, 0.6)), 'muy_alta'),
            (_and(cores_medios, prod), 'alta'),
            (cores_medios, 'media'),
            (cores_bajos, 'baja'),
        ]
    if use_case == 'estudio':
        return [
            (_and(cores_medios, max(tdp_bajo, 0.5)), 'alta'),
            (_and(cores_bajos, tdp_bajo), 'media'),
            (cores_altos, 'baja'),
            (cores_bajos, 'baja'),
        ]
    if use_case == 'streaming':
        return [
            (cores_altos, 'muy_alta'),
            (_and(cores_medios, prod), 'alta'),
            (cores_medios, 'media'),
            (cores_bajos, 'muy_baja'),
        ]
    return [
        (_and(x3d, max(cores_medios, cores_altos)), 'muy_alta'),
        (_and(cores_medios, max(boost_alto, 0.55)), 'alta'),
        (_and(cores_altos, max(boost_alto, 0.5)), 'alta'),
        (cores_bajos, 'baja'),
    ]


def _ram_rules(specs: dict, use_case: str) -> List[Fired]:
    speed = specs.get('speed')
    generation = None
    if isinstance(speed, (list, tuple)) and speed:
        head = to_float(speed[0])
        if head is not None and 2 <= head <= 5:
            generation = int(head)
    count = to_float(specs.get('module_count')) or 1.0
    capacity = to_float(specs.get('module_capacity_gb')) or 0.0
    gb = count * capacity
    gb_baja = trapmf(gb, -1, 0, 8, 12)
    gb_media = trimf(gb, 8, 16, 24)
    gb_alta = trapmf(gb, 24, 32, 256, 257)
    ddr5 = 1.0 if generation == 5 else 0.0

    if use_case == 'estudio':
        return [
            (gb_media, 'muy_alta'),
            (gb_baja, 'baja'),
            (gb_alta, 'media'),
        ]
    return [
        (gb_alta, 'muy_alta'),
        (_and(gb_media, max(ddr5, 0.7)), 'alta'),
        (gb_media, 'media'),
        (gb_baja, 'baja'),
        (_and(ddr5, gb_alta), 'muy_alta'),
    ]


def _storage_rules(specs: dict, use_case: str) -> List[Fired]:
    kind = str(specs.get('type') or '').lower()
    interface = str(specs.get('interface') or '').lower()
    form = str(specs.get('form_factor') or '').lower()
    capacity = to_float(specs.get('capacity')) or 0.0
    nvme = 1.0 if ('nvme' in interface or 'pcie' in interface or 'nvme' in kind) else 0.0
    ssd = 1.0 if (nvme or 'ssd' in kind or 'm.2' in form) else 0.0
    hdd = 1.0 - ssd
    cap_alta = trapmf(capacity, 1500, 2000, 8000, 8001) if capacity else 0.0

    if use_case == 'estudio':
        return [
            (nvme, 'alta'),
            (_and(ssd, 1.0 - nvme), 'alta'),
            (hdd, 'baja'),
        ]
    if use_case == 'streaming':
        return [
            (_and(nvme, max(cap_alta, 0.4)), 'muy_alta'),
            (ssd, 'alta'),
            (hdd, 'muy_baja'),
        ]
    return [
        (_and(nvme, max(cap_alta, 0.45)), 'muy_alta'),
        (nvme, 'alta'),
        (_and(ssd, 1.0 - nvme), 'media'),
        (hdd, 'muy_baja'),
    ]


def _psu_rules(specs: dict, use_case: str) -> List[Fired]:
    wattage = to_float(specs.get('wattage')) or 0.0
    efficiency = str(specs.get('efficiency') or '').lower()
    target = {'estudio': 500.0, 'gaming': 650.0, 'trabajo': 650.0, 'streaming': 750.0}.get(use_case, 650.0)
    ratio = wattage / target if target else 0.0
    baja = trapmf(ratio, -0.1, 0, 0.6, 0.85)
    ok = trimf(ratio, 0.75, 1.05, 1.45)
    alta = trapmf(ratio, 1.25, 1.6, 4, 4.1)
    gold = 1.0 if any(token in efficiency for token in ('gold', 'platinum', 'titanium')) else 0.0
    return [
        (_and(ok, gold), 'muy_alta'),
        (ok, 'alta'),
        (alta, 'media'),
        (baja, 'baja'),
    ]


def _board_rules(product: Any, specs: dict, use_case: str) -> List[Fired]:
    name = _name(product)
    form = str(specs.get('form_factor') or '').lower()
    max_memory = to_float(specs.get('max_memory')) or 0.0
    gaming = 1.0 if any(
        token in name for token in ('b550', 'b650', 'b660', 'b760', 'x570', 'x670', 'z690', 'z790', 'gaming')
    ) else 0.0
    micro = 1.0 if 'micro' in form or 'mini' in form else 0.0
    mem_alta = trapmf(max_memory, 64, 128, 512, 513) if max_memory else 0.0
    if use_case == 'estudio':
        return [
            (micro, 'alta'),
            (1.0 - micro, 'media'),
            (mem_alta, 'baja'),
        ]
    if use_case == 'gaming':
        return [
            (_and(gaming, max(mem_alta, 0.4)), 'muy_alta'),
            (gaming, 'alta'),
            (1.0 - gaming, 'baja'),
        ]
    return [
        (_and(gaming, mem_alta), 'alta'),
        (mem_alta, 'media'),
        (1.0 - gaming, 'media'),
    ]


def _case_rules(product: Any, specs: dict, use_case: str) -> List[Fired]:
    name = _name(product)
    side = str(specs.get('side_panel') or '').lower()
    volume = to_float(specs.get('external_volume')) or 0.0
    airflow = 1.0 if ('airflow' in name or 'mesh' in name or 'mesh' in side) else 0.0
    compacto = trapmf(volume, -1, 0, 30, 45) if volume else 0.0
    if use_case == 'estudio':
        return [
            (compacto if volume else micro_hint(specs), 'alta'),
            (1.0 - (compacto if volume else 0.0), 'media'),
        ]
    if use_case in ('gaming', 'streaming'):
        return [
            (airflow, 'muy_alta'),
            (1.0 - airflow, 'baja'),
        ]
    return [
        (airflow, 'alta'),
        (1.0 - airflow, 'media'),
    ]


def micro_hint(specs: dict) -> float:
    kind = str(specs.get('type') or '').lower()
    if any(token in kind for token in ('mini', 'htpc', 'slim', 'desktop')):
        return 1.0
    return 0.0


def _cooler_rules(specs: dict, use_case: str) -> List[Fired]:
    radiator = to_float(specs.get('radiator_size')) or 0.0
    kind = str(specs.get('cooler_type') or '').lower()
    air = 1.0 if 'air' in kind and radiator < 120 else 0.0
    grande = trapmf(radiator, 180, 240, 480, 481) if radiator else 0.0
    if use_case == 'estudio':
        return [
            (max(air, 1.0 - grande), 'alta'),
            (grande, 'baja'),
        ]
    if use_case in ('gaming', 'streaming'):
        return [
            (grande, 'muy_alta'),
            (air, 'media'),
            (_clip(1.0 - grande - air), 'baja'),
        ]
    return [
        (grande, 'alta'),
        (air, 'media'),
    ]


def _rules_for(product: Any, use_case: str) -> Sequence[Fired]:
    specs = specs_of(product)
    slug = _slug(product)
    selected = use_case if use_case in ('gaming', 'trabajo', 'estudio', 'streaming') else 'gaming'
    if slug == 'video-card':
        return _gpu_rules(product, specs, selected)
    if slug == 'cpu':
        return _cpu_rules(product, specs, selected)
    if slug == 'memory':
        return _ram_rules(specs, selected)
    if slug == 'internal-hard-drive':
        return _storage_rules(specs, selected)
    if slug == 'power-supply':
        return _psu_rules(specs, selected)
    if slug == 'motherboard':
        return _board_rules(product, specs, selected)
    if slug == 'case':
        return _case_rules(product, specs, selected)
    if slug == 'cpu-cooler':
        return _cooler_rules(specs, selected)
    return [(0.2, 'media')]


def component_quality(product: Any, use_case: str) -> float:
    """Adecuacion 0-100 de una pieza para el uso. Defuzzificacion por centroide."""
    fired = [( _clip(strength), term) for strength, term in _rules_for(product, use_case)]
    return round(_defuzzify(fired), 2)
