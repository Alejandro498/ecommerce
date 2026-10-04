====================================================================
DOCUMENTACION TECNICA DEL PROYECTO - ECOMMERCE + ASISTENTE DE COMPRAS
====================================================================

Fecha de actualizacion: 2026-09-18
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
- logica de recomendacion por score (precio + specs + keywords)
- pool limitado: no scorea todo el catalogo, solo candidatos cerca del presupuesto
- ordenamiento de productos por afinidad con el caso de uso
- recomendaciones mostradas en pantalla con nombre, precio, categoria, score y motivo
- pagina dedicada /assistant/
- acceso visible desde la navegacion principal
- pruebas de Django para validar la vista, el pool, specs y casos de uso
- funciona con productos ORM y con elementos del catalogo CSV de `CleanData`
- devuelve hasta 3 recomendaciones con precio valido y stock disponible

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

El asistente actualmente sigue una logica de ranking por reglas (no es IA generativa):

1. El usuario entra a /assistant/
2. El formulario solicita:
   - necesidad principal (gaming, trabajo, estudio, streaming)
   - presupuesto en MXN
   - categoria (opcional)
3. Si no hay filtros, usa defaults: gaming, 15000 MXN, cualquier categoria.
4. La vista recibe esos parametros con request.GET.
5. Se arma un pool de candidatos (maximo 200), no se evalua todo el catalogo:
   - prioriza productos ORM disponibles (is_available, stock > 0, price > 0)
   - si la base esta vacia, lee los CSV de `CleanedCSV/`
   - si hay categoria, solo esa; si no, un subconjunto por caso de uso
     (gaming: GPU, CPU, RAM, motherboard; trabajo: CPU, RAM, storage, motherboard;
      estudio: CPU, RAM, storage; streaming: GPU, CPU, RAM, storage)
   - busca primero productos entre 50% y 125% del presupuesto; si no hay, abre
     el rango (30-160%, 15-200%, y al final sin tope)
   - dentro de la banda, ordena por cercania al presupuesto y corta en 200
6. Cada candidato recibe un score:
   score = precio + specs de la categoria + keywords del caso de uso
7. Se ordenan de mayor a menor score y se devuelven las mejores 3 (TOP_N).
8. La tarjeta muestra nombre, precio, categoria, score y un motivo breve
   (hasta 3 razones: chipset, VRAM, núcleos, cerca del presupuesto, etc.).

La recomendacion actual no es una IA generativa ni un agente conversacional completo; es una primera fase basada en reglas y ranking por proximidad de preferencias.

--------------------------------------------------------------------
5. REGLAS DE NEGOCIO Y LOGICA DEL ASISTENTE
--------------------------------------------------------------------

Casos soportados en la primera fase:
- gaming
- trabajo
- estudio
- streaming

Sin categoria elegida, no se mezcla todo el catalogo. Cada uso tiene categorias fijas
(`USE_CASE_CATEGORIES` en assistant/views.py):
- gaming: video-card, cpu, memory, motherboard
- trabajo: cpu, memory, internal-hard-drive, motherboard
- estudio: cpu, memory, internal-hard-drive
- streaming: video-card, cpu, memory, internal-hard-drive

PSU, gabinete y cooler solo entran si el usuario elige esa categoria a mano.
Monitor no forma parte del ranking actual.

El score de cada producto es la suma de tres partes:

1. Precio
   Campana alrededor del presupuesto (hasta ~320 puntos). Premia estar cerca
   del monto y da un bonus si no se pasa mas de 15%. No elige "el mas barato".

2. Specs (el peso mas grande; cambia con el uso)
   - GPU: RTX/GTX/Radeon, VRAM, workstation vs gamer
   - CPU: nucleos, boost, X3D, TDP, i5 vs i9 segun el uso
   - RAM: GB totales y DDR4/DDR5
   - Storage: NVMe/SSD y capacidad
   - Motherboard / PSU / case / cooler: chipset, watts, airflow, radiador, tamaño
   El mismo producto cambia de ranking segun el caso de uso
   (ejemplo: 7800X3D gana en gaming; i5 de bajo TDP gana en estudio).

3. Keywords (+35 por coincidencia, con limites de palabra)
   - gaming: rtx, gtx, radeon, geforce, nvidia, amd, x3d, ddr5, nvme, ssd, gaming
   - trabajo: quadro, workstation, creator, i7, i9, ecc, nvme
   - estudio: i5, ryzen, micro, budget, compact, ssd
   - streaming: rtx, nvenc, creator, ryzen, i7, i9, ddr5, nvme

El top 3 es simplemente los 3 scores mas altos. No hay diversidad forzada:
pueden salir tres productos de la misma categoria.

El asistente no arma una PC completa ni valida compatibilidad
(socket, DDR, wattage vs GPU). Eso queda para fases futuras.

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

--------------------------------------------------------------------
12. COMO FUNCIONA EL ASISTENTE AHORA (MAMDANI + GENETICO)
--------------------------------------------------------------------

Esta seccion describe el asistente que esta en produccion en el codigo
actual. Sustituye, para la pagina /assistant/, la primera fase de ranking
de piezas sueltas descrita en las secciones 4 y 5. El formulario ya no
pide categoria: arma una PC completa.

Archivos:

- assistant/forms.py
  Uso (gaming, trabajo, estudio, streaming) y presupuesto en MXN.
- assistant/views.py
  La vista assistant() llama a recommend_builds.
- assistant/mamdani.py
  Inferencia Mamdani: pesos de prioridad por pieza.
- assistant/quality_mamdani.py
  Segundo Mamdani: adecuacion 0-100 de una pieza concreta para el uso.
- assistant/fuzzy.py
  Score Sugeno de la primera fase (piezas sueltas). El armado de PCs ya no lo usa.
- assistant/compatibility.py
  Filtro de socket, energia y tamano. Corre antes de la aptitud.
- assistant/genetic.py
  Cromosoma, ruleta, cruce, mutacion y busqueda.
- templates/assistant/assistant.html
  Muestra los pesos y hasta tres configuraciones.

Si el usuario abre /assistant/ sin enviar el formulario, los defaults son
gaming y 15000 MXN.

Parametros de la busqueda (assistant/genetic.py):

- poblacion: 20
- generaciones: 12
- elitismo: 2
- probabilidad de mutacion: 0.35
- tope de candidatos por pieza: 36
- tope duro de precio de la build: 1.12 veces el presupuesto

--------------------------------------------------------------------
12.1 PROCEDIMIENTO, DE LA PANTALLA A LA RESPUESTA
--------------------------------------------------------------------

1. Leer el formulario.
   Uso y presupuesto. No hay categoria, porque el resultado es la PC
   entera de ocho piezas.

2. Mamdani (assistant/mamdani.py, infer_priorities).
   El presupuesto se difumina en bajo, medio, alto y muy alto.
   El uso queda en el conjunto que el usuario eligio, con pertenencia 1.
   Las reglas if-then asignan a cada pieza un conjunto de salida
   (Muy baja, Baja, Media, Alta, Muy alta). La defuzzificacion es el
   centroide. Sale un numero de 0 a 100 y una etiqueta por pieza.

3. Repartir el presupuesto.
   El peso de cada pieza se eleva al cuadrado para que "Muy alta" se
   lleve mucho mas dinero que "Muy baja". Esos cuadrados, normalizados,
   son la parte del presupuesto que le toca a cada gen.

4. Armar el catalogo de cada gen.
   Si la base tiene al menos un producto con precio y stock en las ocho
   categorias, se usa la base. Si falta alguna, se usan los CSV de
   CleanedCSV/. Cada pieza tiene un tope de precio respecto al
   presupuesto (GPU 58 %, CPU 42 %, motherboard 32 %, RAM 28 %,
   almacenamiento 28 %, fuente 24 %, gabinete 22 %, cooler 18 %).
   De lo que queda se conservan unas 36 opciones: en cada banda de
   precio, las de mejor spec para el uso.

5. Crear la poblacion.
   Cada individuo es un cromosoma de ocho genes, en este orden:
   CPU, GPU, RAM, motherboard, almacenamiento, fuente, gabinete, cooler.
   Se construye en orden de dependencia (CPU, luego placa del mismo
   socket, luego gabinete que acepte la placa, RAM compatible, GPU que
   quepa, fuente que cubra los watts, cooler que quepa y alcance el TDP,
   disco). Al elegir cada pieza se reserva el precio minimo de las que
   faltan, para no gastar el presupuesto antes de terminar la PC.

6. Filtro fuerte, antes de la aptitud.
   diagnose() en assistant/compatibility.py. Si falla, la aptitud es 0
   y la ruleta no puede elegir esa PC. El cruce que deja una PC rota
   intenta repararse; si no puede, se copia el padre.

7. Aptitud, solo de las compatibles.
   80 % calidad de las piezas. Esa calidad es el segundo Mamdani
   (assistant/quality_mamdani.py): specs de la pieza y el uso, reglas
   if-then, centroide de 0 a 100. Se multiplica por el peso de prioridad
   al cuadrado.
   20 % cercania del total al presupuesto, penalizando pasarse.

8. Doce generaciones.
   Las dos mejores pasan directo. El resto nace por ruleta, cruce
   uniforme y mutacion. La mutacion solo acepta un reemplazo que siga
   siendo compatible y no pase el tope de precio.

9. Respuesta.
   Se quitan duplicados, se prefieren las que cuestan como maximo el
   presupuesto, y se muestran hasta tres. La pagina lista los pesos
   Mamdani y, por configuracion, las ocho piezas, el total, la aptitud
   y el resumen de compatibilidad.

--------------------------------------------------------------------
12.2 LOGICA DIFUSA: DOS CAPAS
--------------------------------------------------------------------

Capa 1, Mamdani de prioridades (assistant/mamdani.py): reparte la
importancia y el dinero de cada tipo de pieza.
Capa 2, Mamdani de adecuacion (assistant/quality_mamdani.py): mide que
tan buena es una pieza concreta para el uso. El genetico combina las
dos. La primera no elige el modelo. La segunda puntua el modelo.

Membresias de entrada del presupuesto (MXN):

- bajo:      trapezoide, pleno de 0 a 8000, cae a 0 en 18000
- medio:     triangulo 12000, 25000, 45000
- alto:      triangulo 35000, 60000, 100000
- muy alto:  trapezoide, sube desde 75000, pleno desde 110000

El uso no se escribe en lenguaje natural. El usuario elige uno de los
cuatro casos y ese caso tiene pertenencia 1. Los otros tienen 0.

Membresias de salida, universo 0 a 100:

- Muy baja:  trapezoide, pleno de 0 a 10, cae a 0 en 30
- Baja:      triangulo 15, 32, 48
- Media:     triangulo 38, 50, 66
- Alta:      triangulo 55, 72, 88
- Muy alta:  trapezoide, sube desde 72, pleno de 88 a 100

Reglas. Hay una tabla por uso, por termino de presupuesto y por pieza
(_PRIORITY_TABLE en assistant/mamdani.py). Ejemplos de gaming:

- presupuesto bajo:  GPU Muy alta, CPU Alta, almacenamiento Muy baja
- presupuesto medio: GPU Muy alta, CPU Alta, almacenamiento Baja
- presupuesto alto:  GPU Muy alta, CPU Muy alta, fuente Muy alta

Trabajo empuja CPU y RAM a Muy alta y deja la GPU en Baja o Media.
Estudio deja la GPU en Muy baja. Streaming sube CPU y GPU juntas.

Inferencia de una pieza:

1. Se mide la pertenencia del presupuesto a bajo, medio, alto y muy alto.
2. Cada termino con pertenencia mayor que 0 dispara su regla. La fuerza
   de la regla es esa pertenencia. El uso ya esta fijo, asi que el AND
   no la baja mas.
3. El consecuente (por ejemplo Muy alta) se recorta a la altura de la
   fuerza. Si dos reglas disparan el mismo consecuente, se queda la
   fuerza mayor. Si disparan consecuentes distintos, las curvas
   recortadas se unen con el maximo punto a punto. Eso es la agregacion
   Mamdani.
4. Centroide: suma(x * pertenencia(x)) / suma(pertenencia(x)), con x
   de 0 a 100.
5. La etiqueta es el conjunto de salida con mayor pertenencia en ese
   centroide.

Capa 2, segundo Mamdani (component_quality en assistant/quality_mamdani.py).
Para una pieza ya candidata fuzzifica sus specs y dispara reglas if-then
segun el uso. La salida usa los mismos conjuntos Muy baja ... Muy alta y
el mismo centroide. El numero queda entre 0 y 100.

Entradas por pieza:

- GPU: VRAM (baja, media, alta) y clase (bajo, medio, alto, trabajo).
  En gaming un RTX con VRAM media o alta da Muy alta. Una GT de 2 GB da
  Baja. En estudio se invierte: la GPU ligera sube y la GPU grande baja.
- CPU: nucleos (bajos, medios, altos), boost, TDP y si el nombre es X3D
  o de gama alta. En gaming pocos nucleos da Baja. En trabajo muchos
  nucleos da Muy alta.
- RAM: GB (baja, media, alta) y DDR5. En gaming y trabajo 32 GB da Muy
  alta. En estudio 16 GB da Muy alta y 32 GB solo Media.
- Almacenamiento: NVMe, SSD o HDD, y capacidad. En gaming un HDD da Muy
  baja y un NVMe da Alta o Muy alta.
- Fuente: watts contra un objetivo del uso (estudio 500, gaming 650,
  streaming 750) y eficiencia gold o mejor.
- Motherboard: chipset de gama reciente y memoria maxima.
- Gabinete: airflow o mesh. En estudio pesa mas el formato compacto.
- Cooler: aire o radiador grande. En estudio el aire puntua mas que un
  AIO grande.

El precio de la pieza no entra en este Mamdani. Que el total quepa en el
presupuesto se decide en la aptitud del genetico, para que una pieza mala
pero barata no le gane a una pieza buena para el uso.

--------------------------------------------------------------------
12.3 FILTRO DE COMPATIBILIDAD
--------------------------------------------------------------------

diagnose() revisa la build completa y devuelve codigos. Lista vacia
significa que pasa. Los codigos son:

- socket: el socket del CPU y el de la placa tienen que existir y ser
  iguales.
- ram: generacion DDR permitida por el socket (AM5 y LGA1851 solo DDR5,
  AM4 y LGA1151 solo DDR4, LGA1700 acepta DDR4 o DDR5), numero de
  modulos menor o igual a los slots, y GB totales menores o iguales al
  maximo de la placa.
- form_factor: el formato de la placa tiene que caber en el maximo del
  gabinete. Orden de menor a mayor: Mini ITX, Micro ATX, ATX, EATX,
  XL ATX. Uno mas chico cabe en uno mas grande.
- gpu_size: el largo de la GPU (si el CSV no trae largo, se asume
  250 mm) no puede pasar el claro del gabinete. El claro se estima por
  el tipo: desktop, slim y HTPC unos 205 mm; mini tower unos 280 mm;
  mid tower unos 370 mm; full tower unos 430 mm.
- cooler: un aire no trae radiador y se estima en unos 200 W. Un AIO
  trae radiador (120, 240, 280, 360, 420) y tiene que caber en el claro
  del gabinete. La capacidad estimada del cooler tiene que cubrir el
  TDP del CPU.
- power: watts de la fuente >= TDP del CPU + TDP estimado de la GPU
  + 100 W de margen. El TDP de la GPU no viene en el CSV; se estima por
  el nombre del chipset (por ejemplo una 3060 ronda 170 W, una 4090
  ronda 450 W).

El almacenamiento no tiene restriccion fisica en este catalogo: la
placa no trae conteo de ranuras M.2.

--------------------------------------------------------------------
12.4 ALGORITMO GENETICO
--------------------------------------------------------------------

Cromosoma. Ocho genes, un producto cada uno:

    Gen 1 CPU
    Gen 2 GPU
    Gen 3 RAM
    Gen 4 motherboard
    Gen 5 almacenamiento
    Gen 6 fuente
    Gen 7 gabinete
    Gen 8 cooler

Seleccion por ruleta. Se suman las aptitudes mayores que 0. Se sortea
un numero entre 0 y esa suma. Cada individuo ocupa un tramo tan largo
como su aptitud. Los de aptitud 0 no ocupan tramo. El torneo (k = 3)
esta implementado en tournament_select y no es el que corre la pagina.
La pagina usa ruleta.

Cruce uniforme. Para cada gen, el hijo lo copia del padre A o del padre
B con probabilidad 0.5. Es el intercambio de componentes entre dos
configuraciones. Despues del cruce se vuelve a correr el filtro. Si la
mezcla dejo sockets o tamanos incompatibles, _repair cambia la pieza
conflictiva por otra del pool que restaure la compatibilidad. Si no
puede, el hijo se reemplaza por el padre.

Mutacion. Con probabilidad 0.35 se elige un gen al azar y se prueba
hasta diez reemplazos del mismo tipo. Solo se acepta el que deje la
build compatible y dentro del tope de precio. Si ninguno sirve, el gen
no cambia.

Elitismo. Las dos mejores de la generacion pasan intactas a la
siguiente. Los otros 18 lugares son hijos.

Aptitud, en una build que ya paso el filtro:

    peso_i = (prioridad_i) ^ 2
    calidad_i = adecuacion_mamdani_i / 100
    si el precio de la pieza pasa 1.65 veces su parte del presupuesto,
        calidad_i se reduce en proporcion
    si la prioridad es alta (60 o mas) y la pieza cuesta menos de 0.35
        de su parte, tambien se reduce, para no elegir un Celeron
        cuando el peso pedia gastar en CPU
    calidad = suma(peso_i * calidad_i) / suma(peso_i)

    ratio = total / presupuesto
    si ratio > 1, el termino de precio cae rapido
    si ratio < 0.62, tambien baja, por quedarse corta
    si no, premia acercarse a 0.97

    aptitud = 100 * (0.80 * calidad + 0.20 * precio)

Al cerrar las 12 generaciones se ordena por aptitud. Si hay builds que
no se pasan del presupuesto, esas salen primero. Se devuelven como
maximo tres distintas.

--------------------------------------------------------------------
12.5 CORRIDA DE ESCRITORIO
--------------------------------------------------------------------

Entrada de papel: uso = gaming, presupuesto = 15000 MXN.
La corrida real usa 20 individuos y 12 generaciones. Esta es la misma
mecanica, reducida para seguirla a mano.

Paso 1. Fuzzificar el presupuesto.

A 15000 solo viven dos conjuntos:

- bajo:  pleno hasta 8000 y cae a 0 en 18000.
         (18000 - 15000) / (18000 - 8000) = 0.30
- medio: triangulo que sube de 12000 a 25000.
         (15000 - 12000) / (25000 - 12000) = 0.23
- alto y muy alto: 0, porque 15000 esta antes de 35000.

El uso gaming tiene pertenencia 1. Trabajo, estudio y streaming tienen 0.

Paso 2. Reglas que disparan.

GPU, presupuesto bajo, fuerza 0.30, consecuente Muy alta.
GPU, presupuesto medio, fuerza 0.23, consecuente Muy alta.
Las dos recortan la misma curva. La agregacion se queda con la fuerza
mayor, 0.30, sobre el trapezoide Muy alta (sube desde 72 y esta en 1
de 88 a 100). El centroide de esa area cae cerca de 87. La etiqueta
en 87 es Muy alta.

Almacenamiento, al reves:

- bajo, fuerza 0.30, consecuente Muy baja
- medio, fuerza 0.23, consecuente Baja

Se superponen las dos curvas recortadas con el maximo, y el centroide
cae cerca de 21. La etiqueta es Muy baja.

Una corrida real de gaming a 15000 queda asi:

- GPU              87   Muy alta
- CPU              72   Alta
- RAM              61   Alta
- Fuente           61   Alta
- Cooler           39   Baja
- Motherboard      39   Baja
- Gabinete         21   Muy baja
- Almacenamiento   21   Muy baja

Paso 3. Cuanto dinero le toca a cada pieza.

Peso de reparto = numero al cuadrado.
GPU: 87^2 = 7569.
Almacenamiento: 21^2 = 441.
La suma de los ocho cuadrados ronda 24300.
Parte de la GPU: 7569 / 24300 es cerca del 31 % de 15000, unos 4700 MXN.
Parte del disco: unos 270 MXN.
Por eso la busqueda puede gastar unos 5000 en la GPU y dejar un disco
barato.

Paso 4. Un cromosoma que si pasa el filtro.

Gen            Pieza                          Check                         Precio
CPU            Ryzen 5, AM4, TDP 65 W                                       1568
Motherboard    B550, AM4, ATX, 4 slots        socket AM4 = AM4              2000
Gabinete       ATX mid tower                  la placa ATX cabe             1398
RAM            2 x 16 GB DDR4                 AM4 acepta DDR4, 2 <= 4       1840
GPU            203 mm, unos 200 W             203 cabe en mid tower         5000
Fuente         750 W                          65 + 200 + 100 = 365 <= 750   1500
Cooler         aire, sin radiador, ~200 W     cabe y cubre 65 W              978
Disco          HDD barato                     sin restriccion fisica         280

Total 14564, menor o igual a 15000. diagnose() no devuelve codigos.
Esta PC si se evalua.

Paso 5. Tres que el filtro tira antes de la aptitud.

- Intel LGA1150 con la B550 AM4. Codigo socket. Aptitud 0. La ruleta
  no la puede elegir.
- GPU de 500 mm en el mid tower. Codigo gpu_size.
- Fuente de 200 W. Codigo power, porque 200 no cubre los 365 W.

Paso 6. Aptitud de la que si paso.

La calidad de cada pieza es el segundo Mamdani, no un score Sugeno.
La GPU RTX cae en Muy alta (cerca de 90) para gaming. El HDD cae en
Muy baja (cerca de 15). Esa calidad se multiplica por el peso de
prioridad al cuadrado: la GPU pesa porque su prioridad es 87 al
cuadrado, y el disco casi no mueve la aptitud. El total 14564 / 15000
es 0.97, cerca del objetivo del termino de precio. La aptitud queda
alrededor de 70 sobre 100. Una PC compatible de 8000 bajaria por
quedarse corta. Una de 16500 bajaria por pasarse.

Paso 7. Una generacion, en miniatura.

Individuo   Idea                                      Aptitud
A           Ryzen + GPU de 5000 + 32 GB               72
B           Ryzen + GPU mas debil + 16 GB             48
C           la del socket cruzado                     0

Ruleta. Suma de las que sirven: 72 + 48 = 120. Se sortea un numero
entre 0 y 120.

- de 0 a 72 elige A (60 % de las veces)
- de 72 a 120 elige B (40 %)
- C no ocupa ningun tramo

Suponiendo que salen A y B como padres.

Cruce. Cada gen se copia de A o de B con una moneda:

Gen     Moneda    Hijo
CPU     A         Ryzen de A
GPU     B         la GPU debil de B
RAM     A         32 GB de A
resto   mezcla    pieza de A o de B

Si la GPU de B mide 500 mm y el gabinete vino de A, el filtro marca
gpu_size. No se calcula aptitud: se cambia esa GPU por otra del pool
que mida menos que el gabinete. Si no hay ninguna, el hijo se descarta
y se queda el padre A.

Mutacion. Con probabilidad 0.35 se cambia un gen, por ejemplo el disco,
por otro disco del pool. Solo se acepta si la PC sigue compatible y el
total no pasa de 15000 x 1.12 = 16800.

Elitismo. A, con 72, pasa directo a la siguiente generacion. Esto se
repite 12 veces. Al final se quitan las repetidas y se muestran como
maximo tres que no se pasen de 15000.

Lo que se ve en pantalla es la del paso 4: socket AM4, placa ATX en
gabinete ATX, fuente de 750 W para unos 365 W, GPU de 203 mm, total
14564, aptitud alrededor de 72, y arriba los pesos Mamdani de la tabla
del paso 2.

--------------------------------------------------------------------
FIN DE LA SECCION 12
--------------------------------------------------------------------
