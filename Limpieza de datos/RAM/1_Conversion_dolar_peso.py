import pandas as pd
import os
import math

# Obtener la carpeta donde está este archivo .py
carpeta = os.path.dirname(os.path.abspath(__file__))

# Ruta del archivo CSV
archivo_csv = os.path.join(carpeta, "memory.csv")

# Leer el CSV
df = pd.read_csv(archivo_csv)

# Convertir price a número
df["price"] = pd.to_numeric(df["price"], errors="coerce")

# Multiplicar por 20 y truncar a 2 decimales
df["price"] = df["price"].apply(
    lambda x: math.trunc(x * 20 * 100) / 100 if pd.notna(x) else x
)

# Guardar el nuevo archivo
archivo_salida = os.path.join(carpeta, "memory-1.csv")

df.to_csv(archivo_salida, index=False)

print("Archivo creado correctamente.")
print(f"Archivo guardado en: {archivo_salida}")