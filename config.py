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
ROLES = [
    "admin", "vendedor", "vista", "mercadeo", "jefe_planta", "disenador", "disenador_alvaro",
    "jefe_logistica", "repartidor", "jefe_capacitacion", "asistente_capacitacion",
    "anfitriona", "jefe_tienda", "subjefe_tienda", "asesor_ventas", "cajero",
]
ROLES_LABEL = {
    "admin": "Administrador",
    "vendedor": "Vendedor",
    "vista": "Solo vista",
    "mercadeo": "Mercadeo",
    "jefe_planta": "Jefe de planta",
    "disenador": "Diseñador (Nicolás)",
    "disenador_alvaro": "Diseñador (Álvaro)",
    "jefe_logistica": "Jefe de logística",
    "repartidor": "Repartidor",
    "jefe_capacitacion": "Jefe de capacitación",
    "asistente_capacitacion": "Asistente de capacitación",
    "anfitriona": "Anfitriona (tienda)",
    "jefe_tienda": "Jefe de tienda",
    "subjefe_tienda": "Sub jefe de tienda",
    "asesor_ventas": "Asesor de ventas",
    "cajero": "Cajero",
}

# Roles que pertenecen a una tienda específica (necesitan el campo "tienda"
# en su usuario) para el Sistema de Tickets — Tiendas. Son los ÚNICOS roles
# de tienda que tienen usuario/contraseña para iniciar sesión — el resto del
# personal de tienda (asesores de ventas / "Diseñador", acabados, express)
# solo queda como nombre asignado a su tienda (ver PERSONAL_TIENDA_INICIAL y
# la colección "personal_tiendas"), sin acceso al sistema.
ROLES_DE_TIENDA = ["anfitriona", "jefe_tienda", "subjefe_tienda", "asesor_ventas", "cajero"]

# ---------------------------------------------------------------------------
# Personal inicial de cada tienda, proporcionado por Steven, para la carga
# masiva desde 'Administración de usuarios' → 'Carga inicial de personal'.
# TODAS estas personas quedan como nombre asignado a su tienda (colección
# "personal_tiendas") para poder elegir quién elabora cada pedido; SOLO las
# que tienen rol 'jefe_tienda', 'subjefe_tienda', 'anfitriona' o 'cajero'
# (ver ROLES_DE_TIENDA) además reciben un usuario/contraseña para iniciar
# sesión — el resto (asesor_ventas / "Diseñador", acabados, express) no
# necesita usuario. Nota: en la lista original, el puesto "Diseñador" en
# tienda corresponde al rol 'asesor_ventas' del sistema (no confundir con
# los roles 'disenador' / 'disenador_alvaro', que son del tablero de Diseño
# Gráfico); los valores "acabados"/"express" en "rol" son solo etiquetas
# descriptivas para agrupar en la carga inicial, ya no son roles reales de
# ROLES/ROLES_LABEL.
# ---------------------------------------------------------------------------
PERSONAL_TIENDA_INICIAL = [
    # Cayalá
    {"nombre": "Hemerson Hernandez", "puesto_original": "Jefe de tienda", "rol": "jefe_tienda", "tienda": "Cayalá"},
    {"nombre": "Josseline Santizo", "puesto_original": "Sub jefe", "rol": "subjefe_tienda", "tienda": "Cayalá"},
    {"nombre": "Dafne Perez", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Otto Garcia", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Melanie Duque", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "William Alvarez", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Jefereson Flores", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Edwin Liska", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Jose Valentin", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Alexander Carvajal", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Karla Ruiz", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Angie Guadalupe", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    {"nombre": "Ana Muñoz", "puesto_original": "Anfitriona", "rol": "anfitriona", "tienda": "Cayalá"},
    {"nombre": "Lesly Orellana", "puesto_original": "Cajera", "rol": "cajero", "tienda": "Cayalá"},
    {"nombre": "Brandos Barillas", "puesto_original": "Acabados", "rol": "acabados", "tienda": "Cayalá"},
    {"nombre": "Mauricio", "puesto_original": "Express", "rol": "express", "tienda": "Cayalá"},
    {"nombre": "Leonel Santizo", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Cayalá"},
    # Vista Hermosa
    {"nombre": "Brenda Rodas", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Jorge Leal", "puesto_original": "Subjefe de tienda", "rol": "subjefe_tienda", "tienda": "Vista Hermosa"},
    {"nombre": "David Sapon", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Christian Cruz", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Rodrigo Velasques", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Madolin Esquizabal", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Jennifer Hernandez", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Catherine Montenegro", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Vista Hermosa"},
    {"nombre": "Andrea Sandoval", "puesto_original": "Cajera", "rol": "cajero", "tienda": "Vista Hermosa"},
    {"nombre": "Fernando Lopez", "puesto_original": "Acabados", "rol": "acabados", "tienda": "Vista Hermosa"},
    # Majadas
    {"nombre": "Luis Crespin", "puesto_original": "Jefe", "rol": "jefe_tienda", "tienda": "Majadas"},
    {"nombre": "Carlos Subuyuj", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Majadas"},
    {"nombre": "Cinthia Flores", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Majadas"},
    {"nombre": "Pedro Cuxil", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "Majadas"},
    {"nombre": "Lourdes Marroquin", "puesto_original": "Cajero", "rol": "cajero", "tienda": "Majadas"},
    {"nombre": "Hugo Yuman", "puesto_original": "Acabados", "rol": "acabados", "tienda": "Majadas"},
    # CAES
    {"nombre": "Paola Sandoval", "puesto_original": "Jefe tienda", "rol": "jefe_tienda", "tienda": "CAES"},
    {"nombre": "Benjamin Reneau", "puesto_original": "Sub jefe tienda", "rol": "subjefe_tienda", "tienda": "CAES"},
    {"nombre": "Cristobal Rodas", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "CAES"},
    {"nombre": "Amalia Gaitán", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "CAES"},
    {"nombre": "Carlos Cruz", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "CAES"},
    {"nombre": "Andrea Bolaños", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "CAES"},
    {"nombre": "Paula Alvizures", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "CAES"},
    {"nombre": "Gabriela Del Aguila", "puesto_original": "Diseñador", "rol": "asesor_ventas", "tienda": "CAES"},
    {"nombre": "Andrea Lemus", "puesto_original": "Anfitriona", "rol": "anfitriona", "tienda": "CAES"},
    {"nombre": "Adriana Choquic", "puesto_original": "Cajera", "rol": "cajero", "tienda": "CAES"},
    {"nombre": "Hector Vasquez", "puesto_original": "Cajero", "rol": "cajero", "tienda": "CAES"},
    {"nombre": "Cristian Gonzalez", "puesto_original": "Acabados", "rol": "acabados", "tienda": "CAES"},
]

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

# Vendedores adicionales (sin necesitar usuario propio) que también se
# pueden elegir como "vendedor que hizo la venta" en un pedido de Logística,
# además de los usuarios que ya tienen el rol 'vendedor'. Se cargan solos la
# primera vez que arranca la app (ver database._seed_logistica_vendedores) y
# no requieren ningún paso manual.
LOGISTICA_VENDEDORES_INICIAL = [
    "Hemerson Hernandez", "Alejandra Santizo", "Paola Sandoval", "Benjamin Reneau",
    "Brenda Rodas", "Jorge Leal", "Luis Crespin", "Jazmin Solorzano",
]

# Para tipificar cada pedido de Logística según el canal/ruta de venta.
TIPOS_RUTA_PEDIDO = ["Venta Externa", "Venta Tiendas", "Administración", "Compras"]

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

# ---------------------------------------------------------------------------
# Capacitación (módulos / submódulos por tienda)
# ---------------------------------------------------------------------------
CAPACITACION_TIENDAS = ["Cayalá", "Vista Hermosa", "Majadas", "CAES"]
CAPACITACION_ARCHIVO_MAX_BYTES = 900_000  # ~900 KB — mismo límite práctico que Diseño Gráfico
CAPACITACION_ARCHIVOS_MAX = 5  # máximo de archivos adjuntos por submódulo

ESTADOS_PENDIENTE_MERCADEO = ["Pendiente", "En proceso", "Resuelto"]

# ---------------------------------------------------------------------------
# Mantenimiento de Maquinaria (por planta — no confundir con TICKET_TIENDAS,
# que son las tiendas del Sistema de Tickets)
# ---------------------------------------------------------------------------
PLANTAS_MAQUINARIA = ["Offset", "Digital", "Valloy"]
MANTENIMIENTO_ARCHIVO_MAX_BYTES = 900_000  # ~900 KB — mismo límite práctico que Diseño/Capacitación
TIPOS_MANTENIMIENTO = ["Preventivo", "Correctivo"]

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

# ---------------------------------------------------------------------------
# Sistema de Tickets — Tiendas (fila de clientes nuevos, con check-in por QR
# desde el celular del cliente, estilo Waitwhile)
# ---------------------------------------------------------------------------
TICKET_TIENDAS = CAPACITACION_TIENDAS  # se reutiliza la misma lista de tiendas

# Se quitó la etapa "Esperando"/"Ingresado": desde que el cliente hace
# check-in (por QR o manual) el ticket entra directo en "En atención"
# ("En espera" en el tablero), sin un paso intermedio.
ESTADOS_TICKET = ["En atención", "En elaboración", "Facturado", "Abandono"]

# Catálogo de servicios/productos que el cliente puede seleccionar (varios a
# la vez) al hacer check-in, ya sea desde el QR o registrado manualmente.
TICKET_SERVICIOS = [
    "BANNERS",
    "BOTONES",
    "CANVAS",
    "COMPRA DE MATERIALES",
    "CORTE RECTO",
    "CORTE TROQUEL",
    "COTIZACIÓN",
    "DISEÑO",
    "EMPLASTICADO",
    "ENCUADERNADO",
    "ESCANER",
    "FOTOCOPIA",
    "FOTOESTATICA",
    "FOTOGRAFÍA VISA",
    "FOTOGRAFÍAS",
    "GAFETES PVC",
    "GRABADO CD",
    "IMPRESIÓN A COLOR PAPEL",
    "IMPRESIÓN B/N PAPEL",
    "IMPRESIÓN PVC",
    "Laminado",
    "LONA VINILICA",
    "PLANOS",
    "POSTERS",
    "REDUCCION",
    "STICKERS",
    "TARJETAS DE PRESENTACIÓN",
    "TROQUEL",
    "USO DE COMPUTADORA",
]

# Slug corto (sin acentos/espacios) para usar en el enlace del código QR, por tienda.
TICKET_TIENDA_SLUG = {
    "Cayalá": "cayala",
    "Vista Hermosa": "vistahermosa",
    "Majadas": "majadas",
    "CAES": "caes",
}
TICKET_SLUG_TIENDA = {v: k for k, v in TICKET_TIENDA_SLUG.items()}

# URL pública de la plataforma, usada para armar el enlace/QR de check-in y el
# enlace de la pantalla "Ahora atendiendo". Si algún día cambia el dominio de
# Streamlit Cloud, solo hay que actualizar esto.
APP_URL = "https://vision-digital-ventas.streamlit.app"
