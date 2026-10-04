"""
Score Sugeno de un componente suelto.

El armado de PCs ya no lo usa. La calidad de cada pieza sale del segundo
Mamdani en assistant/quality_mamdani.py. Este módulo sigue disponible para
el ranking de piezas sueltas de la primera fase.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Membership helpers
# ---------------------------------------------------------------------------

def _clamp01(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return float(value)


def trimf(x: float, a: float, b: float, c: float) -> float:
    """Función de membresía triangular."""
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a) if b != a else 0.0
    return (c - x) / (c - b) if c != b else 0.0


def trapmf(x: float, a: float, b: float, c: float, d: float) -> float:
    """Función de membresía trapezoidal."""
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a) if b != a else 0.0
    return (d - x) / (d - c) if d != c else 0.0


def fuzzy_and(*degrees: float) -> float:
    return min(_clamp01(d) for d in degrees) if degrees else 0.0


def fuzzy_or(*degrees: float) -> float:
    return max(_clamp01(d) for d in degrees) if degrees else 0.0


def sugeno(rules: Sequence[Tuple[float, float]]) -> float:
    """
    Defuzzificación Sugeno de orden cero.
    rules: lista de (activacion, valor_crisp_salida)
    """
    numerator = 0.0
    denominator = 0.0
    for activation, consequent in rules:
        strength = _clamp01(activation)
        if strength <= 0:
            continue
        numerator += strength * float(consequent)
        denominator += strength
    if denominator <= 0:
        return 0.0
    return numerator / denominator


# ---------------------------------------------------------------------------
# Product feature extraction (misma fuente de datos que el ranking previo)
# ---------------------------------------------------------------------------

USE_CASE_KEYWORDS = {
    'gaming': {
        'video-card': ('rtx', 'gtx', 'radeon', 'geforce', 'nvidia', 'amd', 'gaming'),
        'cpu': ('ryzen', 'x3d', 'intel'),
        'motherboard': ('b550', 'b650', 'x570', 'x670', 'z790', 'gaming'),
        'memory': ('ddr5', 'rgb'),
        'power-supply': ('gold', 'platinum', 'gaming'),
        'case': ('airflow', 'rgb', 'mesh'),
        'internal-hard-drive': ('nvme', 'ssd'),
    },
    'trabajo': {
        'video-card': ('quadro', 'workstation', 'creator', 'studio', 'pro'),
        'cpu': ('i7', 'i9', 'ryzen'),
        'motherboard': ('stable', 'business'),
        'memory': ('ecc',),
        'power-supply': ('gold', 'platinum'),
        'case': ('quiet', 'compact'),
        'internal-hard-drive': ('nvme', 'ssd'),
    },
    'estudio': {
        'video-card': ('integrated',),
        'cpu': ('i5', 'ryzen'),
        'motherboard': ('micro', 'budget'),
        'memory': (),
        'power-supply': ('bronze', 'gold'),
        'case': ('compact', 'mini'),
        'internal-hard-drive': ('ssd', 'nvme'),
    },
    'streaming': {
        'video-card': ('rtx', 'nvenc', 'creator'),
        'cpu': ('ryzen', 'i7', 'i9'),
        'motherboard': ('creator',),
        'memory': ('ddr5',),
        'power-supply': ('gold', 'platinum'),
        'case': ('airflow', 'cooling'),
        'internal-hard-drive': ('nvme', 'ssd'),
    },
}

PSU_TARGETS = {
    'estudio': 550,
    'trabajo': 650,
    'gaming': 750,
    'streaming': 850,
}


def _has_token(text: str, token: str) -> bool:
    if not text or not token:
        return False
    return re.search(
        rf'(?<![a-z0-9]){re.escape(str(token).lower())}(?![a-z0-9])',
        str(text).lower(),
    ) is not None


def _to_number(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            number = _to_number(item)
            if number is not None:
                return number
        return None
    text = re.sub(r'[^0-9.\-]+', '', str(value).strip())
    if text in ('', '-', '.', '-.'):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _category_slug(product: Any) -> str:
    category = getattr(product, 'category', None)
    return getattr(category, 'slug', getattr(product, 'category_slug', '')) or ''


def _specs(product: Any) -> Dict[str, Any]:
    if hasattr(product, 'get_specs_dict'):
        specs = product.get_specs_dict()
        if isinstance(specs, dict):
            return specs
    specs = getattr(product, 'specs', {}) or {}
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except (TypeError, ValueError):
            return {}
    return specs if isinstance(specs, dict) else {}


def _text(product: Any) -> str:
    specs = _specs(product)
    parts = [
        getattr(product, 'product_name', ''),
        getattr(product, 'description', ''),
        getattr(product, 'part_type', ''),
        _category_slug(product),
    ]
    category = getattr(product, 'category', None)
    parts.append(getattr(category, 'category_name', ''))
    for key, value in specs.items():
        parts.append(str(key))
        parts.append(str(value))
    return ' '.join(str(part or '') for part in parts).lower()


def _ram_capacity_gb(specs: Dict[str, Any]) -> Optional[float]:
    count = _to_number(specs.get('module_count'))
    cap = _to_number(specs.get('module_capacity_gb'))
    if count and cap:
        return count * cap
    return None


def _ddr_generation(specs: Dict[str, Any]) -> Optional[int]:
    speed = specs.get('speed')
    if isinstance(speed, (list, tuple)) and speed:
        gen = _to_number(speed[0])
        if gen in (4, 5):
            return int(gen)
    return None


def _add_reason(reasons: List[str], label: str) -> None:
    if label and label not in reasons:
        reasons.append(label)


def matching_keywords(product: Any, use_case: str) -> List[str]:
    slug = _category_slug(product)
    text = _text(product)
    keywords = USE_CASE_KEYWORDS.get(use_case, {}).get(slug, ())
    return [keyword for keyword in keywords if _has_token(text, keyword)]


# ---------------------------------------------------------------------------
# Shared fuzzy blocks: precio + keywords
# ---------------------------------------------------------------------------

def _price_memberships(price: float, budget: float) -> Dict[str, float]:
    if price <= 0 or budget <= 0:
        return {'barato': 0.0, 'adecuado': 0.0, 'caro': 1.0}
    ratio = price / budget
    return {
        'barato': trapmf(ratio, 0.0, 0.0, 0.35, 0.70),
        'adecuado': trimf(ratio, 0.55, 1.0, 1.35),
        'caro': trapmf(ratio, 1.10, 1.45, 5.0, 5.0),
    }


def _fuzzy_price_score(price: float, budget: float, reasons: List[str]) -> float:
    """Salida crisp ~0-320 (misma escala aproximada que el score previo)."""
    m = _price_memberships(price, budget)
    under_budget = 1.0 if budget > 0 and price <= budget * 1.15 else 0.0
    rules = [
        (m['adecuado'], 320.0),
        (fuzzy_and(m['barato'], 1.0 - m['caro']), 120.0),
        (m['caro'], 20.0),
        (fuzzy_and(m['adecuado'], under_budget), 40.0),
    ]
    # Bonus de cercanía: segunda inferencia pequeña
    score = sugeno(rules[:3]) + (40.0 * under_budget * m['adecuado'])
    if budget > 0 and abs(price - budget) / budget <= 0.12:
        _add_reason(reasons, 'cerca de tu presupuesto')
    return score


def _keyword_memberships(hits: int) -> Dict[str, float]:
    x = float(hits)
    return {
        'ninguno': trapmf(x, -0.1, -0.1, 0.0, 0.8),
        'pocos': trimf(x, 0.2, 1.0, 2.2),
        'varios': trapmf(x, 1.5, 3.0, 10.0, 10.0),
    }


def _fuzzy_keyword_score(hits: Sequence[str], reasons: List[str]) -> float:
    m = _keyword_memberships(len(hits))
    score = sugeno([
        (m['ninguno'], 0.0),
        (m['pocos'], 45.0),
        (m['varios'], 110.0),
    ])
    if hits:
        _add_reason(reasons, 'coincide con el uso')
    return score


# ---------------------------------------------------------------------------
# Per-component performance fuzzy systems
# ---------------------------------------------------------------------------

def _gpu_tier(specs: Dict[str, Any], text: str) -> Tuple[float, Dict[str, bool]]:
    chipset = str(specs.get('chipset') or '').lower()
    brand = str(specs.get('gpu_brand') or '').lower()
    haystack = f'{chipset} {brand} {text}'
    flags = {
        'rtx': _has_token(haystack, 'rtx'),
        'gtx': _has_token(haystack, 'gtx'),
        'radeon': _has_token(haystack, 'radeon'),
        'workstation': any(
            _has_token(haystack, token)
            for token in ('quadro', 'workstation', 'studio', 'creator')
        ) or 'radeon pro' in haystack,
        'integrated': _has_token(haystack, 'integrated'),
        'nvidia_amd': brand in ('nvidia', 'amd'),
    }
    if flags['rtx']:
        tier = 0.95
    elif flags['gtx'] or flags['radeon']:
        tier = 0.65
    elif flags['workstation']:
        tier = 0.75
    elif flags['integrated']:
        tier = 0.35
    else:
        tier = 0.15
    return tier, flags


def _fuzzy_gpu(specs: Dict[str, Any], text: str, use_case: str, reasons: List[str]) -> float:
    tier, flags = _gpu_tier(specs, text)
    vram = _to_number(specs.get('memory')) or 0.0
    vram_baja = trapmf(vram, 0, 0, 4, 8)
    vram_media = trimf(vram, 6, 10, 14)
    vram_alta = trapmf(vram, 12, 16, 48, 48)
    tier_bajo = trapmf(tier, 0, 0, 0.25, 0.45)
    tier_medio = trimf(tier, 0.35, 0.65, 0.85)
    tier_alto = trapmf(tier, 0.70, 0.90, 1.0, 1.0)

    work = 1.0 if flags['workstation'] else 0.0
    integrated = 1.0 if flags['integrated'] else 0.0

    if use_case == 'gaming':
        # Workstation baja el atractivo gaming vía regla con salida baja.
        score = sugeno([
            (fuzzy_and(tier_alto, fuzzy_or(vram_alta, vram_media), 1.0 - work), 340.0),
            (fuzzy_and(tier_medio, fuzzy_or(vram_media, vram_alta), 1.0 - work), 220.0),
            (fuzzy_and(tier_medio, vram_baja, 1.0 - work), 150.0),
            (fuzzy_and(tier_bajo, 1.0 - work), 35.0),
            (work, 90.0),
        ])
        if flags['rtx']:
            _add_reason(reasons, 'chipset RTX')
        elif flags['gtx'] or flags['radeon']:
            _add_reason(reasons, 'GPU gamer')
        if vram >= 8:
            _add_reason(reasons, f'{int(vram)} GB VRAM')
    elif use_case == 'trabajo':
        score = sugeno([
            (fuzzy_and(work, fuzzy_or(vram_alta, vram_media)), 360.0),
            (fuzzy_and(tier_alto, fuzzy_or(vram_alta, vram_media)), 200.0),
            (fuzzy_and(tier_medio, vram_media), 140.0),
            (tier_bajo, 30.0),
        ])
        if flags['workstation']:
            _add_reason(reasons, 'GPU para trabajo')
        if vram >= 8:
            _add_reason(reasons, f'{int(vram)} GB VRAM')
    elif use_case == 'estudio':
        score = sugeno([
            (fuzzy_and(vram_baja, fuzzy_or(tier_bajo, tier_medio)), 260.0),
            (vram_media, 140.0),
            (vram_alta, 40.0),
            (integrated, 280.0),
        ])
        if (vram and vram <= 8) or flags['integrated']:
            _add_reason(reasons, 'GPU ligera')
    else:  # streaming
        score = sugeno([
            (fuzzy_and(tier_alto, fuzzy_or(vram_alta, vram_media)), 360.0),
            (fuzzy_and(tier_medio, vram_media), 180.0),
            (tier_bajo, 40.0),
        ])
        if flags['rtx']:
            _add_reason(reasons, 'RTX / NVENC')
        if vram >= 12:
            _add_reason(reasons, f'{int(vram)} GB VRAM')

    if flags['nvidia_amd']:
        score += 30.0
    return score


def _fuzzy_cpu(product: Any, specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    name = (getattr(product, 'product_name', '') or '').lower()
    cores = _to_number(specs.get('core_count')) or _to_number(specs.get('cores')) or 0.0
    tdp = _to_number(specs.get('tdp')) or 0.0
    boost = _to_number(specs.get('boost_clock')) or 0.0
    is_x3d = 1.0 if 'x3d' in name else 0.0
    is_prod = 1.0 if any(t in name for t in ('i7', 'i9', 'ryzen 7', 'ryzen 9')) else 0.0
    is_study = 1.0 if any(t in name for t in ('i3', 'i5', 'ryzen 3', 'ryzen 5')) else 0.0

    cores_bajos = trapmf(cores, 0, 0, 4, 6)
    cores_medios = trimf(cores, 4, 8, 12)
    cores_altos = trapmf(cores, 10, 16, 64, 64)
    tdp_bajo = trapmf(tdp, 0, 0, 45, 75)
    tdp_alto = trapmf(tdp, 85, 120, 300, 300)
    boost_alto = trapmf(boost, 4.0, 5.0, 7.0, 7.0)

    if use_case == 'gaming':
        score = sugeno([
            (fuzzy_and(is_x3d, fuzzy_or(cores_medios, cores_altos)), 380.0),
            (fuzzy_and(cores_medios, boost_alto), 280.0),
            (fuzzy_and(cores_altos, boost_alto), 300.0),
            (cores_bajos, 80.0),
        ])
        if is_x3d:
            _add_reason(reasons, 'caché 3D')
        if cores >= 6:
            _add_reason(reasons, f'{int(cores)} núcleos')
    elif use_case == 'trabajo':
        score = sugeno([
            (fuzzy_and(cores_altos, is_prod), 360.0),
            (fuzzy_and(cores_medios, is_prod), 280.0),
            (cores_medios, 200.0),
            (cores_bajos, 60.0),
        ])
        if cores >= 8:
            _add_reason(reasons, f'{int(cores)} núcleos')
        if is_prod:
            _add_reason(reasons, 'CPU de productividad')
    elif use_case == 'estudio':
        score = sugeno([
            (fuzzy_and(is_study, tdp_bajo, cores_medios), 360.0),
            (fuzzy_and(is_study, cores_medios), 300.0),
            (fuzzy_and(tdp_bajo, cores_medios), 260.0),
            (cores_altos, 50.0),
            (cores_bajos, 100.0),
        ])
        if is_study:
            _add_reason(reasons, 'CPU de estudio')
        if tdp and tdp <= 65:
            _add_reason(reasons, f'TDP {int(tdp)}W')
    else:  # streaming
        score = sugeno([
            (fuzzy_and(cores_altos, fuzzy_or(tdp_alto, 1.0)), 340.0),
            (fuzzy_and(cores_medios, is_prod), 280.0),
            (cores_medios, 200.0),
            (cores_bajos, 50.0),
        ])
        if cores >= 8:
            _add_reason(reasons, f'{int(cores)} núcleos para encoding')
    return score


def _fuzzy_memory(specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    gb = _ram_capacity_gb(specs) or 0.0
    ddr = _ddr_generation(specs)
    gb_baja = trapmf(gb, 0, 0, 8, 12)
    gb_media = trimf(gb, 8, 16, 24)
    gb_alta = trapmf(gb, 24, 32, 256, 256)
    ddr5 = 1.0 if ddr == 5 else 0.0
    ddr4 = 1.0 if ddr == 4 else 0.0

    if use_case == 'estudio':
        score = sugeno([
            (gb_media, 220.0),
            (fuzzy_and(gb_alta, 1.0), 90.0),
            (gb_baja, 60.0),
            (ddr4, 40.0),
        ])
    elif use_case == 'streaming':
        score = sugeno([
            (gb_alta, 280.0),
            (gb_media, 120.0),
            (gb_baja, 40.0),
            (ddr5, 80.0),
        ])
    else:
        score = sugeno([
            (gb_alta, 260.0),
            (gb_media, 160.0),
            (gb_baja, 50.0),
            (ddr5, 80.0),
        ])
    if gb:
        _add_reason(reasons, f'{int(gb)} GB RAM')
    if ddr == 5 and use_case in ('gaming', 'streaming', 'trabajo'):
        _add_reason(reasons, 'DDR5')
    return score


def _fuzzy_psu(specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    wattage = _to_number(specs.get('wattage')) or 0.0
    efficiency = str(specs.get('efficiency') or '').lower()
    target = float(PSU_TARGETS.get(use_case, 650))
    ratio = wattage / target if target else 0.0
    pot_baja = trapmf(ratio, 0, 0, 0.6, 0.85)
    pot_ok = trimf(ratio, 0.75, 1.0, 1.25)
    pot_alta = trapmf(ratio, 1.15, 1.4, 3.0, 3.0)
    eff_alta = 1.0 if any(t in efficiency for t in ('gold', 'platinum', 'titanium')) else 0.0
    score = sugeno([
        (fuzzy_and(pot_ok, eff_alta), 280.0),
        (pot_ok, 200.0),
        (pot_alta, 120.0),
        (pot_baja, 60.0),
        (eff_alta, 80.0),
    ])
    if wattage:
        _add_reason(reasons, f'{int(wattage)}W')
    if eff_alta:
        _add_reason(reasons, efficiency or 'alta eficiencia')
    return score


def _fuzzy_storage(specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    kind = str(specs.get('type') or '').lower()
    interface = str(specs.get('interface') or '').lower()
    form = str(specs.get('form_factor') or '').lower()
    capacity = _to_number(specs.get('capacity')) or 0.0
    is_nvme = 1.0 if ('nvme' in interface or 'pcie' in interface or 'nvme' in kind) else 0.0
    is_ssd = 1.0 if (is_nvme or 'ssd' in kind or 'm.2' in form) else 0.0
    cap_media = trimf(capacity, 256, 1000, 2000)
    cap_alta = trapmf(capacity, 1500, 2000, 8000, 8000)

    if use_case == 'streaming':
        score = sugeno([
            (fuzzy_and(is_nvme, cap_alta), 320.0),
            (fuzzy_and(is_nvme, cap_media), 260.0),
            (is_ssd, 180.0),
            (1.0 - is_ssd, 40.0),
        ])
        if capacity >= 2000:
            _add_reason(reasons, f'{int(round(capacity / 1000))} TB')
    elif use_case == 'estudio':
        score = sugeno([
            (is_nvme, 240.0),
            (is_ssd, 200.0),
            (1.0 - is_ssd, 60.0),
        ])
    else:
        score = sugeno([
            (fuzzy_and(is_nvme, fuzzy_or(cap_media, cap_alta)), 280.0),
            (is_nvme, 240.0),
            (is_ssd, 180.0),
            (1.0 - is_ssd, 30.0),
        ])
    if is_nvme:
        _add_reason(reasons, 'SSD NVMe')
    elif is_ssd:
        _add_reason(reasons, 'SSD')
    return score


def _fuzzy_motherboard(product: Any, specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    name = (getattr(product, 'product_name', '') or '').lower()
    form = str(specs.get('form_factor') or '').lower()
    max_memory = _to_number(specs.get('max_memory')) or 0.0
    gaming_chip = 1.0 if any(
        t in name for t in ('b550', 'b650', 'x570', 'x670', 'z790', 'b760', 'gaming')
    ) else 0.0
    micro = 1.0 if 'micro' in form else 0.0
    mem_alta = trapmf(max_memory, 64, 128, 512, 512)

    if use_case == 'gaming':
        score = sugeno([
            (fuzzy_and(gaming_chip, mem_alta), 240.0),
            (gaming_chip, 180.0),
            (mem_alta, 80.0),
            (1.0 - gaming_chip, 40.0),
        ])
        if gaming_chip:
            _add_reason(reasons, 'chipset gaming')
    elif use_case == 'estudio':
        score = sugeno([
            (micro, 160.0),
            (mem_alta, 60.0),
            (1.0 - micro, 50.0),
        ])
        if micro:
            _add_reason(reasons, 'formato compacto')
    else:
        score = sugeno([
            (fuzzy_or(gaming_chip, mem_alta), 140.0),
            (1.0, 60.0),
        ])
    return score


def _fuzzy_case(product: Any, specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    name = (getattr(product, 'product_name', '') or '').lower()
    side = str(specs.get('side_panel') or '').lower()
    volume = _to_number(specs.get('external_volume')) or 0.0
    airflow = 1.0 if ('airflow' in name or 'mesh' in side) else 0.0
    rgb = 1.0 if ('rgb' in name or 'argb' in name) else 0.0
    compacto = trapmf(volume, 0, 0, 30, 45) if volume else 0.0

    if use_case in ('gaming', 'streaming'):
        score = sugeno([
            (fuzzy_and(airflow, rgb), 180.0),
            (airflow, 150.0),
            (rgb, 60.0),
            (1.0 - airflow, 30.0),
        ])
        if airflow:
            _add_reason(reasons, 'airflow')
    elif use_case == 'estudio':
        score = sugeno([
            (compacto, 160.0),
            (1.0 - compacto, 40.0),
        ])
        if volume and volume <= 40:
            _add_reason(reasons, 'compacto')
    else:
        score = sugeno([(airflow, 100.0), (1.0, 40.0)])
    return score


def _fuzzy_cooler(specs: Dict[str, Any], use_case: str, reasons: List[str]) -> float:
    radiator = _to_number(specs.get('radiator_size')) or 0.0
    cooler_type = str(specs.get('cooler_type') or '').lower()
    rad_grande = trapmf(radiator, 180, 240, 480, 480)
    air = 1.0 if 'air' in cooler_type else 0.0

    if use_case in ('gaming', 'streaming'):
        score = sugeno([
            (rad_grande, 180.0),
            (1.0 - rad_grande, 40.0),
        ])
        if radiator >= 240:
            _add_reason(reasons, f'radiador {int(radiator)} mm')
    elif use_case == 'estudio':
        score = sugeno([(air, 120.0), (1.0 - air, 40.0)])
    else:
        score = sugeno([(rad_grande, 120.0), (air, 80.0), (1.0, 40.0)])
    return score


def _fuzzy_specs(product: Any, use_case: str, reasons: List[str]) -> float:
    slug = _category_slug(product)
    specs = _specs(product)
    text = _text(product)
    if slug == 'video-card':
        return _fuzzy_gpu(specs, text, use_case, reasons)
    if slug == 'cpu':
        return _fuzzy_cpu(product, specs, use_case, reasons)
    if slug == 'memory':
        return _fuzzy_memory(specs, use_case, reasons)
    if slug == 'power-supply':
        return _fuzzy_psu(specs, use_case, reasons)
    if slug == 'internal-hard-drive':
        return _fuzzy_storage(specs, use_case, reasons)
    if slug == 'motherboard':
        return _fuzzy_motherboard(product, specs, use_case, reasons)
    if slug == 'case':
        return _fuzzy_case(product, specs, use_case, reasons)
    if slug == 'cpu-cooler':
        return _fuzzy_cooler(specs, use_case, reasons)
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_component(
    product: Any,
    budget: float,
    use_case: str,
) -> Tuple[float, List[str], Dict[str, Any]]:
    """
    Evalúa un componente individual con lógica difusa.

    Returns:
        score total, motivos legibles, desglose {precio, specs, keywords, keyword_hits}
    """
    reasons: List[str] = []
    keyword_hits = matching_keywords(product, use_case)
    price = getattr(product, 'price', 0) or 0

    score_price = _fuzzy_price_score(float(price), float(budget), reasons)
    score_specs = _fuzzy_specs(product, use_case, reasons)
    score_keywords = _fuzzy_keyword_score(keyword_hits, reasons)
    score = score_price + score_specs + score_keywords

    parts = {
        'precio': round(score_price, 2),
        'specs': round(score_specs, 2),
        'keywords': round(score_keywords, 2),
        'keyword_hits': keyword_hits,
        'engine': 'fuzzy-sugeno',
    }
    return score, reasons, parts
