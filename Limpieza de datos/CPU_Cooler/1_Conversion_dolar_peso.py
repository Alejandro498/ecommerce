import math
import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "cpu-cooler.csv")
archivo_salida = os.path.join(carpeta, "cpu-cooler-1.csv")

df = pd.read_csv(archivo_entrada)
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["price"] = df["price"].apply(
    lambda valor: math.trunc(valor * 20 * 100) / 100 if pd.notna(valor) else valor
)
df.to_csv(archivo_salida, index=False)

print(f"Instancias originales: {len(df)}")
print(f"Precios disponibles: {df['price'].notna().sum()}")
print(f"Archivo creado: {archivo_salida}")
