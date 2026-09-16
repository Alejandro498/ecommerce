Limpiar gabinetes (Case)

Fuente: case.csv del repositorio docyx/pc-part-dataset.

1.- Ejecutar 1_Conversion_dolar_peso.py.
    Convierte price de USD a MXN con tipo de cambio 20 y trunca a 2 decimales.

2.- Ejecutar 2_Limpieza_y_normalizacion.py.
    - Conserva gabinetes sin precio y agrega price_available.
    - Elimina filas duplicadas exactas.
    - Exige nombre, type e internal_35_bays.
    - side_panel vacio se convierte a Solid; un panel solido es valido.
    - psu vacio no es un error: significa que no trae fuente incluida.
      Se convierte a included_psu_wattage y has_included_psu.
    - Agrega max_motherboard_form_factor (ATX, Micro ATX o Mini ITX)
      para alinear el type del gabinete con form_factor de Motherboard.
    - El color y external_volume pueden faltar porque no definen
      la compatibilidad.

3.- Ejecutar 3_Agregacion_de_brand.py.
    - Agrega brand desde el fabricante incluido al inicio de name.
    - Los nombres no reconocidos quedan como Desconocida.

4.- Ejecutar 4_Muestreo_1000_registros.py.
    - Genera una muestra reproducible de exactamente 1,000 registros.
    - Reserva al menos un registro por cada combinacion de type, marca
      y disponibilidad de precio.
    - Reparte los registros restantes proporcionalmente para conservar variedad.
    - Usa la semilla 20260916.

ARCHIVO LIMPIO COMPLETO: case-123.csv
ARCHIVO REDUCIDO: case-1000.csv

Columnas finales:
name, price, type, max_motherboard_form_factor, color, included_psu_wattage,
has_included_psu, side_panel, external_volume, internal_35_bays,
price_available, brand
