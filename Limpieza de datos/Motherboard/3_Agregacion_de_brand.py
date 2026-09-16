import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "motherboard-12.csv")
archivo_salida = os.path.join(carpeta, "motherboard-123.csv")

marcas = [
    "ASRock",
    "ASUS",
    "Biostar",
    "Colorful",
    "ECS",
    "EVGA",
    "Foxconn",
    "Gigabyte",
    "Intel",
    "Jetway",
    "MAXSUN",
    "MSI",
    "NZXT",
    "Sapphire",
    "Supermicro",
    "Zotac",
]


def obtener_brand(nombre):
    nombre = str(nombre).upper()
    for marca in marcas:
        if marca.upper() in nombre:
            return "ASUS" if marca == "ASUS" else marca
    return "Desconocida"


df = pd.read_csv(archivo_entrada)
df["brand"] = df["name"].apply(obtener_brand)
df.to_csv(archivo_salida, index=False)

print("Cantidad de motherboards por marca:")
print(df["brand"].value_counts())
print(f"Marcas no identificadas: {(df['brand'] == 'Desconocida').sum()}")
print(f"Archivo creado: {archivo_salida}")
