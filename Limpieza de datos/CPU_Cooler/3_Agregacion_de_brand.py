import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "cpu-cooler-12.csv")
archivo_salida = os.path.join(carpeta, "cpu-cooler-123.csv")

marcas = [
    "Geometric Future",
    "Gelid Solutions",
    "Iceberg Thermal",
    "Cooler Master",
    "Fractal Design",
    "Mars Gaming",
    "SilentiumPC",
    "Inter-Tech",
    "darkFlash",
    "BitFenix",
    "Aerocool",
    "PC Cooler",
    "be quiet!",
    "ID-COOLING",
    "Thermalright",
    "Alpenföhn",
    "KOLINK",
    "ADATA",
    "Intel",
    "HYTE",
    "Azza",
    "SAMA",
    "APNX",
    "Razer",
    "FSP",
    "Prolimatech",
    "ZEROtherm",
    "Alphacool",
    "RAIJINTEK",
    "Silverstone",
    "Masscool",
    "CRYORIG",
    "Deepcool",
    "Thermaltake",
    "Evercool",
    "Xigmatek",
    "Gigabyte",
    "Phanteks",
    "ENDORFY",
    "GameMax",
    "Rosewill",
    "Valkyrie",
    "In Win",
    "Lian Li",
    "Enermax",
    "Dynatron",
    "Xilence",
    "Ocypus",
    "upHere",
    "SilenX",
    "Montech",
    "Reeven",
    "Logisys",
    "GAMDIAS",
    "Corsair",
    "ARCTIC",
    "Scythe",
    "Noctua",
    "Jonsbo",
    "Zalman",
    "Antec",
    "Cougar",
    "Vetroo",
    "Gelid",
    "Akasa",
    "Titan",
    "Noua",
    "TRYX",
    "Asus",
    "NZXT",
    "MSI",
    "EVGA",
    "AMD",
    "EK",
]

nombres_canonicos = {
    "Asus": "ASUS",
    "Deepcool": "DeepCool",
    "Silverstone": "SilverStone",
    "Gelid Solutions": "Gelid",
}


def obtener_brand(nombre):
    nombre = str(nombre).strip().upper()
    for marca in sorted(marcas, key=len, reverse=True):
        if nombre.startswith(marca.upper()):
            return nombres_canonicos.get(marca, marca)
    return "Desconocida"


df = pd.read_csv(archivo_entrada)
df["brand"] = df["name"].apply(obtener_brand)
df.to_csv(archivo_salida, index=False)

print("Cantidad de coolers por marca:")
print(df["brand"].value_counts())
print(f"Marcas no identificadas: {(df['brand'] == 'Desconocida').sum()}")
print(f"Archivo creado: {archivo_salida}")
