"""
Filtro fuerte de compatibilidad física, previo a la evaluación del genético.

Comprueba socket (CPU, placa y generación de RAM), energía (TDP de CPU +
GPU estimada contra la fuente y el cooler) y tamaño (formato de placa,
largo de GPU y radiador dentro del gabinete).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

BUILD_SLOTS = (
    'cpu',
    'video-card',
    'memory',
    'motherboard',
    'internal-hard-drive',
    'power-supply',
    'case',
    'cpu-cooler',
)

SLOT_LABELS = {
    'cpu': 'CPU',
    'video-card': 'GPU',
    'memory': 'RAM',
    'motherboard': 'Motherboard',
    'internal-hard-drive': 'Almacenamiento',
    'power-supply': 'Fuente',
    'case': 'Gabinete',
    'cpu-cooler': 'Cooler',
}

# Generaciones de DDR que acepta cada socket. LGA1700 sale en placas DDR4 y DDR5.
DDR_BY_SOCKET = {
    'AM5': {5},
    'LGA1851': {5},
    'STR5': {5},
    'LGA1700': {4, 5},
    'AM4': {4},
    'LGA1200': {4},
    'LGA1151': {4},
    'LGA2066': {4},
    'LGA2011-3': {4},
    'LGA2011': {4},
    'TR4': {4},
    'STRX4': {4},
    'LGA1150': {3},
    'LGA1155': {3},
    'LGA1156': {3},
    'AM3': {3},
    'AM3+': {3},
    'FM2': {3},
    'FM2+': {3},
    'LGA775': {2, 3},
}

SYSTEM_OVERHEAD_W = 100

_GPU_TDP_RULES = (
    (r'4090', 450),
    (r'4080', 320),
    (r'4070\s*ti', 285),
    (r'4070', 200),
    (r'4060\s*ti', 165),
    (r'4060', 115),
    (r'3090', 350),
    (r'3080', 320),
    (r'3070', 220),
    (r'3060', 170),
    (r'3050', 130),
    (r'2080', 215),
    (r'2070', 175),
    (r'2060', 160),
    (r'1660', 120),
    (r'1650', 75),
    (r'7900\s*xtx', 355),
    (r'7900', 315),
    (r'7800', 263),
    (r'7700', 245),
    (r'7600', 165),
    (r'6900', 300),
    (r'6800', 250),
    (r'6700', 230),
    (r'6600', 160),
    (r'6500', 107),
    (r'5700', 180),
    (r'quadro|rtx\s*a\d', 140),
)


def specs_of(product: Any) -> Dict[str, Any]:
    if hasattr(product, 'get_specs_dict'):
        specs = product.get_specs_dict()
        if isinstance(specs, dict):
            return specs
    specs = getattr(product, 'specs', {}) or {}
    return specs if isinstance(specs, dict) else {}


def to_float(value: Any) -> Optional[float]:
    if value is None or value == '' or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)):
        return None
    text = str(value).strip().replace(',', '')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def norm_socket(value: Any) -> str:
    return re.sub(r'\s+', '', str(value or '').upper())


def socket_of(product: Any) -> str:
    return norm_socket(specs_of(product).get('socket'))


def form_factor_rank(value: Any) -> Optional[int]:
    text = re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()
    if not text:
        return None
    if any(token in text for token in ('xl atx', 'ssi eeb', 'hptx')):
        return 5
    if any(token in text for token in ('eatx', 'e atx', 'ssi ceb')):
        return 4
    if any(token in text for token in ('thin mini', 'mini itx', 'mini dtx')):
        return 1
    if 'micro' in text or 'flex' in text:
        return 2
    if text == 'atx' or text.endswith(' atx'):
        return 3
    return None


def form_factor_name(value: Any) -> str:
    rank = form_factor_rank(value)
    return {
        1: 'Mini ITX',
        2: 'Micro ATX',
        3: 'ATX',
        4: 'EATX',
        5: 'XL ATX',
    }.get(rank, str(value or 'desconocido'))


def ram_profile(product: Any) -> Tuple[Optional[int], int, float]:
    specs = specs_of(product)
    speed = specs.get('speed')
    generation = None
    if isinstance(speed, (list, tuple)) and speed:
        head = to_float(speed[0])
        if head is not None and 2 <= head <= 5:
            generation = int(head)
    else:
        text = str(speed or '')
        matched = re.search(r'(?:ddr\s*)?([2-5])(?:\s*,|\s*-\s*\d)', text, re.I)
        if matched:
            generation = int(matched.group(1))
    modules = to_float(specs.get('module_count')) or 1.0
    capacity = to_float(specs.get('module_capacity_gb')) or 0.0
    return generation, int(modules), modules * capacity


def cpu_tdp(product: Any) -> float:
    value = to_float(specs_of(product).get('tdp'))
    if value is None or value <= 0:
        return 95.0
    return value


def gpu_tdp(product: Any) -> float:
    cached = getattr(product, '_gpu_tdp', None)
    if cached is not None:
        return cached
    specs = specs_of(product)
    text = f"{getattr(product, 'product_name', '')} {specs.get('chipset', '')}".lower()
    estimated = 150.0
    for pattern, watts in _GPU_TDP_RULES:
        if re.search(pattern, text):
            estimated = float(watts)
            break
    else:
        if 'rtx' in text:
            estimated = 200.0
        elif any(token in text for token in ('gtx', 'radeon', 'rx ')):
            estimated = 150.0
        else:
            estimated = 120.0
    try:
        setattr(product, '_gpu_tdp', estimated)
    except AttributeError:
        pass
    return estimated


def gpu_length_mm(product: Any) -> float:
    length = to_float(specs_of(product).get('length'))
    if length is None or length <= 0:
        return 250.0
    return length


def psu_watts(product: Any) -> float:
    return to_float(specs_of(product).get('wattage')) or 0.0


def case_clearance(product: Any) -> Tuple[float, float]:
    specs = specs_of(product)
    kind = f"{specs.get('type', '')} {getattr(product, 'product_name', '')}".lower()
    if any(token in kind for token in ('htpc', 'slim', 'desktop')):
        return 205.0, 0.0
    if 'full tower' in kind or 'test bench' in kind:
        return 430.0, 420.0
    if 'mid tower' in kind:
        return 370.0, 360.0
    if 'mini tower' in kind or 'mini itx tower' in kind:
        return 280.0, 240.0
    return 330.0, 280.0


def case_max_rank(product: Any) -> Optional[int]:
    return form_factor_rank(specs_of(product).get('max_motherboard_form_factor'))


def cooler_limits(product: Any) -> Tuple[float, float]:
    """Devuelve (capacidad TDP en W, radiador en mm). El aire usa radiador 0."""
    specs = specs_of(product)
    kind = str(specs.get('cooler_type') or '').lower()
    radiator = to_float(specs.get('radiator_size')) or 0.0
    if 'aio' in kind or radiator >= 120:
        if radiator <= 0:
            radiator = 240.0
        if radiator >= 360:
            return 320.0, radiator
        if radiator >= 240:
            return 250.0, radiator
        if radiator >= 140:
            return 180.0, radiator
        return 150.0, radiator
    return 200.0, 0.0


def power_need(build: Dict[str, Any]) -> float:
    cpu = build.get('cpu')
    gpu = build.get('video-card')
    if cpu is None or gpu is None:
        return 0.0
    return cpu_tdp(cpu) + gpu_tdp(gpu) + SYSTEM_OVERHEAD_W


def diagnose(build: Dict[str, Any]) -> List[str]:
    """Códigos de incompatibilidad. Lista vacía significa que la build pasa el filtro."""
    issues: List[str] = []
    for slot in BUILD_SLOTS:
        if build.get(slot) is None:
            issues.append('missing')
            return issues

    cpu = build['cpu']
    motherboard = build['motherboard']
    memory = build['memory']
    gpu = build['video-card']
    psu = build['power-supply']
    case = build['case']
    cooler = build['cpu-cooler']

    cpu_socket = socket_of(cpu)
    board_socket = socket_of(motherboard)
    if not cpu_socket or not board_socket or cpu_socket != board_socket:
        issues.append('socket')

    board_rank = form_factor_rank(specs_of(motherboard).get('form_factor'))
    case_rank = case_max_rank(case)
    if board_rank is None or case_rank is None or board_rank > case_rank:
        issues.append('form_factor')

    generation, modules, total_gb = ram_profile(memory)
    allowed = DDR_BY_SOCKET.get(cpu_socket) if cpu_socket else None
    board_specs = specs_of(motherboard)
    slot_count = to_float(board_specs.get('memory_slots'))
    max_memory = to_float(board_specs.get('max_memory'))
    if generation is None or total_gb <= 0:
        issues.append('ram')
    elif allowed is not None and generation not in allowed:
        issues.append('ram')
    elif slot_count is not None and modules > slot_count:
        issues.append('ram')
    elif max_memory is not None and total_gb > max_memory:
        issues.append('ram')

    max_gpu, max_radiator = case_clearance(case)
    if gpu_length_mm(gpu) > max_gpu:
        issues.append('gpu_size')

    cooler_watts, radiator = cooler_limits(cooler)
    if radiator > max_radiator or cooler_watts < cpu_tdp(cpu):
        issues.append('cooler')

    if psu_watts(psu) < power_need(build):
        issues.append('power')

    return issues


def is_compatible(build: Dict[str, Any]) -> bool:
    return not diagnose(build)


def compatibility_summary(build: Dict[str, Any]) -> str:
    cpu = build.get('cpu')
    motherboard = build.get('motherboard')
    case = build.get('case')
    gpu = build.get('video-card')
    psu = build.get('power-supply')
    if not all((cpu, motherboard, case, gpu, psu)):
        return 'Configuración incompleta'
    socket = socket_of(cpu) or 'sin socket'
    board_name = form_factor_name(specs_of(motherboard).get('form_factor'))
    case_name = form_factor_name(specs_of(case).get('max_motherboard_form_factor'))
    need = power_need(build)
    watts = psu_watts(psu)
    length = gpu_length_mm(gpu)
    return (
        f'Socket {socket} · placa {board_name} en gabinete hasta {case_name} · '
        f'fuente {watts:.0f}W cubre ~{need:.0f}W · GPU {length:.0f} mm'
    )
