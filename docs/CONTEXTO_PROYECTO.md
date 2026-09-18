====================================================================
DOCUMENTACION TECNICA DEL PROYECTO - ECOMMERCE + ASISTENTE DE COMPRAS
====================================================================

Fecha de actualizacion: 2026-09-17
Proyecto: Ecommerce de componentes de PC
Ubicacion actual: C:\Users\divad\Documents\Proyectos\ecommerce
Rama de trabajo actual: CleanData

--------------------------------------------------------------------
1. RESUMEN DEL PROYECTO
--------------------------------------------------------------------

Este proyecto es una tienda ecommerce orientada a la venta de componentes de PC (CPU, GPU, RAM, SSD, motherboard, fuentes, gabinetes, monitores, etc.).

Ademas se desarrollo una primera fase de un asistente de compras, cuyo objetivo es ayudar al usuario a seleccionar productos recomendados en funcion de:
- presupuesto
- caso de uso (gaming, trabajo, estudio, streaming)
- categoria de producto (opcional)

El proyecto se construyo en Django y usa SQLite para el entorno local. La base de datos y los modelos estan pensados para soportar una tienda real con catalogo de productos, carrito, ordenes, usuarios y un sistema de asistente inteligente de recomendacion.

El objetivo principal de esta documentacion es dejar un estado claro del proyecto para que pueda ser movido a otra ubicacion y entregado a una nueva sesion de trabajo, de modo que un agente IA pueda entender exactamente que se hizo, que falta, y continuar desde el punto en que quedamos.

--------------------------------------------------------------------
2. ESTADO ACTUAL DEL PROYECTO
--------------------------------------------------------------------

El proyecto ya cuenta con lo siguiente:

2.1 Estructura base de la tienda
- App accounts
- App carts
- App category
- App orders
- App store
- App assistant
- templates del proyecto
- modelo Product con campos basicos: nombre, slug, descripcion, precio, stock, categoria, part_type, specs, etc.

2.2 Catalogo de productos
- La rama `CleanData` utiliza el catalogo limpio ubicado en `CleanedCSV/`.
- `store/catalog_concurrent.py` consulta la base de datos y los CSV locales para mantener disponible la tienda si la base esta vacia o falla.
- El catalogo local incluye archivos para CPU, CPU cooler, motherboard, memoria, almacenamiento interno, tarjeta de video, gabinete y fuente de poder.
- El asistente puede leer directamente los CSV cuando no existen productos en la base de datos.

2.3 Navegacion principal y tienda
- La tienda tiene navegacion por categorias y listado de productos.
- La home muestra componentes destacados.
- El navbar tiene acceso a la tienda y al asistente.

2.4 Primera fase del asistente
Se desarrollo una primera fase funcional del asistente de compras con los siguientes elementos:
- formulario para seleccionar:
  * caso de uso
  * presupuesto
  * categoria opcional
- logica de recomendacion por score
- ordenamiento de productos por afinidad con el caso de uso
- recomendaciones mostradas en pantalla con nombre, precio, categoria y descripcion de uso
- pagina dedicada /assistant/
- acceso visible desde la navegacion principal
- pruebas de Django para validar la vista y el flujo basico
- funciona con productos ORM y con elementos del catalogo CSV de `CleanData`
- devuelve hasta 3 recomendaciones con precio valido

2.5 Compatibilidad y correcciones aplicadas
- La rama `CleanData` mantiene `Product.specs` como `JSONField`; el asistente acepta diccionarios JSON y texto JSON.
- El asistente prioriza productos disponibles de la base de datos; si la base esta vacia, utiliza `CleanedCSV/` sin modificar el catalogo ni sus vistas.
- Se corrigio una duplicacion de `templates/assistant/assistant.html` que provocaba dos bloques `{% block content %}`.
- La app `assistant` esta registrada en `INSTALLED_APPS` y en las URLs principales.

--------------------------------------------------------------------
3. ARQUITECTURA DEL PROYECTO
--------------------------------------------------------------------

3.1 Apps principales

- accounts
  Funcionalidad de usuarios y perfil.

- store
  Modelos, vistas, catalogo y gestion de productos.

- carts
  Carrito de compras.

- category
  Categorias y menu links para la navegacion.

- orders
  Gestion de compras y ordenes.

- assistant
  Nueva app para el asistente de compras.

3.2 Archivos relevantes

- ecommerce/settings.py
  Configuracion global del proyecto, apps instaladas, base de datos y variables de entorno.

- ecommerce/urls.py
  Rutas principales del proyecto.

- templates/base.html
  Layout principal.

- templates/includes/navbar.html
  Navegacion general del sitio.

- templates/home.html
  Inicio del sitio.

- templates/assistant/assistant.html
  Vista del asistente.

- assistant/forms.py
  Formulario del asistente.

- assistant/views.py
  Logica de recomendacion.

- assistant/urls.py
  Rutas del asistente.

- store/models.py
  Modelos del catalogo y propiedades de productos.

- store/management/commands/import_pc_parts.py
  Comando para importar el catalogo desde CSV.

- store/catalog_concurrent.py
  Lectura concurrente de base de datos y catalogo CSV limpio; define los slugs y archivos usados por `CleanData`.

--------------------------------------------------------------------
4. FLUJO ACTUAL DEL ASISTENTE
--------------------------------------------------------------------

El asistente actualmente sigue una logica simple pero funcional:

1. El usuario entra a /assistant/
2. El formulario solicita:
   - necesidad principal
   - presupuesto
   - categoria (opcional)
3. La vista recibe esos parametros con request.GET.
4. Se seleccionan productos ORM disponibles; si no hay productos, se leen los CSV de `CleanedCSV/`.
5. Se ejecuta una recomendacion basada en disparadores clave para cada caso de uso.
6. Se scorea cada producto con una formula simple que toma en cuenta:
   - distancia del precio al presupuesto
   - categoria seleccionada
   - coincidencias con palabras clave por caso de uso
   - disponibilidad del producto
   - rango de precios razonable
7. Se filtran precios validos y se ordenan los productos por score.
8. Se devuelven las mejores 3 opciones para mostrar en la interfaz.

La recomendacion actual no es una IA generativa ni un agente conversacional completo; es una primera fase basada en reglas y ranking por proximidad de preferencias.

--------------------------------------------------------------------
5. REGLAS DE NEGOCIO Y LOGICA DEL ASISTENTE
--------------------------------------------------------------------

Casos soportados en la primera fase:
- gaming
- trabajo
- estudio
- streaming

Categorias principales contempladas en el ranking:
- cpu
- video-card
- motherboard
- memory
- monitor
- power-supply
- case
- internal-hard-drive (almacenamiento en `CleanData`)

Keywords de ejemplo:
- gaming: rtx, gtx, fps, gaming, nvidia, amd, rgb
- trabajo: office, productivity, stable, efficient
- estudio: office, student, budget, compact
- streaming: streaming, creator, 4k, encoders

El score considera un equilibrio entre:
- presupuesto
- categoria
- uso
- disponibilidad
- palabras clave relevantes

--------------------------------------------------------------------
6. COMANDOS IMPORTANTES PARA DESARROLLAR Y PROBAR
--------------------------------------------------------------------

Para levantar el proyecto localmente desde la raiz del proyecto:

1. Activar entorno virtual
  .\venv\Scripts\Activate.ps1

2. Instalar dependencias (si es necesario)
   python -m pip install -r requirements.txt

3. Ejecutar migraciones
   python manage.py migrate

4. Confirmar que exista el catalogo limpio en `CleanedCSV/`.
  La rama `CleanData` puede mostrarlo sin cargar productos en SQLite.

5. Ejecutar servidor local
   python manage.py runserver

6. Abrir en navegador
   http://127.0.0.1:8000/
   http://127.0.0.1:8000/assistant/

7. Ejecutar pruebas del asistente
   python manage.py test assistant

8. Validar Django
   python manage.py check

--------------------------------------------------------------------
7. PROBLEMAS CONOCIDOS Y SOLUCIONES
--------------------------------------------------------------------

7.1 Compatibilidad de `specs`
Descripcion:
- `CleanData` conserva `JSONField` en el modelo `Product`, mientras que otra variante del proyecto usaba texto JSON.

Solucion aplicada:
- El asistente acepta ambos formatos al construir el texto usado por el scoring.

7.2 Entorno Python
Descripcion:
- El proyecto original estaba usando Python 3.7 y luego se detecto que requiere compatibilidad con Django 3.2 y dependencias del stack.

Solucion recomendada:
- Usar Python 3.10 para desarrollo local y compatibilidad con deps.
- Python 3.14 puede fallar con algunos paquetes legacy sin ajuste adicional.

7.3 Base de datos vacia
Descripcion:
- La base SQLite local de `CleanData` puede estar vacia porque la tienda usa archivos CSV limpios como fallback.

Solucion:
- Verificar que exista la carpeta `CleanedCSV/` con los archivos esperados.
- Si se desea usar ORM, ejecutar las migraciones y cargar productos mediante el mecanismo de importacion disponible en la rama.

--------------------------------------------------------------------
8. PLANES DE DESARROLLO FUTUROS
--------------------------------------------------------------------

Los siguientes planes fueron discutidos durante las sesiones de trabajo. El objetivo es continuar desde la primera fase y ampliar el asistente a un sistema mas potente.

8.1 Segunda fase: asistente modular y conversacional
- Crear una experiencia de chat para el asistente
- Permitir que el usuario hable con el sistema de forma natural
- Convertir las preguntas en contexto del presupuesto, uso y preferencias
- Aprender los gustos del usuario con el tiempo

8.2 Tercera fase: recomendacion de configuraciones completas
- En lugar de recomendar productos individuales, armar builds completos
- Relacionar CPU + motherboard + RAM + GPU + almacenamiento + fuente + gabinete
- Validar compatibilidad entre componentes
- Proponer combinaciones por rango de presupuesto

8.3 Cuarta fase: integracion con perfil de usuario y historial
- Guardar preferencias del usuario
- Seguir historial de busquedas y compras
- Personalizar recomendaciones por comportamiento
- Crear sesiones y sugerencias continuas

8.4 Quinta fase: analisis inteligente de productos
- Analizar especificaciones tecnicas
- Comparar productos por rendimiento y precio
- Mostrar recomendaciones con justificacion tecnica clara
- Identificar mejores opciones por categoria y caso de uso

8.5 Sexta fase: integracion de IA embebida
- Permitir inferencia de contexto por lenguaje natural
- Asociar preguntas con el catalogo existente
- Generar respuestas estructuradas y faciles de entender
- Mejorar la experiencia del asistente con recomendaciones mas humanas

8.6 Septima fase: conversion comercial y merchandising
- Hacer que el asistente recomiende no solo por rendimiento sino por conversion
- Priorizar productos con mejor margen o disponibilidad
- Mostrar promociones, bundles y ofertas
- Integrar recomendaciones en la home y la tienda

8.7 Octava fase: mejora de frontend y UX
- Mejorar el diseño de la vista assistant
- Añadir cards, carga animada, filtros interactivos, mensajes visuales
- Implementar dashboard inteligente de configuracion recomendada
- Mejorar la experiencia mobile

8.8 Novena fase: analisis y metricas
- Medir clicks, recomendaciones aceptadas y conversiones
- Registrar interacciones del usuario con el asistente
- Evaluar que tan efectiva es la recomendacion
- AJustar score y reglas con datos reales

--------------------------------------------------------------------
9. RECOMENDACIONES PARA CONTINUAR EL PROYECTO EN OTRA SESION
--------------------------------------------------------------------

Para continuar en otra ubicacion o con otra sesion de trabajo, este es el procedimiento recomendado:

1. Mover la carpeta del proyecto a la nueva ubicacion sin romper rutas relativas.
2. Crear o activar el entorno virtual con Python 3.10.
3. Instalar requirements.txt.
4. Copiar el archivo .env si se requiere continuidad del entorno local.
5. Ejecutar `python manage.py migrate`.
6. Confirmar que `CleanedCSV/` este disponible; no es obligatorio poblar SQLite para probar la tienda y el asistente.
7. Ejecutar `python manage.py check` y `python manage.py test assistant`.
8. Revisar la app assistant y confirmar que no haya dependencias rotas.
9. Continuar con la fase 2 del asistente, priorizando un chat conversacional y configuraciones full build.

--------------------------------------------------------------------
10. PUNTOS CRITICOS PARA EL AGENTE IA QUE CONTINUA EL PROYECTO
--------------------------------------------------------------------

Un agente IA que tome este proyecto debe tener en cuenta lo siguiente:

- La app principal es ecommerce con catalogo de PC parts.
- La base se compone de productos por categoria y un sistema de tienda.
- El asistente es una primera fase basada en reglas y ranking.
- El sistema no es totalmente conversacional aun.
- El asistente necesita datos reales en SQLite o archivos validos en `CleanedCSV/` para funcionar.
- En `CleanData`, el modelo `Product` usa `JSONField` para `specs`; el asistente tambien tolera texto JSON.
- La rama `CleanData` usa `store/catalog_concurrent.py` para la disponibilidad del catalogo y no debe recibir cambios de catalogo de `AsisTest`.
- El proyecto necesita Python 3.10 para compatibilidad estable.
- El flujo principal de recomendacion se encuentra en assistant/views.py.
- La fuente principal del catalogo limpio esta en `CleanedCSV/` y su lector esta en `store/catalog_concurrent.py`.
- `store/management/commands/import_pc_parts.py` pertenece a otra variante del flujo y no debe asumirse como requisito para probar `CleanData`.
- La app assistant tiene pruebas basicas y debe mantenerse con pruebas cada vez que se amplie la funcionalidad.

--------------------------------------------------------------------
11. CONCLUSIONES
--------------------------------------------------------------------

El proyecto ya tiene una base solida para una tienda ecommerce especializada en componentes de PC y una primera fase funcional de asistente de compras. El trabajo realizado sirve como base para una evolucion hacia un asistente inteligente, conversacional y orientado a configuraciones completas.

La clave del proyecto es que el asistente no solo recomienda productos a lo loco, sino que analiza presupuesto, uso y categoria para devolver sugerencias con sentido. Este enfoque deja una base muy clara para continuar con un sistema mas avanzado de IA, personalizacion y analisis de compatibilidad.

La documentacion actual debe permitir que, al mover el proyecto a otra ubicacion y entregar la carpeta a una nueva sesion, el agente sepa exactamente:
- que se hizo
- que funciona
- que falta por hacer
- que decisiones de arquitectura se tomaron
- y por donde continuar el desarrollo

--------------------------------------------------------------------
FIN DE LA DOCUMENTACION
--------------------------------------------------------------------
