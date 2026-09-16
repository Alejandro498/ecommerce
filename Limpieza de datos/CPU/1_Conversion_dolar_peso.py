import math
import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "cpu.csv")
archivo_salida = os.path.join(carpeta, "cpu-1.csv")

df = pd.read_csv(archivo_entrada)
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["price"] = df["price"].apply(
    lambda precio: math.trunc(precio * 20 * 100) / 100 if pd.notna(precio) else precio
)

df.to_csv(archivo_salida, index=False)
print(f"Archivo creado: {archivo_salida}")
