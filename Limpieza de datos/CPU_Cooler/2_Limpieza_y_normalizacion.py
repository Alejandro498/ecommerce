import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "cpu-cooler-1.csv")
archivo_salida = os.path.join(carpeta, "cpu-cooler-12.csv")


def separar_rango(valor):
    if pd.isna(valor):
        return pd.NA, pd.NA
    texto = str(valor).strip()
    if texto == "" or texto.lower() == "nan":
        return pd.NA, pd.NA
    numeros = []
    for parte in texto.split(","):
        try:
            numeros.append(float(parte.strip()))
        except ValueError:
            return pd.NA, pd.NA
    if not numeros:
        return pd.NA, pd.NA
    return min(numeros), max(numeros)


df = pd.read_csv(archivo_entrada)
filas_antes = len(df)
df = df.drop_duplicates()

df["name"] = df["name"].fillna("").astype(str).str.strip()
df["color"] = df["color"].fillna("").astype(str).str.strip()
df = df[df["name"] != ""]

rangos_rpm = df["rpm"].apply(separar_rango)
df["rpm_min"] = [rango[0] for rango in rangos_rpm]
df["rpm_max"] = [rango[1] for rango in rangos_rpm]

rangos_ruido = df["noise_level"].apply(separar_rango)
df["noise_min_db"] = [rango[0] for rango in rangos_ruido]
df["noise_max_db"] = [rango[1] for rango in rangos_ruido]

df["radiator_size"] = pd.to_numeric(df["size"], errors="coerce")
df["cooler_type"] = df["radiator_size"].apply(
    lambda tamano: "AIO" if pd.notna(tamano) and tamano > 0 else "Air"
)
df["price_available"] = df["price"].notna()

columnas = [
    "name",
    "price",
    "rpm_min",
    "rpm_max",
    "noise_min_db",
    "noise_max_db",
    "color",
    "radiator_size",
    "cooler_type",
    "price_available",
]
df = df[columnas]
df.to_csv(archivo_salida, index=False)

print(f"Instancias originales: {filas_antes}")
print(f"Instancias eliminadas: {filas_antes - len(df)}")
print(f"Instancias restantes: {len(df)}")
print(f"Sin precio: {(~df['price_available']).sum()}")
print("Tipo de cooler:")
print(df["cooler_type"].value_counts().to_string())
print(f"Archivo creado: {archivo_salida}")
