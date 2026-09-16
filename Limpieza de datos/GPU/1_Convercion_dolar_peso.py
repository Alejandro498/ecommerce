import pandas as pd
import math

# Leer el CSV original
df = pd.read_csv("video-card.csv")

# Convertir price a número
df["price"] = pd.to_numeric(df["price"], errors="coerce")

# Multiplicar por 20 y truncar a 2 decimales
df["price"] = df["price"].apply(lambda x: math.trunc(x * 20 * 100) / 100 if pd.notna(x) else x)

# Guardar en un nuevo CSV
df.to_csv("video-card-1.csv", index=False)

print("Archivo creado correctamente.")