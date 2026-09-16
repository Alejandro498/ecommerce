import pandas as pd
import os

carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_csv = os.path.join(carpeta, "internal-hard-drive-12.csv")

df = pd.read_csv(archivo_csv)

marcas = [
    "Samsung",
    "Western Digital",
    "WD",
    "Seagate",
    "Crucial",
    "Kingston",
    "SanDisk",
    "Sabrent",
    "TeamGroup",
    "Team Group",
    "Lexar",
    "ADATA",
    "XPG",
    "Corsair",
    "Intel",
    "SK hynix",
    "SK Hynix",
    "Toshiba",
    "Micron",
    "PNY",
    "Silicon Power",
    "Patriot",
    "Transcend",
    "Solidigm",
    "Kioxia",
    "HGST",
    "Hitachi",
    "LaCie",
    "Mushkin",
    "Inland",
    "Silicon Power",
    "Fantom Drives",
    "OWC",
    "Acer",
    "MSI",
    "Gigabyte",
    "HP",
    "Nextorage",
    "Plextor",
    "Lenovo",
    "Dell"
    
    
]

def obtener_brand(nombre):
    nombre = str(nombre).upper().strip()

    for marca in marcas:
        if marca.upper() in nombre:
            # Unificamos WD como Western Digital
            if marca.upper() == "WD":
                return "Western Digital"

            # Unificamos Team Group
            if marca.upper() == "TEAM GROUP":
                return "TeamGroup"

            return marca

    return "Desconocida"


df["brand"] = df["name"].apply(obtener_brand)

archivo_salida = os.path.join(carpeta, "internal-hard-drive-123.csv")
df.to_csv(archivo_salida, index=False)

print("Columna 'brand' creada correctamente.")
print("\nMarcas encontradas:")
print(df["brand"].value_counts())

print(f"\nMemorias no identificadas: {(df['brand'] == 'Desconocida').sum()}")
print(f"Archivo guardado en: {archivo_salida}")