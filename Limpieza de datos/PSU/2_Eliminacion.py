import pandas as pd
import os

# Obtener la carpeta donde está este archivo .py
carpeta = os.path.dirname(os.path.abspath(__file__))

# Archivo de entrada
archivo_csv = os.path.join(carpeta, "power-supply-1.csv")

# Leer el CSV
df = pd.read_csv(archivo_csv)

# Cantidad de instancias antes
filas_antes = len(df)

# Eliminar filas que tengan cualquier valor vacío
df = df.dropna()

# Eliminar también celdas que contengan solamente espacios
df = df[~df.astype(str).apply(lambda fila: fila.str.strip().eq("").any(), axis=1)]

# Cantidad de instancias después
filas_despues = len(df)

# Calcular eliminadas
filas_eliminadas = filas_antes - filas_despues

# Guardar nuevo archivo
archivo_salida = os.path.join(carpeta, "power-supply-12.csv")
df.to_csv(archivo_salida, index=False)

# Mostrar resultados
print("Limpieza completada.")
print(f"Instancias originales: {filas_antes}")
print(f"Instancias eliminadas: {filas_eliminadas}")
print(f"Instancias restantes: {filas_despues}")
print(f"Archivo guardado en: {archivo_salida}")