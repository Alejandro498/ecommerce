import os

import pandas as pd


CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_ENTRADA = os.path.join(CARPETA, "motherboard-123.csv")
ARCHIVO_SALIDA = os.path.join(CARPETA, "motherboard-1000.csv")
TAMANO_OBJETIVO = 1000
SEMILLA = 20260916
COLUMNAS_ESTRATO = ["socket", "form_factor", "brand", "price_available"]


def asignar_cuotas(grupos, total):
    tamanos = grupos.size().astype(float)
    asignadas = pd.Series(1, index=tamanos.index, dtype=int)
    disponibles = tamanos - 1
    restante = total - len(asignadas)
    cuotas = disponibles / disponibles.sum() * restante
    parte_entera = cuotas.astype(int)
    asignadas += parte_entera
    faltantes = total - int(asignadas.sum())
    if faltantes:
        residuos = (cuotas - parte_entera).sort_values(ascending=False)
        asignadas.loc[residuos.index[:faltantes]] += 1
    return asignadas.astype(int)


df = pd.read_csv(ARCHIVO_ENTRADA)
if len(df) < TAMANO_OBJETIVO:
    raise ValueError("El dataset de entrada tiene menos registros que el objetivo.")

grupos = df.groupby(COLUMNAS_ESTRATO, dropna=False, sort=False)
cuotas = asignar_cuotas(grupos, TAMANO_OBJETIVO)

muestras = []
for clave, grupo in grupos:
    cantidad = min(int(cuotas.loc[clave]), len(grupo))
    muestras.append(grupo.sample(n=cantidad, random_state=SEMILLA))

resultado = pd.concat(muestras).sample(frac=1, random_state=SEMILLA).reset_index(drop=True)
resultado.to_csv(ARCHIVO_SALIDA, index=False)

print(f"Registros originales: {len(df)}")
print(f"Registros seleccionados: {len(resultado)}")
print(f"Estratos conservados: {len(cuotas)}")
print(f"Precio disponible: {resultado['price_available'].mean():.1%}")
print(f"Archivo creado: {ARCHIVO_SALIDA}")
