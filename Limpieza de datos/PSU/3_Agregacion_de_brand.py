import pandas as pd
import os

# Obtener la carpeta donde está este archivo .py
carpeta = os.path.dirname(os.path.abspath(__file__))

# Archivo de entrada
archivo_csv = os.path.join(carpeta, "power-supply-12.csv")

# Leer CSV
df = pd.read_csv(archivo_csv)


# Marcas de fuentes de poder
marcas = [
    "Corsair",
    "EVGA",
    "Seasonic",
    "Thermaltake",
    "Cooler Master",
    "MSI",
    "ASUS",
    "Gigabyte",
    "be quiet!",
    "be quiet",
    "NZXT",
    "SilverStone",
    "Super Flower",
    "FSP",
    "Antec",
    "XPG",
    "DeepCool",
    "Fractal Design",
    "Enermax",
    "Rosewill",
    "Phanteks",
    "Lian Li",
    "SAMA",
    "Thermaltake",
    "Cougar",
    "In Win",
    "InWin",
    "Cooler Master",
    "Redragon",
    "GameMax",
    "Thermaltake",
    "Vetroo",
    "Montech",
    "Apevia",
    "ASRock",
    "Segotep",
    "Azza",
    "Razer",
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


# Guardar resultado
archivo_salida = os.path.join(carpeta, "power-supply-123.csv")
df.to_csv(archivo_salida, index=False)


# Mostrar resultados
print("Columna 'brand' creada correctamente.")
print()
print("Cantidad de fuentes por marca:")
print(df["brand"].value_counts())
print()
print(f"Marcas no identificadas: {(df['brand'] == 'Desconocida').sum()}")
print(f"Archivo guardado en: {archivo_salida}")