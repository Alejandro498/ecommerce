import os

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "case-12.csv")
archivo_salida = os.path.join(carpeta, "case-123.csv")

marcas = [
    "Geometric Future",
    "Parvum Systems",
    "Broadway Com",
    "Cooler Master",
    "Fractal Design",
    "Athena Power",
    "SilentiumPC",
    "MagniumGear",
    "Mars Gaming",
    "1STPLAYER",
    "Supermicro",
    "Inter-Tech",
    "SeaSonic",
    "ADATA XPG",
    "FSP Group",
    "DAN Cases",
    "PC Cooler",
    "be quiet!",
    "nMEDIAPC",
    "DARKROCK",
    "G.Skill",
    "Segotep",
    "Xilence",
    "In Win",
    "Lian Li",
    "FormD",
    "Okinos",
    "NCASE",
    "HAVN",
    "Razer",
    "TRYX",
    "Thermaltake",
    "Silverstone",
    "Athenatech",
    "darkFlash",
    "RAIJINTEK",
    "SHARKOON",
    "BitFenix",
    "Phanteks",
    "Rosewill",
    "Diablotek",
    "iBuypower",
    "LC-Power",
    "Linkworld",
    "Cooltek",
    "Streacom",
    "MUSETEX",
    "GameMax",
    "Deepcool",
    "Gigabyte",
    "Enermax",
    "Xigmatek",
    "Sentey",
    "GAMDIAS",
    "Montech",
    "Raidmax",
    "KOLINK",
    "Jonsbo",
    "Aerocool",
    "Corsair",
    "Apevia",
    "Anidees",
    "Chieftec",
    "Foxconn",
    "Nanoxia",
    "Ocypus",
    "RIOTORO",
    "mean:it",
    "ENDORFY",
    "Tecware",
    "Tempest",
    "Sunbeam",
    "Topower",
    "Cubitek",
    "BGears",
    "Logisys",
    "YEYIAN",
    "SSUPD",
    "Vetroo",
    "Zalman",
    "Cougar",
    "Antec",
    "DIYPC",
    "HYTE",
    "Azza",
    "Apex",
    "Noua",
    "Xion",
    "SAMA",
    "XClio",
    "APNX",
    "GALAX",
    "OCPC",
    "Asus",
    "NZXT",
    "MSI",
    "HEC",
    "CiT",
    "NOX",
    "EVGA",
    "VIVO",
    "Sigma",
    "Ultra",
    "CFI",
    "FSP",
    "XPG",
    "ADATA",
]

nombres_canonicos = {
    "Asus": "ASUS",
    "Deepcool": "DeepCool",
    "Silverstone": "SilverStone",
    "ADATA XPG": "XPG",
    "FSP Group": "FSP",
}


def obtener_brand(nombre):
    nombre = str(nombre).strip().upper()
    for marca in sorted(marcas, key=len, reverse=True):
        if nombre.startswith(marca.upper()):
            return nombres_canonicos.get(marca, marca)
    return "Desconocida"


df = pd.read_csv(archivo_entrada)
df["brand"] = df["name"].apply(obtener_brand)
df.to_csv(archivo_salida, index=False)

print("Cantidad de gabinetes por marca:")
print(df["brand"].value_counts())
print(f"Marcas no identificadas: {(df['brand'] == 'Desconocida').sum()}")
print(f"Archivo creado: {archivo_salida}")
