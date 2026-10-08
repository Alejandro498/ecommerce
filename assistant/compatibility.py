"""
Filtro fuerte de compatibilidad fisica, previo a la evaluacion del genetico.

Comprueba socket, generacion de RAM, formato de placa, largo de GPU,
radiador/altura de cooler, watts de fuente (con margen), dual-channel,
plataformas demasiado antiguas segun preferencias, y almacenamiento
adecuado al rendimiento pedido.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from assistant.preferences import normalize_prefs

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

# Sockets demasiado viejos para builds modernas / principiantes.
LEGACY_SOCKETS = {
    'LGA775', 'LGA1150', 'LGA1155', 'LGA1156', 'AM3', 'AM3+', 'FM2', 'FM2+',
    'LGA2011', 'LGA2011-3',
}

MODERN_SOCKETS = {'AM4', 'AM5', 'LGA1200', 'LGA1700', 'LGA1851'}

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


def cpu_brand(product: Any) -> str:
    specs = specs_of(product)
    brand = str(specs.get('brand') or '').strip().lower()
    name = str(getattr(product, 'product_name', '') or '').lower()
    if brand in ('amd', 'intel'):
        return brand
    if 'amd' in name or 'ryzen' in name:
        return 'amd'
    if 'intel' in name or 'core i' in name or 'celeron' in name or 'pentium' in name:
        return 'intel'
    return ''


def gpu_brand(product: Any) -> str:
    """Marca de GPU: nvidia | amd | '' si no se puede inferir."""
    specs = specs_of(product)
    brand = str(specs.get('gpu_brand') or specs.get('brand') or '').strip().lower()
    chipset = str(specs.get('chipset') or '').lower()
    name = str(getattr(product, 'product_name', '') or '').lower()
    haystack = f'{brand} {chipset} {name}'
    if brand in ('nvidia', 'amd'):
        return brand
    if any(token in haystack for token in ('nvidia', 'geforce', 'rtx', 'gtx', 'quadro')):
        return 'nvidia'
    if any(token in haystack for token in ('radeon', 'rx ', 'rx-', 'vega')):
        return 'amd'
    if 'amd' in haystack and any(token in haystack for token in ('gpu', 'graphics', 'video')):
        return 'amd'
    return ''


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


def psu_is_sfx(product: Any) -> bool:
    text = f"{specs_of(product).get('type', '')} {getattr(product, 'product_name', '')}".lower()
    return 'sfx' in text


def case_clearance(product: Any) -> Tuple[float, float, float]:
    """GPU mm, radiador mm, altura cooler aire mm."""
    specs = specs_of(product)
    kind = f"{specs.get('type', '')} {getattr(product, 'product_name', '')}".lower()
    if any(token in kind for token in ('htpc', 'slim', 'desktop')):
        return 205.0, 0.0, 65.0
    if 'full tower' in kind or 'test bench' in kind:
        return 430.0, 420.0, 180.0
    if 'mid tower' in kind:
        return 370.0, 360.0, 165.0
    if 'mini tower' in kind or 'mini itx tower' in kind:
        return 280.0, 240.0, 150.0
    return 330.0, 280.0, 160.0


def case_max_rank(product: Any) -> Optional[int]:
    return form_factor_rank(specs_of(product).get('max_motherboard_form_factor'))


def cooler_limits(product: Any) -> Tuple[float, float, float]:
    """(capacidad TDP W, radiador mm, altura aire mm). AIO usa altura 0."""
    specs = specs_of(product)
    kind = str(specs.get('cooler_type') or '').lower()
    radiator = to_float(specs.get('radiator_size')) or 0.0
    if 'aio' in kind or radiator >= 120:
        if radiator <= 0:
            radiator = 240.0
        if radiator >= 360:
            return 320.0, radiator, 0.0
        if radiator >= 240:
            return 250.0, radiator, 0.0
        if radiator >= 140:
            return 180.0, radiator, 0.0
        return 150.0, radiator, 0.0
    # Aire: altura tipica segun nombre
    name = str(getattr(product, 'product_name', '') or '').lower()
    if any(token in name for token in ('low profile', 'slim', 'low-profile')):
        height = 50.0
        watts = 95.0
    elif any(token in name for token in ('dual', 'tower', 'peerless', 'dark rock', 'nh-d')):
        height = 160.0
        watts = 210.0
    else:
        height = 155.0
        watts = 180.0
    return watts, 0.0, height


def storage_is_ssd(product: Any) -> bool:
    specs = specs_of(product)
    kind = str(specs.get('type') or '').lower()
    interface = str(specs.get('interface') or '').lower()
    form = str(specs.get('form_factor') or '').lower()
    if 'hdd' in kind and 'ssd' not in kind:
        return False
    return any(token in kind or token in interface or token in form for token in (
        'ssd', 'nvme', 'm.2', 'pcie',
    ))


def power_need(build: Dict[str, Any], prefs: Optional[Dict[str, str]] = None) -> float:
    cpu = build.get('cpu')
    gpu = build.get('video-card')
    if cpu is None or gpu is None:
        return 0.0
    base = cpu_tdp(cpu) + gpu_tdp(gpu) + SYSTEM_OVERHEAD_W
    prefs = normalize_prefs(prefs, use_case='gaming')
    # Principiante / alto rendimiento: mas margen en la fuente.
    if prefs['experience'] == 'principiante' or prefs['performance'] == 'alto':
        return base * 1.25
    if prefs['performance'] == 'medio':
        return base * 1.15
    return base * 1.10


def _needs_modern_platform(prefs: Dict[str, str]) -> bool:
    if prefs['experience'] == 'principiante':
        return True
    if prefs['performance'] in ('medio', 'alto'):
        return True
    if prefs['resolution'] in ('1440p', '4k'):
        return True
    return False


def diagnose(build: Dict[str, Any], prefs: Optional[Dict[str, str]] = None) -> List[str]:
    """Codigos de incompatibilidad. Lista vacia = la build pasa el filtro."""
    prefs = normalize_prefs(prefs, use_case='gaming')
    issues: List[str] = []
    for slot in BUILD_SLOTS:
        if build.get(slot) is None:
            issues.append('missing')
            return issues

    cpu = build['cpu']
    motherboard = build['motherboard']
    memory = build['memory']
    gpu = build['video-card']
    storage = build['internal-hard-drive']
    psu = build['power-supply']
    case = build['case']
    cooler = build['cpu-cooler']

    cpu_socket = socket_of(cpu)
    board_socket = socket_of(motherboard)
    if not cpu_socket or not board_socket or cpu_socket != board_socket:
        issues.append('socket')

    if prefs['brand'] in ('amd', 'intel'):
        brand = cpu_brand(cpu)
        if brand and brand != prefs['brand']:
            issues.append('brand')

    if prefs.get('gpu_brand') in ('nvidia', 'amd'):
        preferred_gpu = prefs['gpu_brand']
        detected_gpu = gpu_brand(gpu)
        if detected_gpu and detected_gpu != preferred_gpu:
            issues.append('gpu_brand')

    if _needs_modern_platform(prefs) and cpu_socket in LEGACY_SOCKETS:
        issues.append('legacy')

    board_rank = form_factor_rank(specs_of(motherboard).get('form_factor'))
    case_rank = case_max_rank(case)
    if board_rank is None or case_rank is None or board_rank > case_rank:
        issues.append('form_factor')

    # Mini ITX + fuente enorme ATX de torre suele ser problema en SFF.
    if board_rank == 1 and not psu_is_sfx(psu) and psu_watts(psu) >= 850:
        max_gpu, _rad, _air = case_clearance(case)
        if max_gpu <= 280:
            issues.append('psu_size')

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
    elif modules < 2 and prefs['performance'] in ('medio', 'alto'):
        # Dual channel: 1 modulo pierde rendimiento.
        issues.append('ram_channels')

    max_gpu, max_radiator, max_air = case_clearance(case)
    if gpu_length_mm(gpu) > max_gpu:
        issues.append('gpu_size')

    cooler_watts, radiator, air_height = cooler_limits(cooler)
    if radiator > max_radiator:
        issues.append('cooler')
    elif air_height > 0 and air_height > max_air:
        issues.append('cooler')
    elif cooler_watts < cpu_tdp(cpu):
        issues.append('cooler')

    if psu_watts(psu) < power_need(build, prefs):
        issues.append('power')

    # HDD mecanico no para gaming/streaming a alto rendimiento o 1440p+.
    if not storage_is_ssd(storage):
        if prefs['resolution'] in ('1440p', '4k') or prefs['performance'] == 'alto':
            issues.append('storage')
        elif prefs['experience'] == 'principiante' and prefs['resolution'] != 'office':
            issues.append('storage')

    return issues


def is_compatible(build: Dict[str, Any], prefs: Optional[Dict[str, str]] = None) -> bool:
    return not diagnose(build, prefs)


def compatibility_summary(build: Dict[str, Any], prefs: Optional[Dict[str, str]] = None) -> str:
    cpu = build.get('cpu')
    motherboard = build.get('motherboard')
    case = build.get('case')
    gpu = build.get('video-card')
    psu = build.get('power-supply')
    memory = build.get('memory')
    if not all((cpu, motherboard, case, gpu, psu, memory)):
        return 'Configuración incompleta'
    socket = socket_of(cpu) or 'sin socket'
    board_name = form_factor_name(specs_of(motherboard).get('form_factor'))
    case_name = form_factor_name(specs_of(case).get('max_motherboard_form_factor'))
    need = power_need(build, prefs)
    watts = psu_watts(psu)
    length = gpu_length_mm(gpu)
    generation, modules, total_gb = ram_profile(memory)
    ram_txt = f'{int(total_gb)} GB'
    if generation:
        ram_txt = f'DDR{generation} {ram_txt}'
    if modules:
        ram_txt += f' ({modules} mod.)'
    storage = build.get('internal-hard-drive')
    disk = 'SSD' if storage and storage_is_ssd(storage) else 'HDD'
    return (
        f'Socket {socket} · placa {board_name} en gabinete hasta {case_name} · '
        f'{ram_txt} · {disk} · fuente {watts:.0f}W cubre ~{need:.0f}W · GPU {length:.0f} mm'
    )
