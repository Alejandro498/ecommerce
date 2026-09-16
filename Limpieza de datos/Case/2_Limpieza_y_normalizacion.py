import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "case-1.csv")
archivo_salida = os.path.join(carpeta, "case-12.csv")

FORMAS_MAXIMAS = {
    "ATX Mid Tower": "ATX",
    "ATX Full Tower": "ATX",
    "ATX Mini Tower": "ATX",
    "ATX Desktop": "ATX",
    "ATX Test Bench": "ATX",
    "MicroATX Mini Tower": "Micro ATX",
    "MicroATX Mid Tower": "Micro ATX",
    "MicroATX Desktop": "Micro ATX",
    "MicroATX Slim": "Micro ATX",
    "Mini ITX Tower": "Mini ITX",
    "Mini ITX Desktop": "Mini ITX",
    "Mini ITX Test Bench": "Mini ITX",
    "HTPC": "Mini ITX",
}


def forma_maxima(tipo):
    tipo = str(tipo).strip()
    if tipo in FORMAS_MAXIMAS:
        return FORMAS_MAXIMAS[tipo]
    if tipo.startswith("Mini ITX"):
        return "Mini ITX"
    if tipo.startswith("MicroATX"):
        return "Micro ATX"
    if tipo.startswith("ATX"):
        return "ATX"
    return None


df = pd.read_csv(archivo_entrada)
filas_antes = len(df)
df = df.drop_duplicates()

for columna in ["name", "type", "color", "side_panel"]:
    df[columna] = df[columna].fillna("").astype(str).str.strip()

df["side_panel"] = df["side_panel"].replace("", "Solid")
df = df[(df["name"] != "") & (df["type"] != "")]

df["internal_35_bays"] = pd.to_numeric(df["internal_35_bays"], errors="coerce")
df["external_volume"] = pd.to_numeric(df["external_volume"], errors="coerce")
df["included_psu_wattage"] = pd.to_numeric(df["psu"], errors="coerce")
df = df.dropna(subset=["internal_35_bays"])
df = df[df["internal_35_bays"] >= 0]
df["internal_35_bays"] = df["internal_35_bays"].astype(int)

df["has_included_psu"] = df["included_psu_wattage"].notna() & (df["included_psu_wattage"] > 0)
df.loc[~df["has_included_psu"], "included_psu_wattage"] = pd.NA
df["price_available"] = df["price"].notna()
df["max_motherboard_form_factor"] = df["type"].apply(forma_maxima)
df = df[df["max_motherboard_form_factor"].notna()]

columnas = [
    "name",
    "price",
    "type",
    "max_motherboard_form_factor",
    "color",
    "included_psu_wattage",
    "has_included_psu",
    "side_panel",
    "external_volume",
    "internal_35_bays",
    "price_available",
]
df = df[columnas]
df.to_csv(archivo_salida, index=False)

print(f"Instancias originales: {filas_antes}")
print(f"Instancias eliminadas: {filas_antes - len(df)}")
print(f"Instancias restantes: {len(df)}")
print(f"Sin precio: {(~df['price_available']).sum()}")
print(f"Con fuente incluida: {df['has_included_psu'].sum()}")
print(f"Archivo creado: {archivo_salida}")
