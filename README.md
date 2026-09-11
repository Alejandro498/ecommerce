# Ecommerce de componentes de PC

Tienda en Django con catálogo de piezas de PC (CPUs, placas madre, RAM, GPUs, etc.). Los productos se cargan desde el [PC Part Dataset](https://github.com/docyx/pc-part-dataset).

## Requisitos

- Python 3.10
- pip
- Conexión a internet la primera vez que importes el catálogo (descarga los CSV)

En local se usa SQLite. No hace falta PostgreSQL ni AWS.

## 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd ecommerce
```

## 2. Crear y activar el entorno virtual

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 4. Configurar variables de entorno

Copia el archivo de ejemplo y déjalo en la raíz del proyecto con el nombre `.env`:

**Windows:**

```powershell
copy .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

Para trabajar en local, el `.env` mínimo es:

```
SECRET_KEY=cambia-esto-por-una-clave-secreta
DEBUG=True
USE_AWS=False
```

`USE_AWS=False` guarda estáticos y fotos en disco, y usa SQLite.

El correo (`EMAIL_*`) es opcional para navegar la tienda. Solo hace falta si quieres que el registro envíe el email de verificación.

## 5. Crear la base de datos

```bash
python manage.py migrate
```

## 6. Cargar el catálogo de productos

Esto descarga los CSV del dataset y crea unas 66.000 piezas en 25 categorías. Tarda poco, pero necesita internet.

```bash
python manage.py import_pc_parts --reset
```

`--reset` borra categorías y productos actuales y los reemplaza.

Si ya importaste una vez y los CSV están en `data/pc-parts/`, el comando reutiliza esos archivos.

## 7. Crear un usuario administrador (opcional)

El modelo de usuario pide email, nombre, apellido y username:

```bash
python manage.py createsuperuser
```

El panel de administración no está en `/admin/` (esa ruta es un señuelo). Entra en:

http://127.0.0.1:8000/securelogin/

## 8. Arrancar el servidor

```bash
python manage.py runserver
```

Abre http://127.0.0.1:8000/

| Página | URL |
| --- | --- |
| Inicio | http://127.0.0.1:8000/ |
| Tienda | http://127.0.0.1:8000/store/ |
| Admin | http://127.0.0.1:8000/securelogin/ |

Para detenerlo: `Ctrl+C` en la terminal.

## Comandos útiles

```bash
# Volver a cargar todo el catálogo
python manage.py import_pc_parts --reset

# Importar solo unas filas por categoría (pruebas rápidas)
python manage.py import_pc_parts --reset --limit 20
```

## Notas

- El dataset no incluye fotos de producto; se usa una imagen genérica.
- Los precios vienen en USD. Si PCPartPicker no publicó precio, se muestra “Consultar precio”.
- Con `USE_AWS=True` hace falta configurar `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_STORAGE_BUCKET_NAME`, y reiniciar el servidor.
- `db.sqlite3`, `.env` y `venv/` no se suben al repositorio.
