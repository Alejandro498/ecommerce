import pandas as pd

# Leer el archivo CSV
df = pd.read_csv("video-card-123.csv")


# Determinar la marca de la GPU usando la columna chipset
def obtener_gpu_brand(chipset):
    chipset = str(chipset).upper().strip()

    # NVIDIA
    if (
        "RTX" in chipset
        or "GEFORCE" in chipset
        or "NVIDIA" in chipset
        or "QUADRO" in chipset
        or "TESLA" in chipset
        or "TITAN" in chipset
        or "NVS" in chipset
    ):
        return "NVIDIA"

    # AMD
    elif (
        "RADEON" in chipset
        or "AMD" in chipset
        or "FIREPRO" in chipset
        or "FIREGL" in chipset
        or "VEGA" in chipset
        or "INSTINCT" in chipset
    ):
        return "AMD"

    # Intel
    elif (
        "INTEL" in chipset
        or "ARC" in chipset
        or "IRIS" in chipset
        or "UHD GRAPHICS" in chipset
        or "HD GRAPHICS" in chipset
        or "XE GRAPHICS" in chipset
    ):
        return "Intel"

    # No identificado
    else:
        return "Desconocida"


# Crear la columna gpu_brand
df["gpu_brand"] = df["chipset"].apply(obtener_gpu_brand)


# Guardar el resultado
df.to_csv("video-card-1234.csv", index=False)


# Mostrar resultados
print("Columna 'gpu_brand' creada correctamente.")
print()
print("Cantidad de GPUs por fabricante:")
print(df["gpu_brand"].value_counts())
print()
print(f"GPUs no identificadas: {(df['gpu_brand'] == 'Desconocida').sum()}")