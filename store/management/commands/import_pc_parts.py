import csv
import json
import re
import urllib.request
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from category.models import Category
from store.models import Product


DATASET_ZIP_URL = 'https://github.com/docyx/pc-part-dataset/raw/main/data/csv.zip'
PLACEHOLDER_NAME = 'photos/products/pc-part-placeholder.png'

PART_CATEGORIES = [
    ('cpu.csv', 'cpu', 'Procesadores', 'CPUs y procesadores'),
    ('cpu-cooler.csv', 'cpu-cooler', 'Coolers de CPU', 'Disipadores y refrigeracion liquida'),
    ('motherboard.csv', 'motherboard', 'Placas Madre', 'Motherboards'),
    ('memory.csv', 'memory', 'Memoria RAM', 'Memoria DDR'),
    ('internal-hard-drive.csv', 'internal-hard-drive', 'Almacenamiento', 'SSD y discos internos'),
    ('video-card.csv', 'video-card', 'Tarjetas de Video', 'GPUs'),
    ('case.csv', 'case', 'Gabinetes', 'Cases para PC'),
    ('power-supply.csv', 'power-supply', 'Fuentes de Poder', 'PSUs'),
    ('optical-drive.csv', 'optical-drive', 'Unidades Opticas', 'Lectores CD/DVD/Blu-ray'),
    ('os.csv', 'os', 'Sistemas Operativos', 'Licencias de sistema operativo'),
    ('monitor.csv', 'monitor', 'Monitores', 'Pantallas'),
    ('external-hard-drive.csv', 'external-hard-drive', 'Almacenamiento Externo', 'Discos y SSD externos'),
    ('case-accessory.csv', 'case-accessory', 'Accesorios de Gabinete', 'Accesorios para case'),
    ('case-fan.csv', 'case-fan', 'Ventiladores', 'Fans de gabinete'),
    ('fan-controller.csv', 'fan-controller', 'Controladores de Fan', 'Controladores de ventiladores'),
    ('thermal-paste.csv', 'thermal-paste', 'Pasta Termica', 'Compuesto termico'),
    ('ups.csv', 'ups', 'UPS', 'Sistemas de alimentacion ininterrumpida'),
    ('sound-card.csv', 'sound-card', 'Tarjetas de Sonido', 'Sound cards'),
    ('wired-network-card.csv', 'wired-network-card', 'Red Cableada', 'Adaptadores Ethernet'),
    ('wireless-network-card.csv', 'wireless-network-card', 'Red Inalambrica', 'Adaptadores Wi-Fi'),
    ('headphones.csv', 'headphones', 'Auriculares', 'Headphones'),
    ('keyboard.csv', 'keyboard', 'Teclados', 'Keyboards'),
    ('mouse.csv', 'mouse', 'Mouse', 'Mouses y trackballs'),
    ('speakers.csv', 'speakers', 'Parlantes', 'Speakers'),
    ('webcam.csv', 'webcam', 'Webcams', 'Camaras web'),
]


class Command(BaseCommand):
    help = 'Replace store products with the PC Part Dataset CSVs (https://github.com/docyx/pc-part-dataset)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing categories and products before importing',
        )
        parser.add_argument(
            '--csv-dir',
            default='',
            help='Directory with CSV files. If omitted, the dataset zip is downloaded.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Optional per-file row cap (0 = import all rows)',
        )

    def handle(self, *args, **options):
        if Product.objects.exists() and not options['reset']:
            self.stdout.write(self.style.WARNING('Products already exist. Use --reset to replace them.'))
            return

        csv_dir = self._resolve_csv_dir(options['csv_dir'])
        placeholder_path = self._ensure_placeholder()

        if options['reset']:
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write('Existing store data removed.')

        categories = {}
        for _filename, slug, name, description in PART_CATEGORIES:
            categories[slug] = Category.objects.create(
                category_name=name,
                slug=slug,
                description=description,
            )
            self.stdout.write(f'Created category: {name}')

        now = timezone.now()
        used_slugs = set()
        total = 0
        per_file_limit = options['limit'] or None

        for filename, slug, name, _description in PART_CATEGORIES:
            csv_path = csv_dir / filename
            if not csv_path.exists():
                raise CommandError(f'Missing CSV file: {csv_path}')

            products = self._load_products(
                csv_path=csv_path,
                category=categories[slug],
                part_type=slug,
                placeholder_path=placeholder_path,
                used_slugs=used_slugs,
                now=now,
                limit=per_file_limit,
            )
            created = self._bulk_insert(products)
            total += created
            self.stdout.write(f'Imported {created} products from {filename}')

        self.stdout.write(self.style.SUCCESS(f'Imported {total} PC parts.'))

    def _resolve_csv_dir(self, csv_dir):
        if csv_dir:
            path = Path(csv_dir)
            if not path.exists():
                raise CommandError(f'CSV directory not found: {path}')
            return path

        data_dir = Path(settings.BASE_DIR) / 'data' / 'pc-parts'
        csv_path = data_dir / 'csv'
        expected = {item[0] for item in PART_CATEGORIES}
        if csv_path.exists() and expected.issubset({p.name for p in csv_path.glob('*.csv')}):
            return csv_path

        data_dir.mkdir(parents=True, exist_ok=True)
        zip_path = data_dir / 'csv.zip'
        self.stdout.write(f'Downloading PC Part Dataset CSVs from {DATASET_ZIP_URL}')
        request = urllib.request.Request(
            DATASET_ZIP_URL,
            headers={'User-Agent': 'ModularEcommerce-pc-parts-importer'},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                zip_path.write_bytes(response.read())
        except Exception as exc:
            raise CommandError(f'Could not download dataset zip: {exc}') from exc

        with ZipFile(zip_path) as archive:
            archive.extractall(data_dir)

        if not csv_path.exists():
            nested = list(data_dir.rglob('cpu.csv'))
            if nested:
                return nested[0].parent
            raise CommandError('The dataset zip did not contain CSV files.')
        return csv_path

    def _ensure_placeholder(self):
        if not default_storage.exists(PLACEHOLDER_NAME):
            default_storage.save(PLACEHOLDER_NAME, ContentFile(self._placeholder_png()))
        static_dir = Path(settings.BASE_DIR) / 'ecommerce' / 'static' / 'images'
        static_dir.mkdir(parents=True, exist_ok=True)
        static_placeholder = static_dir / 'pc-part-placeholder.png'
        if not static_placeholder.exists():
            static_placeholder.write_bytes(self._placeholder_png())
        return PLACEHOLDER_NAME

    def _placeholder_png(self):
        image = Image.new('RGB', (600, 600), (28, 33, 48))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle([36, 36, 564, 564], radius=24, outline=(80, 140, 230), width=6)
        draw.rectangle([190, 170, 410, 390], outline=(80, 140, 230), width=4)
        for index in range(8):
            y = 198 + index * 22
            draw.line([(210, y), (390, y)], fill=(70, 100, 150), width=2)
        font = self._font(36)
        text = 'PC Part'
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((600 - text_width) / 2, 450), text, fill=(220, 228, 240), font=font)
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def _font(self, size):
        for candidate in (
            Path('C:/Windows/Fonts/arial.ttf'),
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        ):
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
        return ImageFont.load_default()

    def _load_products(self, csv_path, category, part_type, placeholder_path, used_slugs, now, limit):
        products = []
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=1):
                if limit and row_number > limit:
                    break
                name = (row.get('name') or '').strip()
                if not name:
                    continue
                specs = {}
                for key, raw_value in row.items():
                    if key in (None, 'name', 'price'):
                        continue
                    parsed = _parse_spec(raw_value)
                    if parsed is not None:
                        specs[key] = parsed
                products.append(Product(
                    product_name=name[:255],
                    slug=_unique_slug(name, used_slugs),
                    description=_build_description(category.category_name, specs),
                    price=_parse_price(row.get('price')),
                    images=placeholder_path,
                    stock=20,
                    is_available=True,
                    category=category,
                    part_type=part_type,
                    specs=json.dumps(specs, ensure_ascii=False),
                    created_date=now,
                    modified_date=now,
                ))
        return products

    def _bulk_insert(self, products):
        created = 0
        batch_size = 1000
        with transaction.atomic():
            for index in range(0, len(products), batch_size):
                batch = products[index:index + batch_size]
                Product.objects.bulk_create(batch, batch_size=batch_size)
                created += len(batch)
        return created


def _parse_price(raw):
    if raw in (None, ''):
        return 0
    try:
        cleaned = str(raw).replace('$', '').replace(',', '').strip()
        return max(0, int(round(float(cleaned))))
    except (TypeError, ValueError):
        return 0


def _parse_spec(raw):
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


def _unique_slug(name, used_slugs):
    base = slugify(name)[:240] or 'part'
    slug = base
    suffix = 2
    while slug in used_slugs:
        slug = f'{base}-{suffix}'
        suffix += 1
    used_slugs.add(slug)
    return slug


def _build_description(category_name, specs):
    parts = [f'{category_name}.']
    for key, value in specs.items():
        parts.append(f'{key.replace("_", " ").title()}: {_format_spec(value)}')
    return ' '.join(parts)


def _format_spec(value):
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (list, tuple)):
        return ' / '.join(str(item) for item in value)
    return str(value)
