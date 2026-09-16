import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "cpu-1.csv")
archivo_salida = os.path.join(carpeta, "cpu-12.csv")

df = pd.read_csv(archivo_entrada)

# Un CPU sin graficos integrados es valido; se conserva como "None".
df["graphics"] = df["graphics"].fillna("None").astype(str).str.strip()
df.loc[df["graphics"] == "", "graphics"] = "None"

# No se elimina un registro por no tener precio o boost_clock: ambos pueden
# faltar en la fuente. Solo se descartan filas sin identidad/especificaciones
# basicas para evaluar una configuracion.
campos_obligatorios = ["name", "core_count", "core_clock", "microarchitecture", "tdp"]
filas_antes = len(df)
df = df.dropna(subset=campos_obligatorios)

for columna in ["name", "microarchitecture"]:
    df[columna] = df[columna].astype(str).str.strip()
df = df[(df["name"] != "") & (df["microarchitecture"] != "")]

df["price_available"] = df["price"].notna()
df["core_count"] = pd.to_numeric(df["core_count"], errors="coerce")
df["core_clock"] = pd.to_numeric(df["core_clock"], errors="coerce")
df["boost_clock"] = pd.to_numeric(df["boost_clock"], errors="coerce")
df["tdp"] = pd.to_numeric(df["tdp"], errors="coerce")
df = df.dropna(subset=["core_count", "core_clock", "tdp"])

df.to_csv(archivo_salida, index=False)
print(f"Instancias originales: {filas_antes}")
print(f"Instancias restantes: {len(df)}")
print(f"Sin precio: {(~df['price_available']).sum()}")
print(f"Archivo creado: {archivo_salida}")
