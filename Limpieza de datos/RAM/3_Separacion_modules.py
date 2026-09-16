import pandas as pd
import os

# Obtener la carpeta donde está este archivo .py
carpeta = os.path.dirname(os.path.abspath(__file__))

# Archivo de entrada
archivo_csv = os.path.join(carpeta, "memory-12.csv")

# Leer CSV
df = pd.read_csv(archivo_csv)


# Separar la columna modules
df[["module_count", "module_capacity_gb"]] = (
    df["modules"]
    .astype(str)
    .str.split(",", expand=True)
)

# Convertir las nuevas columnas a números
df["module_count"] = pd.to_numeric(df["module_count"], errors="coerce")
df["module_capacity_gb"] = pd.to_numeric(df["module_capacity_gb"], errors="coerce")


# Guardar nuevo archivo
archivo_salida = os.path.join(carpeta, "memory-123.csv")
df.to_csv(archivo_salida, index=False)


print("Columnas creadas correctamente.")
print(f"Archivo guardado en: {archivo_salida}")