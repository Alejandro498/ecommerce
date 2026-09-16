import pandas as pd
import os

# Obtener la carpeta donde está este archivo .py
carpeta = os.path.dirname(os.path.abspath(__file__))

# Archivo de entrada
archivo_csv = os.path.join(carpeta, "memory-1234.csv")

# Leer CSV
df = pd.read_csv(archivo_csv)

# Eliminar columnas
df = df.drop(columns=[
    "first_word_latency",
    "modules",
    "price_per_gb"
])

# Guardar nuevo archivo
archivo_salida = os.path.join(carpeta, "memory-12345.csv")
df.to_csv(archivo_salida, index=False)

print("Columnas eliminadas correctamente.")
print("Columnas eliminadas: first_word_latency, modules, price_per_gb")
print(f"Archivo guardado en: {archivo_salida}")