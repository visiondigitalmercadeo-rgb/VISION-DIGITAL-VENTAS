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
ROLES = ["admin", "vendedor", "vista"]
ROLES_LABEL = {"admin": "Administrador", "vendedor": "Vendedor", "vista": "Solo vista"}

PLANTAS = ["Offset", "Digital", "Valloy", "Colorado"]

ESTADOS_PROSPECTO = ["Prospecto", "En negociación", "Cliente (Ganado)", "Perdido"]

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
