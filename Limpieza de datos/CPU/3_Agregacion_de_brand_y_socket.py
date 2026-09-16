import os
import re

import pandas as pd


carpeta = os.path.dirname(os.path.abspath(__file__))
archivo_entrada = os.path.join(carpeta, "cpu-12.csv")
archivo_salida = os.path.join(carpeta, "cpu-123.csv")


def obtener_brand(nombre):
    nombre = str(nombre).upper().strip()
    if nombre.startswith("AMD "):
        return "AMD"
    if nombre.startswith("INTEL "):
        return "Intel"
    return "Desconocida"


def obtener_socket(nombre, microarquitectura, brand):
    """Deriva solo sockets seguros; los demas quedan pendientes de validar."""
    nombre = str(nombre)
    arquitectura = str(microarquitectura).lower()

    if brand == "AMD":
        ryzen = re.search(r"\bRyzen\s+[3579]\s+(\d{4})", nombre, re.IGNORECASE)
        if ryzen:
            serie = int(ryzen.group(1)[0])
            if 1 <= serie <= 5:
                return "AM4", "derivado_por_modelo"
            if 7 <= serie <= 9:
                return "AM5", "derivado_por_modelo"

        threadripper = re.search(r"\bThreadripper\s+(\d{4})", nombre, re.IGNORECASE)
        if threadripper:
            serie = int(threadripper.group(1)[0])
            if serie in (1, 2):
                return "TR4", "derivado_por_modelo"
            if serie == 3:
                return "sTRX4", "derivado_por_modelo"
            if serie in (7, 9):
                return "sTR5", "derivado_por_modelo"

    if brand == "Intel":
        arquitectura_socket = {
            "arrow lake": "LGA1851",
            "raptor lake": "LGA1700",
            "alder lake": "LGA1700",
            "rocket lake": "LGA1200",
            "comet lake": "LGA1200",
            "coffee lake": "LGA1151",
            "kaby lake": "LGA1151",
            "skylake": "LGA1151",
            "haswell": "LGA1150",
            "broadwell": "LGA1150",
            "ivy bridge": "LGA1155",
            "sandy bridge": "LGA1155",
            "wolfdale": "LGA775",
        }
        for arquitectura_conocida, socket in arquitectura_socket.items():
            if arquitectura_conocida in arquitectura:
                return socket, "derivado_por_microarquitectura"

    return None, "requiere_validacion_manual"


df = pd.read_csv(archivo_entrada)
df["brand"] = df["name"].apply(obtener_brand)

resultado_socket = df.apply(
    lambda fila: obtener_socket(fila["name"], fila["microarchitecture"], fila["brand"]), axis=1
)
df[["socket", "socket_source"]] = pd.DataFrame(resultado_socket.tolist(), index=df.index)

df.to_csv(archivo_salida, index=False)
print("Cantidad de CPUs por marca:")
print(df["brand"].value_counts())
print()
print("Sockets pendientes de validacion manual:")
print((df["socket_source"] == "requiere_validacion_manual").sum())
print(f"Archivo creado: {archivo_salida}")
