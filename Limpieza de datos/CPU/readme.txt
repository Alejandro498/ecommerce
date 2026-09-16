Limpiar CPU

Fuente: cpu.csv del repositorio docyx/pc-part-dataset.

1.- Ejecutar 1_Conversion_dolar_peso.py.
    Convierte price de USD a MXN con tipo de cambio 20 y trunca a 2 decimales.

2.- Ejecutar 2_Limpieza_y_normalizacion.py.
    - graphics vacio se convierte a None; no es un dato invalido.
    - Se eliminan solo filas sin nombre o especificaciones base (nucleos, reloj,
      microarquitectura y TDP).
    - Los CPUs sin precio se conservan con price_available=False para no perder
      informacion tecnica, pero no deben recomendarse por presupuesto.

3.- Ejecutar 3_Agregacion_de_brand_y_socket.py.
    - Agrega brand (AMD, Intel o Desconocida).
    - Agrega socket y socket_source.
    - El socket se deriva solo cuando modelo o microarquitectura permiten hacerlo
      con seguridad. Si no, socket queda vacio y socket_source indica
      requiere_validacion_manual.

ARCHIVO LIMPIO: cpu-123.csv

Columnas finales:
name, price, core_count, core_clock, boost_clock, microarchitecture, tdp,
graphics, price_available, brand, socket, socket_source
