"""
Consulta concurrente del catálogo: DB (SQLite local / RDS en AWS) + CSV en paralelo.

En local, SQLite actúa como sustituto de RDS. Si la DB falla o se demora,
se usa el resultado de los CSV en CleanedCSV/ para mantener disponibilidad.
"""
from __future__ import annotations

import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import close_old_connections, connection
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify

from category.models import Category
from store.models import Product

PART_CSV_FILES = [
    ('cpu-123.csv', 'cpu', 'Procesadores'),
    ('cpu-cooler-1000.csv', 'cpu-cooler', 'Coolers de CPU'),
    ('motherboard-1000.csv', 'motherboard', 'Placas Madre'),
    ('memory-12345.csv', 'memory', 'Memoria RAM'),
    ('internal-hard-drive-1234.csv', 'internal-hard-drive', 'Almacenamiento'),
    ('video-card-1234.csv', 'video-card', 'Tarjetas de Video'),
    ('case-1000.csv', 'case', 'Gabinetes'),
    ('power-supply-123.csv', 'power-supply', 'Fuentes de Poder'),
]

CSV_BY_SLUG = {slug: (filename, name) for filename, slug, name in PART_CSV_FILES}
SKIP_SPEC_KEYS = {'name', 'price', 'price_available', 'socket_source'}


@dataclass
class CatalogItem:
    """Producto mínimo desde CSV para poder pintar la tienda sin DB."""

    id: Optional[int]
    product_name: str
    slug: str
    price: int
    category_slug: str
    part_type: str
    from_csv: bool = True
    specs: Dict[str, Any] = field(default_factory=dict)
    stock: int = 1
    is_available: bool = True
    description: str = ''

    def get_url(self):
        if self.id is None:
            return '#'
        return reverse('product_detail', args=[self.category_slug, self.slug])

    def get_image_url(self):
        return static('images/pc-part-placeholder.png')

    def get_specs_dict(self):
        return self.specs if isinstance(self.specs, dict) else {}

    @property
    def category(self):
        label = CSV_BY_SLUG.get(self.category_slug, ('', 'Componente'))[1]
        return SimpleNamespace(category_name=label, slug=self.category_slug)


def _csv_dir() -> Path:
    return Path(getattr(settings, 'CATALOG_CSV_DIR', '') or (Path(settings.BASE_DIR) / 'CleanedCSV'))


def _parse_price(raw) -> int:
    if raw in (None, ''):
        return 0
    try:
        cleaned = str(raw).replace('$', '').replace(',', '').strip()
        return max(0, int(round(float(cleaned))))
    except (TypeError, ValueError):
        return 0


def _parse_csv_spec(raw):
    if raw in (None, ''):
        return None
    if not isinstance(raw, str):
        return raw
    value = raw.strip()
    if not value:
        return None
    lowered = value.lower()
    if lowered in ('true', 'false'):
        return lowered == 'true'
    if (value.startswith('[') and value.endswith(']')) or (value.startswith('{') and value.endswith('}')):
        try:
            return json.loads(value.replace("'", '"'))
        except json.JSONDecodeError:
            return value
    if re.fullmatch(r'-?\d+(?:\.\d+)?(?:\s*,\s*-?\d+(?:\.\d+)?)+', value):
        parsed_values = []
        for part in value.split(','):
            part = part.strip()
            parsed_values.append(float(part) if '.' in part else int(part))
        return parsed_values
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _row_to_specs(row: Dict[str, Any]) -> Dict[str, Any]:
    specs = {}
    for key, raw_value in row.items():
        if key is None or key in SKIP_SPEC_KEYS:
            continue
        parsed = _parse_csv_spec(raw_value)
        if parsed is not None:
            specs[key] = parsed
    return specs


def _row_is_available(row: Dict[str, Any], price: int) -> bool:
    raw = row.get('price_available')
    if raw in (None, ''):
        return price > 0
    return str(raw).strip().lower() in ('true', '1', 'yes')


def _db_engine_label() -> str:
    engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
    if 'postgresql' in engine:
        return 'AWS RDS (PostgreSQL)'
    if 'sqlite' in engine:
        return 'SQLite (sustituto local de RDS)'
    return engine or 'database'


def _query_database(
    category_slug: Optional[str],
    keyword: Optional[str],
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    spec_filters: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    close_old_connections()
    started = time.perf_counter()
    label = _db_engine_label()
    try:
        delay_ms = int(getattr(settings, 'CATALOG_SIMULATE_DB_DELAY_MS', 0) or 0)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        if getattr(settings, 'CATALOG_SIMULATE_DB_FAILURE', False):
            raise RuntimeError('Fallo simulado de la base de datos (demo)')

        from django.db.models import Min, Max
        base_qs = Product.objects.filter(is_available=True).select_related('category')
        if category_slug:
            Category.objects.get(slug=category_slug)
            base_qs = base_qs.filter(category__slug=category_slug)
        if keyword:
            from django.db.models import Q
            base_qs = base_qs.filter(
                Q(description__icontains=keyword) | Q(product_name__icontains=keyword)
            )

        # Límites de precios para la categoría/búsqueda actual (con precio > 0)
        bounds = base_qs.filter(price__gt=0).aggregate(min_p=Min('price'), max_p=Max('price'))
        min_bound = bounds['min_p'] if bounds['min_p'] is not None else 0
        max_bound = bounds['max_p'] if bounds['max_p'] is not None else 0

        # Specs de la categoría para generar dinámicamente las opciones del menú lateral
        category_specs_list = list(base_qs.values_list('specs', flat=True)) if category_slug else []

        qs = base_qs
        if min_price is not None:
            qs = qs.filter(price__gte=min_price)
        if max_price is not None:
            qs = qs.filter(price__lte=max_price)

        if spec_filters:
            from .spec_filters import apply_spec_filters_to_queryset
            qs = apply_spec_filters_to_queryset(qs, spec_filters)

        if keyword:
            qs = qs.order_by('-created_date')
        else:
            qs = qs.order_by('id')

        products = list(qs)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            'ok': True,
            'source': 'database',
            'label': label,
            'products': products,
            'count': len(products),
            'min_bound': min_bound,
            'max_bound': max_bound,
            'category_specs_list': category_specs_list,
            'elapsed_ms': elapsed_ms,
            'error': None,
            'thread': 'db-worker',
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            'ok': False,
            'source': 'database',
            'label': label,
            'products': [],
            'count': 0,
            'min_bound': 0,
            'max_bound': 0,
            'category_specs_list': [],
            'elapsed_ms': elapsed_ms,
            'error': str(exc),
            'thread': 'db-worker',
        }
    finally:
        connection.close()


def _iter_csv_rows(category_slug: Optional[str]):
    csv_dir = _csv_dir()
    files = PART_CSV_FILES
    if category_slug:
        if category_slug not in CSV_BY_SLUG:
            return
        filename, _name = CSV_BY_SLUG[category_slug]
        files = [(filename, category_slug, _name)]

    for filename, slug, _name in files:
        path = csv_dir / filename
        if not path.exists():
            continue
        with path.open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield slug, row


def _query_csv(
    category_slug: Optional[str],
    keyword: Optional[str],
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    spec_filters: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        items: List[CatalogItem] = []
        used_slugs = set()
        needle = (keyword or '').strip().lower()

        for part_slug, row in _iter_csv_rows(category_slug):
            name = (row.get('name') or '').strip()
            if not name:
                continue
            if needle and needle not in name.lower():
                continue
            base = slugify(name)[:240] or 'part'
            slug = base
            suffix = 2
            while slug in used_slugs:
                slug = f'{base}-{suffix}'
                suffix += 1
            used_slugs.add(slug)
            price = _parse_price(row.get('price'))
            items.append(
                CatalogItem(
                    id=None,
                    product_name=name[:255],
                    slug=slug,
                    price=price,
                    category_slug=part_slug,
                    part_type=part_slug,
                    specs=_row_to_specs(row),
                    is_available=_row_is_available(row, price),
                )
            )

        # Available items
        available_items = [item for item in items if item.is_available]
        category_specs_list = [item.specs for item in available_items if getattr(item, 'specs', None)] if category_slug else []

        # Límites de precios para la categoría/búsqueda actual (con precio > 0)
        prices = [item.price for item in available_items if item.price > 0]
        min_bound = min(prices) if prices else 0
        max_bound = max(prices) if prices else 0

        # Filtrar por precio si se especificó
        filtered = available_items
        if min_price is not None:
            filtered = [item for item in filtered if item.price >= min_price]
        if max_price is not None:
            filtered = [item for item in filtered if item.price <= max_price]

        # Filtrar por especificaciones si se especificó
        if spec_filters:
            from .spec_filters import apply_spec_filters_to_items
            filtered = apply_spec_filters_to_items(filtered, spec_filters)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            'ok': True,
            'source': 'csv',
            'label': 'CSV locales (CleanedCSV/)',
            'products': filtered,
            'count': len(filtered),
            'min_bound': min_bound,
            'max_bound': max_bound,
            'category_specs_list': category_specs_list,
            'elapsed_ms': elapsed_ms,
            'error': None,
            'thread': 'csv-worker',
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            'ok': False,
            'source': 'csv',
            'label': 'CSV locales (CleanedCSV/)',
            'products': [],
            'count': 0,
            'min_bound': 0,
            'max_bound': 0,
            'category_specs_list': [],
            'elapsed_ms': elapsed_ms,
            'error': str(exc),
            'thread': 'csv-worker',
        }


def fetch_catalog_concurrent(
    category_slug: Optional[str] = None,
    keyword: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    spec_filters: Optional[Dict[str, List[str]]] = None,
) -> Tuple[list, int, Dict[str, Any], int, int, List[Dict[str, Any]]]:
    """
    Lanza dos hilos en paralelo (DB + CSV) y elige la mejor fuente disponible.

    Preferencia: DB si responde OK; si falla o no llega a tiempo, CSV.
    Retorna: (products, count, trace, min_bound, max_bound, spec_filter_definitions)
    """
    wall_started = time.perf_counter()
    timeout_s = float(getattr(settings, 'CATALOG_DB_TIMEOUT_SECONDS', 3) or 3)
    db_result: Optional[Dict[str, Any]] = None
    csv_result: Optional[Dict[str, Any]] = None
    finish_order: List[str] = []

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='catalog') as pool:
        futures = {
            pool.submit(_query_database, category_slug, keyword, min_price, max_price, spec_filters): 'database',
            pool.submit(_query_csv, category_slug, keyword, min_price, max_price, spec_filters): 'csv',
        }
        try:
            for future in as_completed(futures, timeout=max(timeout_s, 30)):
                kind = futures[future]
                result = future.result()
                finish_order.append(kind)
                if kind == 'database':
                    db_result = result
                else:
                    csv_result = result
        except Exception as exc:
            # Timeout global de as_completed: recolectar lo que ya terminó.
            for future, kind in futures.items():
                if future.done():
                    result = future.result()
                    if kind == 'database':
                        db_result = result
                    else:
                        csv_result = result
                    if kind not in finish_order:
                        finish_order.append(kind)
                else:
                    future.cancel()
            if db_result is None:
                db_result = {
                    'ok': False,
                    'source': 'database',
                    'label': _db_engine_label(),
                    'products': [],
                    'count': 0,
                    'min_bound': 0,
                    'max_bound': 0,
                    'category_specs_list': [],
                    'elapsed_ms': round(timeout_s * 1000, 2),
                    'error': f'Timeout / no respondió a tiempo ({exc})',
                    'thread': 'db-worker',
                }

    if db_result is None:
        db_result = {
            'ok': False,
            'source': 'database',
            'label': _db_engine_label(),
            'products': [],
            'count': 0,
            'min_bound': 0,
            'max_bound': 0,
            'category_specs_list': [],
            'elapsed_ms': 0,
            'error': 'Sin respuesta',
            'thread': 'db-worker',
        }
    if csv_result is None:
        csv_result = {
            'ok': False,
            'source': 'csv',
            'label': 'CSV locales (CleanedCSV/)',
            'products': [],
            'count': 0,
            'min_bound': 0,
            'max_bound': 0,
            'category_specs_list': [],
            'elapsed_ms': 0,
            'error': 'Sin respuesta',
            'thread': 'csv-worker',
        }

    wall_ms = round((time.perf_counter() - wall_started) * 1000, 2)
    sequential_ms = round(db_result['elapsed_ms'] + csv_result['elapsed_ms'], 2)
    saved_ms = max(0, round(sequential_ms - wall_ms, 2))

    if db_result['ok'] and db_result['elapsed_ms'] <= (timeout_s * 1000):
        chosen = db_result
        reason = 'DB respondió correctamente; se usa como fuente principal'
    elif csv_result['ok']:
        chosen = csv_result
        reason = (
            'DB falló o se demoró; se mantiene disponibilidad con CSV local'
            if not db_result['ok']
            else 'DB OK pero se eligió CSV (fallback)'
        )
        if db_result['ok'] and db_result['elapsed_ms'] > (timeout_s * 1000):
            reason = f'DB superó el timeout ({timeout_s}s); se usa CSV local'
    elif db_result['ok']:
        chosen = db_result
        reason = 'CSV no disponible; se usa DB'
    else:
        chosen = csv_result if csv_result['ok'] else db_result
        reason = 'Ambas fuentes fallaron'

    products = chosen.get('products') or []
    count = chosen.get('count') or len(products)
    min_bound = chosen.get('min_bound', 0)
    max_bound = chosen.get('max_bound', 0)

    if min_bound >= max_bound:
        max_bound = min_bound + 100

    from .spec_filters import extract_category_spec_definitions
    spec_filter_definitions = extract_category_spec_definitions(
        category_slug=category_slug,
        selected_specs=spec_filters or {},
        specs_iterable=chosen.get('category_specs_list', []),
    )

    trace = {
        'mode': 'concurrent_threads',
        'category_slug': category_slug,
        'keyword': keyword,
        'min_price': min_price,
        'max_price': max_price,
        'spec_filters': spec_filters,
        'min_bound': min_bound,
        'max_bound': max_bound,
        'wall_clock_ms': wall_ms,
        'sequential_estimate_ms': sequential_ms,
        'latency_saved_ms': saved_ms,
        'db_timeout_seconds': timeout_s,
        'finish_order': finish_order,
        'chosen_source': chosen['source'],
        'chosen_label': chosen['label'],
        'reason': reason,
        'workers': {
            'database': {
                'ok': db_result['ok'],
                'label': db_result['label'],
                'count': db_result['count'],
                'elapsed_ms': db_result['elapsed_ms'],
                'error': db_result['error'],
                'thread': db_result['thread'],
            },
            'csv': {
                'ok': csv_result['ok'],
                'label': csv_result['label'],
                'count': csv_result['count'],
                'elapsed_ms': csv_result['elapsed_ms'],
                'error': csv_result['error'],
                'thread': csv_result['thread'],
            },
        },
        'note': (
            'Consulta lanzada en 2 hilos en paralelo. '
            'Abre F12 → Console para ver este rastro de demo.'
        ),
    }
    return products, count, trace, min_bound, max_bound, spec_filter_definitions
