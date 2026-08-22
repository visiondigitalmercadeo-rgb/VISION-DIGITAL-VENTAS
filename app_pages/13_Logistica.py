"""Configuración global: rutas, colores (paleta validada de la skill dataviz),
listas de opciones de negocio (plantas, estados, etc.)."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Marca
# ---------------------------------------------------------------------------
EMPRESA_NOMBRE = "Visión Digital"
EMPRESA_LEMA = "Tu punto de impresión"
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo.png")
BRAND_PINK = "#FF0C82"  # color de marca — solo para chrome de la interfaz (botones, acentos),
                         # NO se usa en las gráficas: ahí se mantiene la paleta validada abajo.

# ---------------------------------------------------------------------------
# Paleta (referencia validada por la skill dataviz — references/palette.md)
# ---------------------------------------------------------------------------
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]
STATUS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
}
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"

# ---------------------------------------------------------------------------
# Catálogos de negocio
# ---------------------------------------------------------------------------
ROLES = ["admin", "vendedor", "vista", "mercadeo", "jefe_planta", "disenador", "jefe_logistica", "repartidor"]
ROLES_LABEL = {
    "admin": "Administrador",
    "vendedor": "Vendedor",
    "vista": "Solo vista",
    "mercadeo": "Mercadeo",
    "jefe_planta": "Jefe de planta",
    "disenador": "Diseñador",
    "jefe_logistica": "Jefe de logística",
    "repartidor": "Repartidor",
}

PLANTAS = ["Offset", "Digital", "Valloy", "Colorado"]

ESTADOS_PROSPECTO = ["Prospecto", "En negociación", "Cliente (Ganado)", "Perdido"]

TIPOS_LLAMADA = ["Llamada inicial", "Llamada de seguimiento"]

# ---------------------------------------------------------------------------
# Diseño Gráfico (tablero estilo Trello)
# ---------------------------------------------------------------------------
ESTADOS_DISENO = ["Lista de tareas", "Emergencias", "En proceso", "Cambios", "Entregado"]
# Columnas en las que puede caer una solicitud NUEVA (la llena el vendedor).
ESTADOS_DISENO_INICIALES = ["Lista de tareas", "Emergencias"]
# Columnas que solo el diseñador (o el administrador) puede asignar después.
ESTADOS_DISENO_DISENADOR = ["Lista de tareas", "Emergencias", "En proceso", "Cambios", "Entregado"]
DISENO_ARCHIVO_MAX_BYTES = 900_000  # ~900 KB — límite práctico por archivo en Firestore
DISENO_ARCHIVOS_MAX = 3  # máximo de archivos adjuntos por solicitud

# ---------------------------------------------------------------------------
# Logística (pedidos AM/PM)
# ---------------------------------------------------------------------------
FRANJAS_PEDIDO = ["AM", "PM"]
ESTADOS_PEDIDO = ["Pendiente", "En ruta", "Entregado", "No entregado"]
ZONAS_CAPITAL = [f"Zona {i}" for i in range(1, 22)]

TIPOS_CITA = ["Cita", "Visita", "Llamada"]
ESTADOS_CITA = ["Programada", "Realizada", "Cancelada", "No asistió"]

ESTADOS_COTIZACION = ["Enviada", "Pendiente", "En negociación", "Aprobada", "Rechazada"]

ESTADOS_VISITA_MERCADEO = ["Pendiente", "Realizada"]
CHECKLIST_DEFAULT = [
    "Exhibición correcta del producto",
    "Material POP colocado",
    "Precios visibles y correctos",
    "Stock disponible",
    "Limpieza y orden del punto de venta",
    "Presencia de competencia relevante",
    "Punto de venta satisfecho con el servicio",
]

ESTADOS_RECLAMO = ["Abierto", "En proceso", "Resuelto", "Cerrado"]

ESTADOS_PENDIENTE_MERCADEO = ["Pendiente", "En proceso", "Resuelto"]

LINEAS_VENTA = [
    "AFICHE",
    "CALENDARIO",
    "MARBETE",
    "TARJETAS DE PRESENTACION",
    "VOLANTES",
    "AGENDAS",
    "FOLDER OFICIO",
    "GIFT CARD",
    "Sticker DTF",
    "MANTA VINILICA",
    "LIBROS",
    "LIBRETAS",
    "MENÚ",
    "EMPAQUE",
    "REVISTAS",
    "PHOTOBOOK",
    "HANG TAG",
    "TARJETAS DE CUMPLEAÑOS",
    "ETIQUETAS",
    "Etiquetas Valloy",
    "FAJAS",
    "MATERIAL BANCARIO",
    "STICKER VINIL COLORADO",
    "ROLL UP",
    "PORTA VASOS",
    "TICKETS",
    "IMPRESIONES",
    "SEPARADORES",
    "STICKER COMIDA",
    "STICKER VARIOS",
    "FOTOGRAFIAS",
    "GAFETES",
    "Bolsas Kraft",
    "MATERIAL PVC",
    "TABLE TENT",
    "CAJAS",
    "BOTONES",
    "TRIFOLIAR",
    "PORTA CREPAS",
    "TARJETA FIDELIDAD",
    "HOJAS MEMBRETADA",
    "LOTERIA",
    "MAPA",
    "BLOCK DE NOTAS",
    "PUBLICIDAD MUNDIAL",
    "PROMOCIONAL MUNDIAL",
    "RASPABLES",
    "BANDEJA COMIDA",
    "INVITACIONES",
    "PAPEL REGALO",
    "DIPLOMAS",
    "Material Tigo",
    "Fotocopias",
    "Sobre Oficio",
    "Otro",
]
