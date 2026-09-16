import pandas as pd

# Leer el archivo CSV
df = pd.read_csv("video-card-12.csv")

# Marcas que queremos detectar
marcas = [
    "ASUS",
    "MSI",
    "Gigabyte",
    "ZOTAC",
    "EVGA",
    "PNY",
    "Sapphire",
    "XFX",
    "PowerColor",
    "ASRock",
    "Palit",
    "Gainward",
    "Inno3D",
    "GALAX",
    "Colorful",
    "NVIDIA",
    "AMD",
    "Acer",
    "Lenovo",
    "Sparkle",
    "ONIX",
    "Yeston",
    "VisionTek",
]

# Función para encontrar la marca
def obtener_marca(nombre):
    nombre = str(nombre).upper()

    for marca in marcas:
        if marca.upper() in nombre:
            return marca

    return "Desconocida"

# Crear la nueva columna "brand"
df["manufacturer"] = df["name"].apply(obtener_marca)

# Guardar en otro archivo
df.to_csv("video-card-123.csv", index=False)

print("Columna 'manufacturer' creada correctamente.")
print(f"Total de instancias: {len(df)}")
print(f"Marcas no identificadas: {(df['manufacturer'] == 'Desconocida').sum()}")