import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "motherboard-1.csv")
archivo_salida = os.path.join(carpeta, "motherboard-12.csv")


df = pd.read_csv(archivo_entrada)
filas_antes = len(df)

for columna in ["name", "socket", "form_factor", "color"]:
    df[columna] = df[columna].fillna("").astype(str).str.strip()

campos_obligatorios = [
    "name",
    "socket",
    "form_factor",
    "max_memory",
    "memory_slots",
]
df = df.dropna(subset=campos_obligatorios)
df = df[
    (df["name"] != "")
    & (df["socket"] != "")
    & (df["form_factor"] != "")
]

for columna in ["max_memory", "memory_slots"]:
    df[columna] = pd.to_numeric(df[columna], errors="coerce")

df = df.dropna(subset=["max_memory", "memory_slots"])
df = df[(df["max_memory"] > 0) & (df["memory_slots"] > 0)]
df["price_available"] = df["price"].notna()
df.to_csv(archivo_salida, index=False)

print(f"Instancias originales: {filas_antes}")
print(f"Instancias eliminadas: {filas_antes - len(df)}")
print(f"Instancias restantes: {len(df)}")
print(f"Sin precio: {(~df['price_available']).sum()}")
print(f"Archivo creado: {archivo_salida}")
