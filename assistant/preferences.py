"""
Preferencias del usuario para armar la PC.

Ademas de uso y presupuesto, el chat/formulario pueden aportar resolucion,
rendimiento esperado, experiencia y marca preferida. Todo tiene default
seguro para no frenar el flujo.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

RESOLUTIONS = ('office', '1080p', '1440p', '4k')
PERFORMANCE = ('bajo', 'medio', 'alto')
EXPERIENCE = ('principiante', 'medio', 'avanzado')
BRANDS = ('any', 'amd', 'intel')

DEFAULTS = {
    'resolution': None,      # se infiere del uso si falta
    'performance': 'medio',
    'experience': 'medio',
    'brand': 'any',
}


def _norm_resolution(value: Any) -> Optional[str]:
    if value is None or value == '':
        return None
    text = str(value).strip().lower().replace(' ', '')
    aliases = {
        '1080': '1080p',
        'fhd': '1080p',
        'fullhd': '1080p',
        '1920x1080': '1080p',
        '1440': '1440p',
        '2k': '1440p',
        'qhd': '1440p',
        '2560x1440': '1440p',
        '2160': '4k',
        '2160p': '4k',
        'uhd': '4k',
        'oficina': 'office',
        'office': 'office',
        'basico': 'office',
    }
    text = aliases.get(text, text)
    if text in RESOLUTIONS:
        return text
    return None


def _norm_choice(value: Any, allowed: tuple, default: str) -> str:
    if value is None or value == '':
        return default
    text = str(value).strip().lower()
    aliases = {
        'low': 'bajo',
        'basic': 'bajo',
        'suave': 'bajo',
        'medium': 'medio',
        'normal': 'medio',
        'intermedio': 'medio',
        'high': 'alto',
        'ultra': 'alto',
        'intenso': 'alto',
        'beginner': 'principiante',
        'novato': 'principiante',
        'newbie': 'principiante',
        'advanced': 'avanzado',
        'pro': 'avanzado',
        'experto': 'avanzado',
        'indiferente': 'any',
        'cualquiera': 'any',
        'daigual': 'any',
        'me_da_igual': 'any',
    }
    text = aliases.get(text, text)
    if text in allowed:
        return text
    return default


def default_resolution_for_use(use_case: str) -> str:
    if use_case == 'estudio':
        return 'office'
    if use_case == 'trabajo':
        return '1080p'
    return '1080p'


def normalize_prefs(
    raw: Optional[Dict[str, Any]] = None,
    *,
    use_case: str = 'gaming',
) -> Dict[str, str]:
    data = dict(DEFAULTS)
    if isinstance(raw, dict):
        data.update({key: raw.get(key) for key in DEFAULTS})
    resolution = _norm_resolution(data.get('resolution'))
    if resolution is None:
        resolution = default_resolution_for_use(use_case)
    return {
        'resolution': resolution,
        'performance': _norm_choice(data.get('performance'), PERFORMANCE, 'medio'),
        'experience': _norm_choice(data.get('experience'), EXPERIENCE, 'medio'),
        'brand': _norm_choice(data.get('brand'), BRANDS, 'any'),
    }


def prefs_summary(prefs: Dict[str, str]) -> str:
    res = {
        'office': 'uso de oficina',
        '1080p': '1080p',
        '1440p': '1440p',
        '4k': '4K',
    }.get(prefs.get('resolution', ''), prefs.get('resolution', ''))
    perf = prefs.get('performance', 'medio')
    exp = prefs.get('experience', 'medio')
    brand = prefs.get('brand', 'any')
    brand_txt = 'AMD o Intel' if brand == 'any' else brand.upper()
    return f'{res}, rendimiento {perf}, nivel {exp}, marca {brand_txt}'
