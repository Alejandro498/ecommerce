"""
Configuración y utilidades de filtros dinámicos por especificaciones (specs)
para cada categoría de componentes de PC.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q


# Definición de filtros por categoría solicitados por el usuario
CATEGORY_SPEC_CONFIG: Dict[str, List[Dict[str, str]]] = {
    'cpu': [
        {'key': 'brand', 'title': 'Marca'},
        {'key': 'socket', 'title': 'Socket'},
        {'key': 'core_count', 'title': 'Número de Núcleos'},
    ],
    'video-card': [
        {'key': 'gpu_brand', 'title': 'Marca GPU'},
        {'key': 'chipset', 'title': 'Chipset'},
    ],
    'motherboard': [
        {'key': 'socket', 'title': 'Socket'},
        {'key': 'brand', 'title': 'Marca'},
        {'key': 'form_factor', 'title': 'Factor de Forma'},
    ],
    'memory': [
        {'key': 'speed', 'title': 'Velocidad'},
        {'key': 'module_count', 'title': 'Módulos'},
        {'key': 'brand', 'title': 'Marca'},
    ],
    'case': [
        {'key': 'brand', 'title': 'Marca'},
        {'key': 'max_motherboard_form_factor', 'title': 'Formato Máx. Motherboard'},
    ],
    'power-supply': [
        {'key': 'type', 'title': 'Tipo'},
        {'key': 'wattage', 'title': 'Potencia (Wattage)'},
        {'key': 'brand', 'title': 'Marca'},
    ],
    'cpu-cooler': [
        {'key': 'brand', 'title': 'Marca'},
    ],
    'internal-hard-drive': [
        {'key': 'capacity', 'title': 'Capacidad'},
        {'key': 'type', 'title': 'Tipo de Almacenamiento'},
    ],
}


def format_spec_option_label(spec_key: str, val: Any) -> str:
    """Retorna una etiqueta visualmente amigable para el usuario."""
    if val is None:
        return ''
    if spec_key == 'core_count':
        try:
            n = int(val)
            return f"{n} núcleos" if n > 1 else f"{n} núcleo"
        except (ValueError, TypeError):
            return str(val)
    if spec_key == 'module_count':
        try:
            n = int(val)
            return f"{n} módulo{'s' if n > 1 else ''}"
        except (ValueError, TypeError):
            return str(val)
    if spec_key == 'wattage':
        try:
            n = int(float(val))
            return f"{n} W"
        except (ValueError, TypeError):
            return f"{val} W"
    if spec_key == 'capacity':
        try:
            c = float(val)
            if c >= 1000:
                tb = c / 1000
                return f"{int(tb)} TB" if tb.is_integer() else f"{tb:.1f} TB"
            return f"{int(c)} GB" if c.is_integer() else f"{c} GB"
        except (ValueError, TypeError):
            return str(val)
    if spec_key == 'type':
        s = str(val).strip()
        if s.isdigit():
            return f"{s} RPM"
        return s
    if spec_key == 'speed':
        if isinstance(val, (list, tuple)) and len(val) == 2:
            return f"DDR{val[0]}-{val[1]}"
        if isinstance(val, str) and ',' in val:
            parts = val.split(',')
            return f"DDR{parts[0].strip()}-{parts[1].strip()}"
        return str(val)
    return str(val)


def raw_spec_value(spec_key: str, val: Any) -> str:
    """Convierte el valor de una especificación en un string para el parámetro GET."""
    if val is None:
        return ''
    if spec_key == 'speed':
        if isinstance(val, (list, tuple)) and len(val) == 2:
            return f"{val[0]},{val[1]}"
        return str(val)
    if spec_key == 'capacity':
        try:
            c = float(val)
            return str(int(c)) if c.is_integer() else str(c)
        except (ValueError, TypeError):
            return str(val)
    return str(val).strip()


def spec_sort_key(spec_key: str, val: Any) -> Tuple[int, Any]:
    """Ordena opciones: números de menor a mayor, marcas y sockets alfabéticamente."""
    if spec_key in ('core_count', 'module_count', 'wattage', 'capacity'):
        try:
            return (0, float(val))
        except (ValueError, TypeError):
            return (1, str(val))
    if spec_key == 'speed':
        try:
            if isinstance(val, (list, tuple)) and len(val) == 2:
                return (0, float(val[0]), float(val[1]))
            if isinstance(val, str) and ',' in val:
                p = val.split(',')
                return (0, float(p[0]), float(p[1]))
        except (ValueError, TypeError):
            pass
    if spec_key == 'gpu_brand':
        order = {'nvidia': 1, 'amd': 2, 'intel': 3}
        return (order.get(str(val).lower(), 4), str(val).lower())
    return (0, str(val).lower())


def extract_spec_filters_from_request(request, category_slug: Optional[str]) -> Dict[str, List[str]]:
    """Extrae los parámetros GET de especificaciones según la categoría actual."""
    if not category_slug or category_slug not in CATEGORY_SPEC_CONFIG:
        return {}

    configs = CATEGORY_SPEC_CONFIG[category_slug]
    selected_specs: Dict[str, List[str]] = {}
    for cfg in configs:
        key = cfg['key']
        vals = request.GET.getlist(key)
        # Filtrar valores vacíos
        cleaned = [v.strip() for v in vals if v and v.strip()]
        if cleaned:
            selected_specs[key] = cleaned
    return selected_specs


def extract_category_spec_definitions(
    category_slug: Optional[str],
    selected_specs: Dict[str, List[str]],
    specs_iterable: Any,
) -> List[Dict[str, Any]]:
    """
    Agrupa las opciones disponibles para la categoría a partir de los specs de sus productos,
    contando las ocurrencias de cada valor e indicando cuáles están seleccionadas.
    """
    if not category_slug or category_slug not in CATEGORY_SPEC_CONFIG:
        return []

    configs = CATEGORY_SPEC_CONFIG[category_slug]
    # Contadores por clave
    counters: Dict[str, Counter] = {cfg['key']: Counter() for cfg in configs}

    for specs in specs_iterable:
        if not specs or not isinstance(specs, dict):
            continue
        for cfg in configs:
            key = cfg['key']
            val = specs.get(key)
            if val in (None, '', []):
                continue
            if key == 'speed' and isinstance(val, (list, tuple)) and len(val) == 2:
                counters[key][f"{val[0]},{val[1]}"] += 1
            else:
                raw_k = raw_spec_value(key, val)
                if raw_k:
                    counters[key][raw_k] += 1

    definitions = []
    for cfg in configs:
        key = cfg['key']
        title = cfg['title']
        key_counter = counters[key]
        if not key_counter:
            continue

        selected_for_key = set(selected_specs.get(key, []))

        # Ordenar las opciones
        sorted_raw_vals = sorted(key_counter.keys(), key=lambda v: spec_sort_key(key, v))

        options = []
        for raw_val in sorted_raw_vals:
            count = key_counter[raw_val]
            label = format_spec_option_label(key, raw_val)
            options.append({
                'raw_value': raw_val,
                'label': label,
                'count': count,
                'is_selected': raw_val in selected_for_key,
            })

        definitions.append({
            'key': key,
            'title': title,
            'options': options,
            'has_active': bool(selected_for_key),
        })

    return definitions


def apply_spec_filters_to_queryset(qs, spec_filters: Dict[str, List[str]]):
    """Aplica filtros de especificaciones JSONField a un QuerySet de Django."""
    if not spec_filters:
        return qs

    for key, values in spec_filters.items():
        if not values:
            continue

        if key == 'speed':
            speed_q = Q()
            for v in values:
                if ',' in v:
                    try:
                        p = [int(x.strip()) for x in v.split(',')]
                        speed_q |= Q(specs__speed=p)
                    except ValueError:
                        speed_q |= Q(specs__speed=v)
                else:
                    speed_q |= Q(specs__speed=v)
            qs = qs.filter(speed_q)

        elif key in ('core_count', 'module_count', 'wattage', 'capacity'):
            # Puede estar almacenado como int, float o str
            candidate_vals = []
            for v in values:
                candidate_vals.append(v)
                try:
                    candidate_vals.append(int(v))
                except (ValueError, TypeError):
                    pass
                try:
                    candidate_vals.append(float(v))
                except (ValueError, TypeError):
                    pass
            qs = qs.filter(**{f'specs__{key}__in': candidate_vals})

        else:
            # Campos de texto (socket, brand, gpu_brand, chipset, form_factor, type, etc.)
            qs = qs.filter(**{f'specs__{key}__in': values})

    return qs


def apply_spec_filters_to_items(items: list, spec_filters: Dict[str, List[str]]) -> list:
    """Filtra una lista de CatalogItem en memoria (para modo fallback CSV)."""
    if not spec_filters:
        return items

    filtered = items
    for key, allowed_vals in spec_filters.items():
        if not allowed_vals:
            continue

        normalized_allowed = set(str(v).strip().lower() for v in allowed_vals)
        numeric_allowed = set()
        for v in allowed_vals:
            try:
                numeric_allowed.add(float(v))
            except (ValueError, TypeError):
                pass

        matched = []
        for item in filtered:
            specs = getattr(item, 'specs', {}) or {}
            val = specs.get(key)
            if val is None:
                continue

            # Comparación para speed lista [5, 6000]
            if key == 'speed':
                if isinstance(val, (list, tuple)) and len(val) == 2:
                    val_str = f"{val[0]},{val[1]}"
                    if val_str in allowed_vals:
                        matched.append(item)
                        continue
                elif str(val) in allowed_vals:
                    matched.append(item)
                    continue

            # Comparación numérica (ej. 2000.0 vs 2000)
            if numeric_allowed:
                try:
                    if float(val) in numeric_allowed:
                        matched.append(item)
                        continue
                except (ValueError, TypeError):
                    pass

            # Comparación de texto
            if str(val).strip().lower() in normalized_allowed:
                matched.append(item)

        filtered = matched

    return filtered
