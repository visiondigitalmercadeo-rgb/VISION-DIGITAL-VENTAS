"""Catálogo de precios de Visión Digital — Cotizador Digital.

Datos cargados una sola vez a partir de los archivos que Steven compartió
(LPM_DIGITAL_ABRIL2025_15042025_STEVEN.xlsx, hojas "PRECIOS DIGITAL" y
"Hoja2"). NO se leen desde Excel en vivo: quedan como datos Python en este
archivo para que la app funcione igual en Streamlit Cloud sin depender de
tener el Excel disponible. Para actualizar precios en el futuro, hay que
editar los valores de aquí directamente (o pedir que se vuelva a generar
este archivo a partir de un Excel nuevo).
"""

# ---------------------------------------------------------------------------
# MATERIALES_DIGITAL: catálogo de materiales para el cotizador de "Impresión
# en pliego" (tarjetas, stickers, adhesivos, empaques, etc. — todo lo que se
# imprime en un pliego completo y se corta a la medida final del producto).
#
# "sheet_w"/"sheet_h" (pulgadas): tamaño del pliego completo de ese material —
# 12x18" es el tamaño estándar; los materiales marcados "(13 X 26")" en el
# catálogo original usan un pliego más grande de 13x26".
#
# "precios": 4 tarifas según volumen/canal (igual que el catálogo LPM):
#   - normal: venta externa estándar (la tarifa por defecto del cotizador)
#   - urgencia: pedidos pequeños/urgentes (0-50 pliegos)
#   - tienda: venta directa en tienda
#   - gerencial: descuento por volumen (aplica desde 250 pliegos)
# Cada tarifa trae "tiro" (impresión a un lado) y "tr" (tiro y retiro, ambos
# lados) — precio por pliego, en Quetzales. None = esa combinación no se
# ofrece para este material.
#
# "laminado_tiro"/"laminado_tr"/"foil"/"troquelado": costo adicional por
# pliego de cada proceso, si aplica a este material (None = no disponible).
# ---------------------------------------------------------------------------
MATERIALES_DIGITAL = [
    {
        "codigo": None, "nombre": 'VINIL METALIZADO',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 35, "tr": 0}, "urgencia": {"tiro": 45, "tr": None}, "tienda": {"tiro": 20, "tr": None}, "gerencial": {"tiro": 23.5, "tr": 0}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '010362', "nombre": 'ADHESIVO PAPEL 12 X 18',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 8, "tr": 0}, "urgencia": {"tiro": 15, "tr": None}, "tienda": {"tiro": 27.003200000000003, "tr": None}, "gerencial": {"tiro": 5.25, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010258', "nombre": 'ADHESIVO PAPEL 13 X 26',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 15, "tr": 0}, "urgencia": {"tiro": 25, "tr": None}, "tienda": {"tiro": 39.995200000000004, "tr": None}, "gerencial": {"tiro": 10, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010099', "nombre": 'ADHESIVO VINIL',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 27, "tr": 0}, "urgencia": {"tiro": 35, "tr": None}, "tienda": {"tiro": 39.995200000000004, "tr": None}, "gerencial": {"tiro": 18.5, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010103', "nombre": 'VINIL TRANSPARENTE PERMANENTE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 45, "tr": 0}, "urgencia": {"tiro": 50, "tr": None}, "tienda": {"tiro": 39.995200000000004, "tr": None}, "gerencial": {"tiro": 32, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010104', "nombre": 'VINIL TRANSPARENTE REMOVIBLE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 45, "tr": 0}, "urgencia": {"tiro": 50, "tr": None}, "tienda": {"tiro": 39.995200000000004, "tr": None}, "gerencial": {"tiro": 32, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010196', "nombre": 'VINIL TRANSPARENTE BARATO CON TAPE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 13, "tr": 0}, "urgencia": {"tiro": 27, "tr": None}, "tienda": {"tiro": 39.995200000000004, "tr": None}, "gerencial": {"tiro": 8.5, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010100', "nombre": 'VINIL BLANCO REMOVIBLE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 30, "tr": 0}, "urgencia": {"tiro": 45, "tr": None}, "tienda": {"tiro": 27, "tr": None}, "gerencial": {"tiro": 20.5, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010511', "nombre": 'ADHESIVO PAPEL MATTE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 8, "tr": 0}, "urgencia": {"tiro": 15, "tr": None}, "tienda": {"tiro": 35, "tr": None}, "gerencial": {"tiro": 5.5, "tr": 0}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '10166', "nombre": 'Acetato',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 32, "tr": 0}, "urgencia": {"tiro": 45, "tr": None}, "tienda": {"tiro": 35, "tr": None}, "gerencial": {"tiro": 22, "tr": 0}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '10122', "nombre": 'Polyester Mate 8 Ml',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 31.5, "tr": 0}, "urgencia": {"tiro": 55, "tr": None}, "tienda": {"tiro": 35, "tr": None}, "gerencial": {"tiro": 21.25, "tr": 0}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '010498', "nombre": 'POLYESTER MATTE 11 MIL',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 38, "tr": 0}, "urgencia": {"tiro": 55, "tr": None}, "tienda": {"tiro": 35, "tr": None}, "gerencial": {"tiro": 26, "tr": 0}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '010137', "nombre": 'POLYESTER BACKLIGHT',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 36, "tr": 41.5}, "urgencia": {"tiro": 55, "tr": None}, "tienda": {"tiro": 35, "tr": None}, "gerencial": {"tiro": 24.5, "tr": 28.25}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010113', "nombre": 'Perlarizado Beige',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 12, "tr": 18}, "urgencia": {"tiro": 25, "tr": 29}, "tienda": {"tiro": 27, "tr": 35}, "gerencial": {"tiro": 8.5, "tr": 12}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 2.5, "troquelado": 2,
    },
    {
        "codigo": '010115', "nombre": 'Perlarizado cocoa',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 12, "tr": 18}, "urgencia": {"tiro": 25, "tr": 29}, "tienda": {"tiro": 27, "tr": 35}, "gerencial": {"tiro": 8.5, "tr": 12}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 2.5, "troquelado": 2,
    },
    {
        "codigo": '010114', "nombre": 'Perlarizado plateado',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 12, "tr": 18}, "urgencia": {"tiro": 25, "tr": 29}, "tienda": {"tiro": 27, "tr": 35}, "gerencial": {"tiro": 8.5, "tr": 12}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 2.5, "troquelado": 2,
    },
    {
        "codigo": '010493', "nombre": 'PAPEL PERLARIZADO BLANCO',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 11.5, "tr": 17}, "urgencia": {"tiro": 25, "tr": 29}, "tienda": {"tiro": 27, "tr": 35}, "gerencial": {"tiro": 8, "tr": 11.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010491', "nombre": 'PERLARIZADO BLANCO OYSTER SHELL',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 13.5, "tr": 19}, "urgencia": {"tiro": 25, "tr": 29}, "tienda": {"tiro": 27, "tr": 35}, "gerencial": {"tiro": 9.5, "tr": 13}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010182', "nombre": 'PERLARIZADO GOLD',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 15, "tr": 20.5}, "urgencia": {"tiro": 27, "tr": 35}, "tienda": {"tiro": 27, "tr": 35}, "gerencial": {"tiro": 10, "tr": 13.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010175', "nombre": 'Desert Storm',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 18, "tr": 23.5}, "urgencia": {"tiro": 27, "tr": 35}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 12, "tr": 16}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 2.5, "troquelado": 2,
    },
    {
        "codigo": '010116', "nombre": 'PAPEL LINO BLANCO',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 14.5, "tr": 20}, "urgencia": {"tiro": 27, "tr": 35}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 10, "tr": 13.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010117', "nombre": 'PAPEL LINO BEIGE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 14.5, "tr": 19.5}, "urgencia": {"tiro": 27, "tr": 35}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 10, "tr": 13.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010098', "nombre": 'PAPEL FOTOGRAFICO',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 13, "tr": 18.5}, "urgencia": {"tiro": 25, "tr": 29}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 9, "tr": 12.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010088', "nombre": 'OPALINA',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 7.5, "tr": 13}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 5, "tr": 8.75}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 2.5, "troquelado": 2,
    },
    {
        "codigo": '010119', "nombre": 'OPALINA BEIGE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 12, "tr": 17.5}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 8.5, "tr": 12}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010118', "nombre": 'CASCARA DE HUEVO',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 14.5, "tr": 19.5}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 9.5, "tr": 13.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010533', "nombre": 'SMOOTH NATURAL',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 13.5, "tr": 19}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 9, "tr": 12.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 2,
    },
    {
        "codigo": '010236', "nombre": 'Husky 8',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.25, "tr": 11.75}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27}, "gerencial": {"tiro": 4.5, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": 4, "foil": 2.5, "troquelado": 2,
    },
    {
        "codigo": '010110', "nombre": 'HUSKY DIGITAL 10',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.25, "tr": 11.75}, "urgencia": {"tiro": 18, "tr": 25}, "tienda": {"tiro": 20.0032, "tr": 27}, "gerencial": {"tiro": 4.25, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": 4, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010091', "nombre": 'HUSKY DIGITAL 12',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.5, "tr": 11.75}, "urgencia": {"tiro": 18, "tr": 25}, "tienda": {"tiro": 20.0032, "tr": 27.003200000000003}, "gerencial": {"tiro": 4.25, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": 4, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010185', "nombre": 'HUSKY DIGITAL 14',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.5, "tr": 12}, "urgencia": {"tiro": 20, "tr": 27.003200000000003}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4.5, "tr": 8}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010436', "nombre": 'HUSKY DIGITAL 16',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 7, "tr": 12}, "urgencia": {"tiro": 20, "tr": 27.003200000000003}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4.5, "tr": 8.25}},
        "laminado_tiro": 2, "laminado_tr": 4, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010093', "nombre": 'KRAFTBACK DIGITAL 12',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.5, "tr": 12}, "urgencia": {"tiro": 18, "tr": 25}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4.5, "tr": 8}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010094', "nombre": 'BOND DIGITAL 90 GRS BASE 24',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 5.75, "tr": 11}, "urgencia": {"tiro": 10, "tr": 15}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4, "tr": 7.5}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010095', "nombre": 'BOND DIGITAL 120 GRS BASE 32',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6, "tr": 11.5}, "urgencia": {"tiro": 10, "tr": 15}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010089', "nombre": 'PAPEL TEXCOTE DIGITAL  12',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6, "tr": 11.5}, "urgencia": {"tiro": 18, "tr": 25}, "tienda": {"tiro": 20, "tr": 22}, "gerencial": {"tiro": 4, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010090', "nombre": 'PAPEL TEXCOTE DIGITAL  14',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.25, "tr": 11.5}, "urgencia": {"tiro": 18, "tr": 25}, "tienda": {"tiro": 7, "tr": 22}, "gerencial": {"tiro": 4.5, "tr": 8}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010168', "nombre": 'PAPEL TEXCOTE DIGITAL  16',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.75, "tr": 12}, "urgencia": {"tiro": 20, "tr": 27.003200000000003}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4.5, "tr": 8}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010086', "nombre": 'COUCHE DIGITAL 80',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 5.75, "tr": 11}, "urgencia": {"tiro": 10, "tr": 15}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010087', "nombre": 'COUCHE DIGITAL 100',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6, "tr": 11.25}, "urgencia": {"tiro": 10, "tr": 15}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4, "tr": 8}},
        "laminado_tiro": 2, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010346', "nombre": 'PLIKE DIGITAL BLUE',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 22.5, "tr": 27.5}, "urgencia": {"tiro": 35, "tr": 45}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 15, "tr": 19}},
        "laminado_tiro": None, "laminado_tr": None, "foil": 4.5, "troquelado": 2,
    },
    {
        "codigo": '010404', "nombre": 'Skytone',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 15, "tr": 20.5}, "urgencia": {"tiro": 27, "tr": 35}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 10.5, "tr": 14}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '010405', "nombre": 'FELT DIGITAL',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 6.75, "tr": 12}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 4.5, "tr": 8.25}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 3,
    },
    {
        "codigo": '010494', "nombre": 'CALCO DIGITAL  90 GRS',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 10.25, "tr": 15.5}, "urgencia": {"tiro": 20, "tr": 27}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 7, "tr": 10.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 3,
    },
    {
        "codigo": '010130', "nombre": 'COUCHE DIGITAL 80 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 12.5, "tr": 23}, "urgencia": {"tiro": 20, "tr": 35}, "tienda": {"tiro": 25, "tr": 30}, "gerencial": {"tiro": 8.5, "tr": 15.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 3,
    },
    {
        "codigo": '010129', "nombre": 'COUCHE DIGITAL 100 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 12.75, "tr": 23.5}, "urgencia": {"tiro": 20, "tr": 35}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 8.5, "tr": 16}},
        "laminado_tiro": 3, "laminado_tr": 6, "foil": 8, "troquelado": 3,
    },
    {
        "codigo": '010126', "nombre": 'BOND DIGITAL 90 GRS BASE 24 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 12.5, "tr": 16}, "urgencia": {"tiro": 20, "tr": 35}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 8.5, "tr": 11}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '10127', "nombre": 'BOND DIGITAL 120 GRS BASE 32 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 13.25, "tr": 16}, "urgencia": {"tiro": 20, "tr": 35}, "tienda": {"tiro": 20, "tr": 27.003200000000003}, "gerencial": {"tiro": 9, "tr": 11}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 3,
    },
    {
        "codigo": '010075', "nombre": 'HUSKY DIGITAL 10 (13 x 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 14, "tr": 25}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 10, "tr": 17}},
        "laminado_tiro": 3, "laminado_tr": 6, "foil": 8, "troquelado": 3,
    },
    {
        "codigo": '010075', "nombre": 'HUSKY DIGITAL 12 (13 x 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 14.5, "tr": 25.5}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 10, "tr": 17}},
        "laminado_tiro": 3, "laminado_tr": 6, "foil": 8, "troquelado": 3,
    },
    {
        "codigo": '10278', "nombre": 'HUSKY DIGITAL 14 (13 x 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 15.5, "tr": 26.5}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 10.5, "tr": 18}},
        "laminado_tiro": 3, "laminado_tr": 6, "foil": 8, "troquelado": 3,
    },
    {
        "codigo": None, "nombre": 'HUSKY DIGITAL 16 (13 x 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 16, "tr": 27}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 11, "tr": 18.5}},
        "laminado_tiro": 3, "laminado_tr": 6, "foil": 8, "troquelado": 3,
    },
    {
        "codigo": '10124', "nombre": 'PAPEL TEXCOTE DIGITAL  12 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 13.5, "tr": 24.5}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 9, "tr": 16.5}},
        "laminado_tiro": 3, "laminado_tr": None, "foil": 3, "troquelado": 3,
    },
    {
        "codigo": '10124', "nombre": 'PAPEL TEXCOTE DIGITAL  14 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 14.5, "tr": 25}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 10, "tr": 17}},
        "laminado_tiro": 3, "laminado_tr": None, "foil": 3, "troquelado": 3,
    },
    {
        "codigo": '10124', "nombre": 'PAPEL TEXCOTE DIGITAL  16 (13 X 26")',
        "sheet_w": 13.0, "sheet_h": 26.0,
        "precios": {"normal": {"tiro": 16, "tr": 26.5}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 11, "tr": 18}},
        "laminado_tiro": 3, "laminado_tr": None, "foil": 3, "troquelado": 3,
    },
    {
        "codigo": '010128', "nombre": 'PAPEL OPALINA DIGITAL (13X26")',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 19.5, "tr": 30}, "urgencia": {"tiro": 27, "tr": 40}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 13, "tr": 20.5}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": 3,
    },
    {
        "codigo": '010502', "nombre": 'HUSKY 18',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 10, "tr": 15.5}, "urgencia": {"tiro": 20, "tr": 35}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 7, "tr": 10.5}},
        "laminado_tiro": 3, "laminado_tr": 6, "foil": 8, "troquelado": 3,
    },
    {
        "codigo": '010011', "nombre": 'BOND DIGITAL 8.5 X 11" 80 GRS BASE 20',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 0.25, "tr": 0.45}, "urgencia": {"tiro": 0.25, "tr": 0.45}, "tienda": {"tiro": 27, "tr": 32}, "gerencial": {"tiro": 0.2, "tr": 0.35}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
    {
        "codigo": '010012', "nombre": 'BOND DIGITAL 8.5 X 13" 80 GRS BASE 20',
        "sheet_w": 12.0, "sheet_h": 18.0,
        "precios": {"normal": {"tiro": 0.4, "tr": 0.75}, "urgencia": {"tiro": 0.4, "tr": 0.75}, "tienda": {"tiro": None, "tr": None}, "gerencial": {"tiro": 0.35, "tr": 0.65}},
        "laminado_tiro": None, "laminado_tr": None, "foil": None, "troquelado": None,
    },
]

# ---------------------------------------------------------------------------
# PAPEL_BOND_INKJET: catálogo para el cotizador de "Impresión en papel bond"
# (formularios, manuales, hojas sueltas impresas por inkjet — no se cotiza por
# pliego, sino por HOJA ya al tamaño final de entrega).
#
# "tamanos" son los 4 tamaños de hoja que ofrece cada gramaje. Cada lista de
# precios (tiro_1_color / tiro_color / duplex_1_color / duplex_color) trae un
# precio por hoja (Quetzales) en el mismo orden que "tamanos".
# ---------------------------------------------------------------------------
PAPEL_BOND_INKJET = [
    {
        "titulo": 'PAPEL BOND 75 GRAMOS IMPRESION INKJET',
        "tamanos": ['CARTA', 'OFICIO', '11X17', '12X17'],
        "tiro_1_color": [0.207, 0.253, 0.52, 0.546],
        "tiro_color": [0.23, 0.276, 0.57, 0.598],
        "duplex_1_color": [0.3, 0.336, 0.67, 0.702],
        "duplex_color": [0.3375, 0.384, 0.76, 0.806],
    },
    {
        "titulo": 'PAPEL BOND 90 GRAMOS IMPRESION INKJET',
        "tamanos": ['CARTA', 'OFICIO', '11X17', '12X18'],
        "tiro_1_color": [0.29, 0.34, 0.65, 0.6762],
        "tiro_color": [0.31, 0.36, 0.69, 0.7314],
        "duplex_1_color": [0.35, 0.41, 0.79, 0.8418],
        "duplex_color": [0.39, 0.47, 0.91, 0.9522],
    },
]

TARIFAS_DIGITAL = ["normal", "urgencia", "tienda", "gerencial"]
TARIFA_LABEL = {
    "normal": "Normal (venta externa estándar)",
    "urgencia": "Urgencia (0-50 pliegos)",
    "tienda": "Tienda",
    "gerencial": "Gerencial (250+ pliegos)",
}

# Margen de corte que se le suma a cada lado de la pieza para calcular cuántas
# piezas caben por pliego ("doble corte") — mismo valor usado en el ejemplo de
# cálculo de Steven (LPM_DIGITAL, hoja "cotizador").
MARGEN_CORTE_PULGADAS = 0.5

# "Ventaja" (merma/desperdicio de producción): se suma siempre al costo, sin
# importar cuántos pliegos son — fórmula tomada del mismo ejemplo de Steven:
# precio de impresión por pliego (tiro) x 0.4 x 5.
VENTAJA_FACTOR = 0.4 * 5
