"""
Inferencia Mamdani para pesos de prioridad de cada pieza.

Las entradas siguen siendo las del formulario (presupuesto en MXN y caso de
uso). Aquí se difuminan y las reglas if-then producen conjuntos de salida
(Muy baja … Muy alta). La defuzzificación es por centroide.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from assistant.compatibility import BUILD_SLOTS
from assistant.fuzzy import trapmf, trimf

TERMS = ('muy_baja', 'baja', 'media', 'alta', 'muy_alta')
TERM_LABELS = {
    'muy_baja': 'Muy baja',
    'baja': 'Baja',
    'media': 'Media',
    'alta': 'Alta',
    'muy_alta': 'Muy alta',
}
BUDGET_TERMS = ('bajo', 'medio', 'alto', 'muy_alto')
USES = ('gaming', 'trabajo', 'estudio', 'streaming')

# Consecuente por uso, término de presupuesto y pieza.
# Contraste a propósito: en gaming el dinero se va a la GPU; en trabajo, a CPU y RAM;
# en estudio la GPU casi no pesa. Si todas salieran "altas", el presupuesto se reparte parejo.
_PRIORITY_TABLE = {
    'gaming': {
        'bajo': {
            'cpu': 'alta', 'video-card': 'muy_alta', 'memory': 'media',
            'motherboard': 'baja', 'internal-hard-drive': 'muy_baja',
            'power-supply': 'media', 'case': 'muy_baja', 'cpu-cooler': 'baja',
        },
        'medio': {
            'cpu': 'alta', 'video-card': 'muy_alta', 'memory': 'alta',
            'motherboard': 'media', 'internal-hard-drive': 'baja',
            'power-supply': 'alta', 'case': 'baja', 'cpu-cooler': 'media',
        },
        'alto': {
            'cpu': 'muy_alta', 'video-card': 'muy_alta', 'memory': 'alta',
            'motherboard': 'alta', 'internal-hard-drive': 'media',
            'power-supply': 'muy_alta', 'case': 'media', 'cpu-cooler': 'alta',
        },
        'muy_alto': {
            'cpu': 'muy_alta', 'video-card': 'muy_alta', 'memory': 'muy_alta',
            'motherboard': 'muy_alta', 'internal-hard-drive': 'alta',
            'power-supply': 'muy_alta', 'case': 'alta', 'cpu-cooler': 'muy_alta',
        },
    },
    'trabajo': {
        'bajo': {
            'cpu': 'alta', 'video-card': 'muy_baja', 'memory': 'alta',
            'motherboard': 'media', 'internal-hard-drive': 'media',
            'power-supply': 'baja', 'case': 'muy_baja', 'cpu-cooler': 'baja',
        },
        'medio': {
            'cpu': 'muy_alta', 'video-card': 'baja', 'memory': 'muy_alta',
            'motherboard': 'alta', 'internal-hard-drive': 'alta',
            'power-supply': 'media', 'case': 'baja', 'cpu-cooler': 'media',
        },
        'alto': {
            'cpu': 'muy_alta', 'video-card': 'media', 'memory': 'muy_alta',
            'motherboard': 'alta', 'internal-hard-drive': 'muy_alta',
            'power-supply': 'media', 'case': 'media', 'cpu-cooler': 'alta',
        },
        'muy_alto': {
            'cpu': 'muy_alta', 'video-card': 'media', 'memory': 'muy_alta',
            'motherboard': 'muy_alta', 'internal-hard-drive': 'muy_alta',
            'power-supply': 'alta', 'case': 'media', 'cpu-cooler': 'alta',
        },
    },
    'estudio': {
        'bajo': {
            'cpu': 'media', 'video-card': 'muy_baja', 'memory': 'media',
            'motherboard': 'baja', 'internal-hard-drive': 'media',
            'power-supply': 'muy_baja', 'case': 'muy_baja', 'cpu-cooler': 'muy_baja',
        },
        'medio': {
            'cpu': 'media', 'video-card': 'muy_baja', 'memory': 'media',
            'motherboard': 'media', 'internal-hard-drive': 'media',
            'power-supply': 'baja', 'case': 'baja', 'cpu-cooler': 'baja',
        },
        'alto': {
            'cpu': 'alta', 'video-card': 'baja', 'memory': 'alta',
            'motherboard': 'media', 'internal-hard-drive': 'alta',
            'power-supply': 'media', 'case': 'baja', 'cpu-cooler': 'media',
        },
        'muy_alto': {
            'cpu': 'alta', 'video-card': 'media', 'memory': 'alta',
            'motherboard': 'alta', 'internal-hard-drive': 'muy_alta',
            'power-supply': 'media', 'case': 'media', 'cpu-cooler': 'media',
        },
    },
    'streaming': {
        'bajo': {
            'cpu': 'muy_alta', 'video-card': 'alta', 'memory': 'alta',
            'motherboard': 'baja', 'internal-hard-drive': 'media',
            'power-supply': 'media', 'case': 'muy_baja', 'cpu-cooler': 'baja',
        },
        'medio': {
            'cpu': 'muy_alta', 'video-card': 'muy_alta', 'memory': 'alta',
            'motherboard': 'media', 'internal-hard-drive': 'alta',
            'power-supply': 'alta', 'case': 'baja', 'cpu-cooler': 'media',
        },
        'alto': {
            'cpu': 'muy_alta', 'video-card': 'muy_alta', 'memory': 'muy_alta',
            'motherboard': 'alta', 'internal-hard-drive': 'muy_alta',
            'power-supply': 'muy_alta', 'case': 'media', 'cpu-cooler': 'alta',
        },
        'muy_alto': {
            'cpu': 'muy_alta', 'video-card': 'muy_alta', 'memory': 'muy_alta',
            'motherboard': 'muy_alta', 'internal-hard-drive': 'muy_alta',
            'power-supply': 'muy_alta', 'case': 'alta', 'cpu-cooler': 'muy_alta',
        },
    },
}


def _series(kind: str, *points: float) -> List[float]:
    values = []
    for x in range(101):
        if kind == 'tri':
            values.append(trimf(x, *points))
        else:
            values.append(trapmf(x, *points))
    return values


# Hombros abiertos: a=-1 y d=101 para que 0 y 100 pertenezcan al conjunto.
OUTPUT_MF = {
    'muy_baja': _series('trap', -1, 0, 10, 30),
    'baja': _series('tri', 15, 32, 48),
    'media': _series('tri', 38, 50, 66),
    'alta': _series('tri', 55, 72, 88),
    'muy_alta': _series('trap', 72, 88, 100, 101),
}


def budget_memberships(budget: float) -> Dict[str, float]:
    value = float(budget)
    return {
        'bajo': trapmf(value, -1, 0, 8000, 18000),
        'medio': trimf(value, 12000, 25000, 45000),
        'alto': trimf(value, 35000, 60000, 100000),
        'muy_alto': trapmf(value, 75000, 110000, 200000, 200001),
    }


def _centroid(aggregated: List[float]) -> float:
    denominator = sum(aggregated)
    if denominator <= 0:
        return 50.0
    numerator = sum(index * strength for index, strength in enumerate(aggregated))
    return numerator / denominator


def _label_for(score: float) -> str:
    point = max(0, min(100, int(round(score))))
    best_term = max(
        TERMS,
        key=lambda term: (OUTPUT_MF[term][point], TERMS.index(term)),
    )
    return TERM_LABELS[best_term]


def _defuzzify(fired: List[Tuple[float, str]]) -> float:
    aggregated = [0.0] * 101
    active = False
    for strength, term in fired:
        if strength <= 0:
            continue
        active = True
        curve = OUTPUT_MF[term]
        for index, degree in enumerate(curve):
            clipped = degree if degree < strength else strength
            if clipped > aggregated[index]:
                aggregated[index] = clipped
    if not active:
        return 50.0
    return _centroid(aggregated)


def _apply_pref_boosts(priorities: Dict[str, Dict[str, float]], prefs: dict) -> None:
    """Ajusta pesos segun resolucion / rendimiento / experiencia."""
    resolution = prefs.get('resolution') or '1080p'
    performance = prefs.get('performance') or 'medio'
    experience = prefs.get('experience') or 'medio'

    def _bump(slot: str, delta: float) -> None:
        score = max(5.0, min(98.0, priorities[slot]['score'] + delta))
        priorities[slot]['score'] = round(score, 2)
        priorities[slot]['label'] = _label_for(score)

    if resolution in ('1440p', '4k') or performance == 'alto':
        _bump('video-card', 12 if resolution == '4k' or performance == 'alto' else 8)
        _bump('power-supply', 6)
        _bump('cpu-cooler', 5)
        _bump('memory', 4)
    if resolution == 'office' or performance == 'bajo':
        _bump('video-card', -10)
        _bump('internal-hard-drive', 4)
    if experience == 'principiante':
        _bump('motherboard', 4)
        _bump('power-supply', 5)
        _bump('case', -3)
    if experience == 'avanzado' and performance == 'alto':
        _bump('cpu', 5)
        _bump('cpu-cooler', 6)


def infer_priorities(
    budget: float,
    use_case: str,
    prefs: dict | None = None,
) -> Dict[str, Dict[str, float]]:
    """
    Pesos Mamdani por pieza.

    Cada entrada es {score: 0-100, label: 'Muy alta'}.
    """
    from assistant.preferences import normalize_prefs

    selected = use_case if use_case in _PRIORITY_TABLE else 'gaming'
    normalized = normalize_prefs(prefs, use_case=selected)
    memberships = budget_memberships(budget)
    table = _PRIORITY_TABLE[selected]
    priorities = {}
    for slot in BUILD_SLOTS:
        fired = [
            (memberships[budget_term], table[budget_term][slot])
            for budget_term in BUDGET_TERMS
        ]
        score = _defuzzify(fired)
        priorities[slot] = {
            'score': round(score, 2),
            'label': _label_for(score),
        }
    _apply_pref_boosts(priorities, normalized)
    return priorities


def priority_rows(priorities: Dict[str, Dict[str, float]]) -> List[dict]:
    from assistant.compatibility import SLOT_LABELS

    return [
        {
            'slot': slot,
            'label': SLOT_LABELS[slot],
            'score': priorities[slot]['score'],
            'prioridad': priorities[slot]['label'],
        }
        for slot in BUILD_SLOTS
    ]
