# Muestra de 36 tarjetas de video

Caso fijo del asistente: **gaming**, presupuesto **$15,000 MXN**.

La muestra son las **36 GPUs** que el algoritmo genético evalúa en ese caso. Salen de `CleanedCSV/video-card-1234.csv`, con las mismas funciones del asistente: tope de precio, pool por bandas y adecuación Mamdani (`component_quality` en `assistant/quality_mamdani.py`).

El catálogo completo de las ocho categorías, con precio, suma **6,256** registros. La muestra de 36 está tomada de las 1,007 GPUs.

## Cómo se recortó el catálogo

Para $15,000 la GPU no puede pasar del 58 % del presupuesto: **$8,700**.


| Etapa                                                                 | GPUs  |
| --------------------------------------------------------------------- | ----- |
| Con precio en el CSV                                                  | 1,007 |
| Encima del tope de $8,700 (fuera de la búsqueda)                      | 710   |
| Dentro del tope                                                       | 297   |
| Muestra que entra al genético (4 bandas de precio, las de mejor spec) | 36    |


El tope deja fuera GPUs caras aunque su adecuación para gaming sea alta. Ejemplos:


| Producto              | Chipset          | VRAM  | Precio   | Adecuación gaming | Motivo                                |
| --------------------- | ---------------- | ----- | -------- | ----------------- | ------------------------------------- |
| Asus ROG Astral LC OC | GeForce RTX 5090 | 32 GB | $84,927  | 89.73             | Pasa el tope de $8,700                |
| Gainward Phantom GS   | GeForce RTX 4080 | 16 GB | $91,396  | 89.73             | Pasa el tope de $8,700                |
| PNY RTX A-Series      | RTX A6000        | 48 GB | $99,480  | 31.67             | Pasa el tope; además es clase trabajo |
| Lenovo 4X61D97085     | RTX A5000        | 24 GB | $150,327 | 31.67             | Pasa el tope; clase trabajo           |




## Estadísticas de las 36


| Medida   | Precio (MXN) | Adecuación gaming (0–100) | Adecuación estudio (0–100) |
| -------- | ------------ | ------------------------- | -------------------------- |
| Mínimo   | $3,200       | 71.62                     | 11.77                      |
| Máximo   | $8,567       | 89.73                     | 42.00                      |
| Promedio | $6,237.64    | 87.27                     | 24.31                      |
| Mediana  | $6,299.50    | 88.14                     | 23.62                      |


En las **36** la adecuación de gaming queda por encima de la de estudio. El pool se armó para gaming, así que concentra RTX. La misma pieza, evaluada para estudio, baja: una RTX 5060 Ti de 16 GB pasa de 89.73 a 11.77, y una Radeon RX 580 de 8 GB queda en 71.62 para gaming y 42.00 para estudio. El modelo cambia el puntaje con el uso.

## Prioridades Mamdani de este caso

Presupuesto $15,000, uso gaming. Defuzzificación por centroide.


| Pieza          | Peso  | Etiqueta |
| -------------- | ----- | -------- |
| GPU            | 87.42 | Muy alta |
| CPU            | 71.57 | Alta     |
| RAM            | 61.46 | Alta     |
| Fuente         | 61.46 | Alta     |
| Cooler         | 39.36 | Baja     |
| Motherboard    | 39.36 | Baja     |
| Gabinete       | 21.33 | Muy baja |
| Almacenamiento | 21.33 | Muy baja |


La parte de presupuesto de la GPU, con el peso al cuadrado, queda cerca de **$4,700**. Por eso una GPU de $8,567 puede tener la mejor adecuación y aun así no salir en la PC: se aleja de esa parte y aprieta el resto de las piezas.

## Búsqueda genética

Población 20, 12 generaciones, ruleta, elitismo 2. Mejor aptitud por generación:


| Generación    | 1     | 2     | 3     | 4     | 5     | 6     | 7     | 8     | 9     | 10    | 11    | 12    |
| ------------- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| Mejor aptitud | 73.81 | 77.28 | 78.72 | 78.72 | 78.72 | 78.72 | 81.40 | 81.73 | 81.73 | 81.73 | 81.85 | 81.86 |


La mejor aptitud sube de 73.81 a **81.86**.

Las tres configuraciones que devuelve el asistente:


| #   | Aptitud | Total   | GPU elegida                   | Precio GPU |
| --- | ------- | ------- | ----------------------------- | ---------- |
| 1   | 81.86   | $14,473 | Asus DUAL (RTX 5050, 8 GB)    | $5,000     |
| 2   | 81.85   | $14,531 | Asus DUAL OC (RTX 5050, 8 GB) | $5,000     |
| 3   | 81.84   | $14,633 | Asus PRIME (RTX 5060, 8 GB)   | $6,000     |


Las tres quedan debajo de $15,000 (96.5 %, 96.9 % y 97.6 % del presupuesto).

## Tabla de la muestra (36 GPUs)

Orden: adecuación para gaming, de mayor a menor. “En la PC” marca las tres que salieron en las configuraciones de arriba. Varios modelos comparten nombre comercial; el chipset y el precio los distinguen.


| #   | Producto                                 | Chipset               | VRAM  | Precio | Gaming | Estudio | En la PC |
| --- | ---------------------------------------- | --------------------- | ----- | ------ | ------ | ------- | -------- |
| 1   | PNY Dual Fan OC                          | GeForce RTX 5060 Ti   | 16 GB | $8,567 | 89.73  | 11.77   | No       |
| 2   | MSI VENTUS 2X XS OC                      | GeForce RTX 3050 8GB  | 8 GB  | $4,400 | 88.14  | 23.62   | No       |
| 3   | Asus DUAL                                | GeForce RTX 5050      | 8 GB  | $5,000 | 88.14  | 23.62   | Sí       |
| 4   | Asus DUAL OC                             | GeForce RTX 5050      | 8 GB  | $5,000 | 88.14  | 23.62   | Sí       |
| 5   | Gigabyte WINDFORCE OC                    | GeForce RTX 5050      | 8 GB  | $5,000 | 88.14  | 23.62   | No       |
| 6   | MSI SHADOW 2X OC                         | GeForce RTX 5050      | 8 GB  | $5,000 | 88.14  | 23.62   | No       |
| 7   | Zotac GAMING SOLO                        | GeForce RTX 5050      | 8 GB  | $5,000 | 88.14  | 23.62   | No       |
| 8   | Zotac GAMING Twin Edge                   | GeForce RTX 3060 12GB | 12 GB | $5,140 | 88.14  | 23.62   | No       |
| 9   | Gigabyte GAMING OC                       | GeForce RTX 5050      | 8 GB  | $5,400 | 88.14  | 23.62   | No       |
| 10  | MSI VENTUS 2X OC                         | GeForce RTX 5050      | 8 GB  | $5,400 | 88.14  | 23.62   | No       |
| 11  | Zotac GAMING Twin Edge OC                | GeForce RTX 5050      | 8 GB  | $5,400 | 88.14  | 23.62   | No       |
| 12  | MSI GAMING OC                            | GeForce RTX 5050      | 8 GB  | $5,600 | 88.14  | 23.62   | No       |
| 13  | Zotac GAMING Twin Edge OC                | GeForce RTX 5050      | 8 GB  | $5,600 | 88.14  | 23.62   | No       |
| 14  | Asus PRIME OC                            | GeForce RTX 5050      | 8 GB  | $5,800 | 88.14  | 23.62   | No       |
| 15  | MSI GeForce RTX 3060 Ventus 2X 12G       | GeForce RTX 3060 12GB | 12 GB | $5,999 | 88.14  | 23.62   | No       |
| 16  | Asus PRIME                               | GeForce RTX 5060      | 8 GB  | $6,000 | 88.14  | 23.62   | Sí       |
| 17  | MSI SHADOW 2X OC                         | GeForce RTX 5060      | 8 GB  | $6,000 | 88.14  | 23.62   | No       |
| 18  | Asus Dual GeForce RTX 3060 V2 OC Edition | GeForce RTX 3060 12GB | 12 GB | $6,599 | 88.14  | 23.62   | No       |
| 19  | MSI INSPIRE 2X OC                        | GeForce RTX 5060      | 8 GB  | $6,600 | 88.14  | 23.62   | No       |
| 20  | MSI VENTUS 2X                            | GeForce RTX 5060      | 8 GB  | $6,600 | 88.14  | 23.62   | No       |
| 21  | MSI VENTUS 3X OC                         | GeForce RTX 5060      | 8 GB  | $6,600 | 88.14  | 23.62   | No       |
| 22  | Zotac GAMING SOLO                        | GeForce RTX 3050 8GB  | 8 GB  | $6,642 | 88.14  | 23.62   | No       |
| 23  | PNY ARGB EPIC-X RGB OC                   | GeForce RTX 5060      | 8 GB  | $6,800 | 88.14  | 23.62   | No       |
| 24  | Zotac GAMING Twin Edge OC                | GeForce RTX 3050 8GB  | 8 GB  | $6,800 | 88.14  | 23.62   | No       |
| 25  | MSI GeForce RTX 3060 Ventus 2X 12G OC    | GeForce RTX 3060 12GB | 12 GB | $6,995 | 88.14  | 23.62   | No       |
| 26  | MSI GAMING TRIO OC                       | GeForce RTX 5060      | 8 GB  | $7,000 | 88.14  | 23.62   | No       |
| 27  | Asus DUAL OC                             | GeForce RTX 3050 8GB  | 8 GB  | $7,600 | 88.14  | 23.62   | No       |
| 28  | Zotac GAMING Twin Edge                   | GeForce RTX 5050      | 8 GB  | $7,614 | 88.14  | 23.62   | No       |
| 29  | Gigabyte WINDFORCE OC                    | GeForce RTX 5060 Ti   | 8 GB  | $7,700 | 88.14  | 23.62   | No       |
| 30  | PNY Dual Fan                             | GeForce RTX 5060 Ti   | 8 GB  | $7,719 | 88.14  | 23.62   | No       |
| 31  | Asus TUF GAMING OC                       | GeForce RTX 3050 8GB  | 8 GB  | $7,800 | 88.14  | 23.62   | No       |
| 32  | PNY VERTO OC                             | GeForce RTX 4060 Ti   | 8 GB  | $7,800 | 88.14  | 23.62   | No       |
| 33  | Zotac Twin Edge OC                       | GeForce RTX 5060 Ti   | 8 GB  | $7,800 | 88.14  | 23.62   | No       |
| 34  | NVIDIA Founders Edition                  | GeForce RTX 4060 Ti   | 8 GB  | $7,980 | 88.14  | 23.62   | No       |
| 35  | XFX GTS XXX                              | Radeon RX 580         | 8 GB  | $3,200 | 71.62  | 42.00   | No       |
| 36  | XFX GTS                                  | Radeon RX 580         | 8 GB  | $4,400 | 71.62  | 42.00   | No       |


