import pandas as pd
import os

# Obtener la carpeta donde está este archivo .py
carpeta = os.path.dirname(os.path.abspath(__file__))

# Archivo de entrada
archivo_csv = os.path.join(carpeta, "memory-123.csv")

# Leer CSV
df = pd.read_csv(archivo_csv)


# Marcas de RAM
marcas = [
    "Corsair",
    "G.Skill",
    "GSKILL",
    "Kingston",
    "Crucial",
    "TeamGroup",
    "Team Group",
    "Patriot",
    "ADATA",
    "XPG",
    "Samsung",
    "SK hynix",
    "SK Hynix",
    "Micron",
    "Silicon Power",
    "Mushkin",
    "PNY",
    "GeIL",
    "GIGABYTE",
    "Gigabyte",
    "Kingston Fury",
    "Lexar",
    "Transcend",
    "Apacer",
    "OLOy",
    "Timetec",
    "Klevv",
    "Acer",
    "Thermaltake",
    "V-Color",
    "GOODRAM",
    "HP",
    "OCZ",
    "IBM",
    "VisionTek",
    "Antec",
    "Supermicro",
    "V7"
]


# Función para obtener la marca
def obtener_brand(nombre):
    nombre = str(nombre).upper()

    for marca in marcas:
        if marca.upper() in nombre:
            return marca

    return "Desconocida"


# Crear columna brand
df["brand"] = df["name"].apply(obtener_brand)


# Guardar nuevo archivo
archivo_salida = os.path.join(carpeta, "memory-1234.csv")
df.to_csv(archivo_salida, index=False)


# Mostrar resultados
print("Columna 'brand' creada correctamente.")
print()
print("Cantidad de RAM por marca:")
print(df["brand"].value_counts())
print()
print(f"Marcas no identificadas: {(df['brand'] == 'Desconocida').sum()}")
print(f"Archivo guardado en: {archivo_salida}")