Limpiar CPU Cooler

Fuente: cpu-cooler.csv del repositorio docyx/pc-part-dataset.

1.- Ejecutar 1_Conversion_dolar_peso.py.
    Convierte price de USD a MXN con tipo de cambio 20 y trunca a 2 decimales.

2.- Ejecutar 2_Limpieza_y_normalizacion.py.
    - Conserva coolers sin precio y agrega price_available.
    - Elimina filas duplicadas exactas.
    - Exige nombre. rpm, noise_level, color y size pueden faltar.
    - rpm y noise_level se separan en min/max cuando vienen como rango
      (por ejemplo 600,3000). Un valor unico se copia a min y max.
    - size vacio es un cooler de aire; con valor es AIO (radiador en mm).
      Se convierte a radiator_size y cooler_type (Air o AIO).
    - No se agrega socket: la fuente no lo trae y la mayoria de coolers
      aftermarket soportan varios sockets. Un socket unico seria incorrecto.

3.- Ejecutar 3_Agregacion_de_brand.py.
    - Agrega brand desde el fabricante incluido al inicio de name.
    - Los nombres no reconocidos quedan como Desconocida.

4.- Ejecutar 4_Muestreo_1000_registros.py.
    - Genera una muestra reproducible de exactamente 1,000 registros.
    - Reserva al menos un registro por cada combinacion de cooler_type,
      radiator_size, marca y disponibilidad de precio.
    - Reparte los registros restantes proporcionalmente para conservar variedad.
    - Usa la semilla 20260916.

ARCHIVO LIMPIO COMPLETO: cpu-cooler-123.csv
ARCHIVO REDUCIDO: cpu-cooler-1000.csv

Columnas finales:
name, price, rpm_min, rpm_max, noise_min_db, noise_max_db, color,
radiator_size, cooler_type, price_available, brand
