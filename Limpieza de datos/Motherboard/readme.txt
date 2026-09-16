Limpiar motherboards

Fuente: motherboard.csv del repositorio docyx/pc-part-dataset.

1.- Ejecutar 1_Conversion_dolar_peso.py.
    Convierte price de USD a MXN con tipo de cambio 20 y trunca a 2 decimales.

2.- Ejecutar 2_Limpieza_y_normalizacion.py.
    - Conserva motherboards sin precio y agrega price_available.
    - Exige nombre, socket, form_factor, max_memory y memory_slots.
    - Convierte max_memory y memory_slots a numeros positivos.
    - Normaliza espacios en campos de texto.
    - El color puede faltar porque no define la compatibilidad.

3.- Ejecutar 3_Agregacion_de_brand.py.
    - Agrega brand desde el fabricante incluido en name.
    - Los nombres no reconocidos quedan como Desconocida.

4.- Ejecutar 4_Muestreo_1000_registros.py.
        - Genera una muestra reproducible de exactamente 1,000 registros.
        - Reserva al menos un registro por cada combinacion de socket, formato,
            marca y disponibilidad de precio.
        - Reparte los registros restantes proporcionalmente para conservar variedad.
        - Usa la semilla 20260916.

ARCHIVO LIMPIO COMPLETO: motherboard-123.csv
ARCHIVO REDUCIDO: motherboard-1000.csv

Columnas finales:
name, price, socket, form_factor, max_memory, memory_slots, color,
price_available, brand
