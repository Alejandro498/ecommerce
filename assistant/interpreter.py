"""
Interprete de lenguaje natural para el asistente.

El LLM solo traduce el mensaje a {use_case, budget}. No elige piezas.
La recomendacion sigue saliendo de Mamdani + genetico.
No usa embeddings ni vector store: es extraccion estructurada.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings

USE_CASES = ('gaming', 'trabajo', 'estudio', 'streaming')
MIN_BUDGET = 2000
MAX_BUDGET = 200000

# Prompt corto a proposito: menos tokens de entrada = respuesta mas rapida.
SYSTEM_PROMPT = """Interprete JSON. NO recomiendes PCs ni piezas.
Acumula del historial. ready=true solo si hay use_case y budget.
Salida SOLO JSON:
{"use_case":"gaming|trabajo|estudio|streaming"|null,"budget":int|null,
"resolution":"office|1080p|1440p|4k"|null,
"performance":"bajo|medio|alto"|null,
"experience":"principiante|medio|avanzado"|null,
"brand":"amd|intel|any"|null,
"ready":bool,"ask":str|null,"summary":str}
Mapa uso: jugar/GTA/fps->gaming; escuela->estudio; editar/render->trabajo; stream->streaming.
Resolucion: 1080/fullhd->1080p; 1440/2k->1440p; 4k/uhd->4k; oficina->office.
Rendimiento: suave/basico->bajo; normal->medio; alto/ultra/144fps->alto.
Experiencia: novato->principiante; experto->avanzado.
Marca CPU: amd/ryzen->amd; intel->intel; si no dice->any.
Presupuesto MXN ("18 mil"=18000)."""


def _clamp_budget(value: Any) -> Optional[int]:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if number < MIN_BUDGET or number > MAX_BUDGET:
        return None
    return number


def _normalize_use_case(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    aliases = {
        'game': 'gaming',
        'gamer': 'gaming',
        'juegos': 'gaming',
        'jugar': 'gaming',
        'office': 'estudio',
        'escuela': 'estudio',
        'school': 'estudio',
        'work': 'trabajo',
        'productivity': 'trabajo',
        'stream': 'streaming',
        'contenido': 'streaming',
    }
    text = aliases.get(text, text)
    if text in USE_CASES:
        return text
    return None


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('La respuesta del LLM no es un objeto JSON')
    return data


_USE_LABELS = {
    'gaming': 'jugar',
    'trabajo': 'trabajo',
    'estudio': 'estudio u oficina',
    'streaming': 'streaming o crear contenido',
}


def _natural_ask(use_case: Optional[str], budget: Optional[int]) -> str:
    if use_case and not budget:
        label = _USE_LABELS.get(use_case, use_case)
        return f'Va, para {label}. ¿Más o menos cuánto quieres gastar en pesos?'
    if budget and not use_case:
        return (
            f'Tengo unos ${budget} MXN. '
            '¿La quieres más para jugar, para trabajar, para la escuela o para streamear?'
        )
    return (
        'Claro. Cuéntame para qué la quieres '
        '(jugar, trabajar, escuela o streamear) y más o menos cuánto puedes gastar.'
    )


def _natural_summary(use_case: str, budget: int) -> str:
    label = _USE_LABELS.get(use_case, use_case)
    return f'PC para {label} con unos ${budget} MXN'


def _extract_resolution(text: str) -> Optional[str]:
    lowered = (text or '').lower()
    if any(token in lowered for token in ('4k', '2160', 'uhd')):
        return '4k'
    if any(token in lowered for token in ('1440', '2k', 'qhd')):
        return '1440p'
    if any(token in lowered for token in ('1080', 'full hd', 'fullhd', 'fhd')):
        return '1080p'
    if any(token in lowered for token in ('oficina', 'office', 'solo navegar', 'word')):
        return 'office'
    return None


def _extract_performance(text: str) -> Optional[str]:
    lowered = (text or '').lower()
    if any(token in lowered for token in (
        '144 fps', '240 fps', 'ultra', 'alto rendimiento', 'rendimiento alto',
        'lo mejor', 'maximo', 'máximo', 'exigente',
    )):
        return 'alto'
    if re.search(r'\balto\b', lowered) and not any(
        token in lowered for token in ('gastar', 'gasto', 'presupuesto alto')
    ):
        return 'alto'
    if any(token in lowered for token in ('suave', 'basico', 'básico', 'barata', 'entrada', '60 fps')):
        return 'bajo'
    if any(token in lowered for token in ('medio', 'normal', 'equilibr', 'intermedio')):
        return 'medio'
    return None


def _extract_experience(text: str) -> Optional[str]:
    lowered = (text or '').lower()
    if any(token in lowered for token in ('principiante', 'novato', 'no se de pcs', 'primera pc', 'nunca arme')):
        return 'principiante'
    if any(token in lowered for token in ('avanzado', 'experto', 'overclock', 'ya se de hardware')):
        return 'avanzado'
    return None


def _extract_brand(text: str) -> Optional[str]:
    lowered = (text or '').lower()
    wants_amd = any(token in lowered for token in ('amd', 'ryzen'))
    wants_intel = 'intel' in lowered
    if wants_amd and not wants_intel:
        return 'amd'
    if wants_intel and not wants_amd:
        return 'intel'
    if any(token in lowered for token in ('me da igual', 'cualquiera', 'indiferente')):
        return 'any'
    return None


def _merge_prefs(
    message: str,
    history: Optional[List[Dict[str, str]]],
    base: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    prefs = {
        'resolution': (base or {}).get('resolution'),
        'performance': (base or {}).get('performance'),
        'experience': (base or {}).get('experience'),
        'brand': (base or {}).get('brand'),
    }
    for item in history or []:
        if item.get('role') != 'user':
            continue
        content = str(item.get('content') or '')
        prefs['resolution'] = _extract_resolution(content) or prefs['resolution']
        prefs['performance'] = _extract_performance(content) or prefs['performance']
        prefs['experience'] = _extract_experience(content) or prefs['experience']
        prefs['brand'] = _extract_brand(content) or prefs['brand']
    prefs['resolution'] = _extract_resolution(message) or prefs['resolution']
    prefs['performance'] = _extract_performance(message) or prefs['performance']
    prefs['experience'] = _extract_experience(message) or prefs['experience']
    prefs['brand'] = _extract_brand(message) or prefs['brand']
    return prefs


def _finalize(payload: Dict[str, Any], source: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    from assistant.preferences import normalize_prefs, prefs_summary

    use_case = _normalize_use_case(payload.get('use_case'))
    budget = _clamp_budget(payload.get('budget'))
    ready = bool(use_case and budget)
    ask = (payload.get('ask') or '').strip() or None
    summary = (payload.get('summary') or '').strip()
    raw_prefs = {
        'resolution': payload.get('resolution'),
        'performance': payload.get('performance'),
        'experience': payload.get('experience'),
        'brand': payload.get('brand'),
    }
    # Si vienen del merge de reglas, ya estan; si no, se normalizan con defaults.
    prefs = normalize_prefs(raw_prefs, use_case=use_case or 'gaming')

    if not use_case or not budget:
        technical = ask and any(
            token in ask.lower()
            for token in ('gaming,', 'use_case', 'streaming)', 'mamdani', 'mxn)')
        )
        if not ask or technical:
            ask = _natural_ask(use_case, budget)
        ready = False
    else:
        ask = None
        ready = True
        if not summary or summary.lower().startswith('uso '):
            summary = (
                f'{_natural_summary(use_case, budget)} '
                f'({prefs_summary(prefs)})'
            )

    return {
        'use_case': use_case,
        'budget': budget,
        'ready': ready,
        'ask': ask,
        'summary': summary,
        'source': source,
        'prefs': prefs,
        'resolution': prefs['resolution'],
        'performance': prefs['performance'],
        'experience': prefs['experience'],
        'brand': prefs['brand'],
    }


def _extract_use_case(text: str) -> Optional[str]:
    lowered = (text or '').lower()
    if any(token in lowered for token in ('stream', 'twitch', 'youtube', 'contenido')):
        return 'streaming'
    if any(token in lowered for token in (
        'juego', 'jugar', 'gamer', 'gaming', 'fps', 'esport', 'gta',
        'valorant', 'fortnite', '1080', '1440',
    )):
        return 'gaming'
    if any(token in lowered for token in ('trabajo', 'editar', 'render', 'program', 'cad')):
        return 'trabajo'
    if any(token in lowered for token in (
        'estudio', 'escuela', 'tarea', 'universidad', 'office', 'word', 'excel',
    )):
        return 'estudio'
    if lowered.strip() in USE_CASES:
        return lowered.strip()
    return None


_RESOLUTION_NUMBERS = {'720', '1080', '1440', '2160', '4320'}


def _extract_budget(text: str) -> Optional[int]:
    lowered = (text or '').lower().strip()
    mil = re.search(r'(\d+(?:[.,]\d+)?)\s*mil\b', lowered)
    if mil:
        return _clamp_budget(float(mil.group(1).replace(',', '.')) * 1000)
    k_match = re.search(r'(\d+(?:[.,]\d+)?)\s*k\b', lowered)
    if k_match:
        return _clamp_budget(float(k_match.group(1).replace(',', '.')) * 1000)
    if re.fullmatch(r'\d{4,6}', lowered):
        return _clamp_budget(lowered)

    candidates = []
    for match in re.finditer(
        r'(?:\$|mxn)?\s*(\d{1,3}(?:[ ,]\d{3})+|\d{4,6})\s*(?:pesos?|mxn)?',
        lowered,
    ):
        raw = re.sub(r'[ ,]', '', match.group(1))
        if raw in _RESOLUTION_NUMBERS:
            continue
        tail = lowered[match.end():match.end() + 6]
        if re.match(r'\s*(fps|hz|p\b)', tail):
            continue
        value = _clamp_budget(raw)
        if value is not None:
            candidates.append(value)
    if candidates:
        return candidates[-1]
    return None


def _merge_from_conversation(
    message: str,
    history: Optional[List[Dict[str, str]]],
    base: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[int]]:
    """Acumula uso y presupuesto del historial + mensaje actual."""
    use_case = _normalize_use_case((base or {}).get('use_case'))
    budget = _clamp_budget((base or {}).get('budget'))
    for item in history or []:
        if item.get('role') != 'user':
            continue
        content = str(item.get('content') or '')
        use_case = _extract_use_case(content) or use_case
        budget = _extract_budget(content) or budget
    use_case = _extract_use_case(message) or use_case
    budget = _extract_budget(message) or budget
    return use_case, budget


def interpret_with_rules(message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Respaldo local / atajo rapido: palabras clave + numeros, con memoria."""
    use_case, budget = _merge_from_conversation(message, history)
    prefs = _merge_prefs(message, history)
    return _finalize(
        {
            'use_case': use_case,
            'budget': budget,
            'ready': bool(use_case and budget),
            'ask': None,
            'summary': '',
            **prefs,
        },
        source='rules',
        history=history,
    )


def _call_openai(message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if not api_key:
        raise RuntimeError('Falta OPENAI_API_KEY en el archivo .env')

    model = getattr(settings, 'OPENAI_MODEL', 'gemini-3.5-flash-lite') or 'gemini-3.5-flash-lite'
    base_url = (getattr(settings, 'OPENAI_BASE_URL', '') or 'https://api.openai.com/v1').rstrip('/')
    timeout = float(getattr(settings, 'OPENAI_TIMEOUT_SECONDS', 20) or 20)

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    # Solo ultimos turnos y textos cortos: baja latencia.
    for item in (history or [])[-4:]:
        role = item.get('role')
        content = (item.get('content') or '').strip()
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content[:280]})
    messages.append({'role': 'user', 'content': (message or '').strip()[:500]})

    payload = {
        'model': model,
        'temperature': 0,
        'max_tokens': 180,
        'messages': messages,
        'response_format': {'type': 'json_object'},
    }

    response = requests.post(
        f'{base_url}/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400 and 'response_format' in (response.text or ''):
        payload.pop('response_format', None)
        response = requests.post(
            f'{base_url}/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=timeout,
        )
    if response.status_code >= 400:
        raise RuntimeError(f'Error del LLM ({response.status_code}): {response.text[:300]}')

    body = response.json()
    content = body['choices'][0]['message']['content']
    raw = _parse_llm_json(content)
    use_case, budget = _merge_from_conversation(message, history, raw)
    prefs = _merge_prefs(message, history, raw)
    return _finalize(
        {
            'use_case': use_case,
            'budget': budget,
            'ready': bool(use_case and budget),
            'ask': raw.get('ask'),
            'summary': raw.get('summary') or '',
            **prefs,
        },
        source='llm',
        history=history,
    )


def interpret_message(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    *,
    allow_rules_fallback: bool = True,
    force_llm: bool = False,
) -> Dict[str, Any]:
    """
    Interpreta el mensaje del usuario.

    Atajo: si las reglas locales ya sacan uso + presupuesto, no llama al LLM
    (casi instantaneo). El LLM solo entra cuando el mensaje es ambiguo.
    """
    text = (message or '').strip()
    if not text:
        return _finalize(
            {
                'use_case': None,
                'budget': None,
                'ready': False,
                'ask': 'Cuéntame para qué quieres la PC y cuánto quieres gastar.',
                'summary': '',
            },
            source='empty',
        )

    prefer_fast = getattr(settings, 'INTERPRETER_FAST_PATH', True)
    if prefer_fast and not force_llm:
        quick = interpret_with_rules(text, history)
        if quick['ready']:
            quick['source'] = 'rules-fast'
            return quick

    api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
    if api_key:
        try:
            return _call_openai(text, history)
        except Exception as exc:
            if not allow_rules_fallback:
                raise
            fallback = interpret_with_rules(text, history)
            fallback['source'] = 'rules'
            fallback['llm_error'] = str(exc)[:240]
            if fallback.get('ask'):
                fallback['ask'] = (
                    f'(Gemini no respondió. Usando reglas locales.) {fallback["ask"]}'
                )
            return fallback
    if allow_rules_fallback:
        return interpret_with_rules(text, history)
    raise RuntimeError('Falta OPENAI_API_KEY en el archivo .env')
