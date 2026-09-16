import pandas as pd

# Leer el archivo CSV
df = pd.read_csv("video-card-1.csv")

# Cantidad de filas antes de eliminar
filas_antes = len(df)

# Eliminar filas que tengan alguna columna vacía o NaN
df = df.dropna()

# También eliminar filas donde haya texto vacío ""
df = df[(df != "").all(axis=1)]

# Cantidad de filas después de eliminar
filas_despues = len(df)

# Calcular cuántas filas se eliminaron
filas_eliminadas = filas_antes - filas_despues

# Guardar el resultado en otro archivo
df.to_csv("video-card-12.csv", index=False)

# Mostrar resultado
print(f"Instancias eliminadas: {filas_eliminadas}")
print(f"Instancias restantes: {filas_despues}")