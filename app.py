import streamlit as st

import auth
import database as db
import public_nps
import public_tickets
from config import EMPRESA_NOMBRE, FAVICON_PATH, LOGO_PATH, PAGINAS_REGISTRO

st.set_page_config(page_title=f"{EMPRESA_NOMBRE} — Plataforma Comercial", page_icon=FAVICON_PATH, layout="wide")

try:
    st.logo(LOGO_PATH, size="large")
    # st.logo limita la altura a ~32px por defecto; la agrandamos un poco
    # manteniendo la proporción original del logo (se define solo el alto,
    # el ancho se ajusta automáticamente).
    st.markdown(
        """
        <style>
        img[data-testid="stSidebarLogo"] {
            height: 4.2rem;
            max-height: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
except Exception:
    pass

db.init_db(seed_demo=True)

# ---------------------------------------------------------------------------
# Rutas públicas del Sistema de Tickets — Tiendas (check-in por QR y pantalla
# "Ahora atendiendo"). NO requieren haber iniciado sesión, así que se
# atienden aquí mismo, antes del login, y se detiene la ejecución.
# ---------------------------------------------------------------------------
_qp_ticket = st.query_params.get("ticket")
_qp_pantalla = st.query_params.get("pantalla")
_qp_nps = st.query_params.get("nps")
if _qp_ticket:
    public_tickets.render_checkin(_qp_ticket)
    st.stop()
elif _qp_pantalla:
    public_tickets.render_pantalla(_qp_pantalla)
    st.stop()
elif _qp_nps:
    public_nps.render_encuesta(_qp_nps)
    st.stop()

if not db.firebase_conectado():
    st.warning(
        "⚠️ **Firebase todavía no está conectado.** Estás viendo la plataforma en "
        "**modo de práctica**: los datos son temporales y se pierden al cerrar el servidor. "
        "Coloca tu archivo `serviceAccountKey.json` (descargado desde Firebase) en la carpeta "
        "del proyecto y vuelve a iniciar la app para guardar datos de verdad.",
        icon="⚠️",
    )

if not auth.require_login():
    st.stop()

user = auth.current_user()
rol = user["rol"]

# Todas las páginas se construyen a partir de config.PAGINAS_REGISTRO (una
# sola fuente de verdad), para que Administración de usuarios pueda ofrecer
# exactamente esas mismas pestañas como "acceso extra" por usuario, más
# abajo. Las variables sueltas (inicio, prospectos, etc.) se mantienen igual
# que antes para no tener que tocar todo el bloque de roles de aquí abajo.
paginas_por_key = {
    p["key"]: st.Page(p["path"], title=p["title"], icon=p["icon"], default=(p["key"] == "inicio"))
    for p in PAGINAS_REGISTRO
}
inicio = paginas_por_key["inicio"]
prospectos = paginas_por_key["prospectos"]
llamadas = paginas_por_key["llamadas"]
citas = paginas_por_key["citas"]
mercadeo = paginas_por_key["mercadeo"]
cotizaciones = paginas_por_key["cotizaciones"]
reclamos = paginas_por_key["reclamos"]
diseno = paginas_por_key["diseno"]
diseno_alvaro = paginas_por_key["diseno_alvaro"]
logistica = paginas_por_key["logistica"]
ventas = paginas_por_key["ventas"]
ventas_mes = paginas_por_key["ventas_mes"]
capacitacion = paginas_por_key["capacitacion"]
tickets_tienda = paginas_por_key["tickets_tienda"]
mantenimiento = paginas_por_key["mantenimiento"]
litografia = paginas_por_key["litografia"]
mant_tiendas = paginas_por_key["mant_tiendas"]
drive = paginas_por_key["drive"]
phara = paginas_por_key["phara"]
documentos = paginas_por_key["documentos"]
colorado = paginas_por_key["colorado"]
galaxy = paginas_por_key["galaxy"]
nps = paginas_por_key["nps"]
generales = paginas_por_key["generales"]
kpis = paginas_por_key["kpis"]
admin = paginas_por_key["administracion"]

if rol == "mercadeo":
    # El rol 'mercadeo' tiene acceso a Visitas de mercadeo y, además, a
    # Tickets — Tiendas (solo para configurar los tiempos meta / KPIs; no
    # puede avanzar ni gestionar tickets, eso lo hace el personal de tienda).
    # También tiene acceso total al tablero de Mantenimiento de Tiendas, a
    # la pestaña Drive (ver puede_editar_drive en auth.py), y a Documentos
    # (solo consulta/descarga — solo el admin puede subir o eliminar ahí).
    # NPS es exclusiva del administrador (ver más abajo).
    pages = [mercadeo, tickets_tienda, mant_tiendas, drive, documentos]
elif rol == "jefe_planta":
    # El rol 'jefe_planta' tiene acceso a Reclamos (donde puede cambiar el
    # estado de cada reclamo), a Mantenimiento de Maquinaria (donde puede
    # registrar máquinas y sus mantenimientos preventivos/correctivos) y,
    # además, a Mant. Tiendas — ahí solo puede subir los PDF de cotización
    # de una solicitud mientras está en la columna 'En cotización'.
    pages = [reclamos, mantenimiento, mant_tiendas]
elif rol == "disenador":
    # El rol 'disenador' solo tiene acceso al tablero de Diseño Gráfico - Nicolás.
    pages = [diseno]
elif rol == "disenador_alvaro":
    # El rol 'disenador_alvaro' solo tiene acceso al tablero de Diseño Gráfico - Álvaro.
    pages = [diseno_alvaro]
elif rol == "jefe_logistica":
    # El rol 'jefe_logistica' solo tiene acceso a la pestaña de Logística.
    pages = [logistica]
elif rol == "repartidor":
    # El rol 'repartidor' solo tiene acceso a la pestaña de Logística
    # (ahí solo puede actualizar el estado de sus pedidos asignados).
    pages = [logistica]
elif rol in ("jefe_capacitacion", "asistente_capacitacion"):
    # Estos roles solo tienen acceso a la pestaña de Capacitación.
    pages = [capacitacion]
elif rol in ("jefe_tienda", "subjefe_tienda"):
    # 'jefe_tienda' y 'subjefe_tienda' tienen acceso al Sistema de Tickets —
    # Tiendas (solo su tienda asignada) y, además, acceso total al tablero
    # de Mantenimiento de Tiendas para su sucursal (crear, editar, mover y
    # eliminar solicitudes), a la pestaña Drive, solo para consulta (ver
    # puede_editar_drive en auth.py), y a Colorado y Galaxy para generar y
    # dar seguimiento a órdenes de producción (ver puede_editar_colorado /
    # puede_editar_galaxy). NPS es exclusiva del administrador (ver más
    # abajo).
    pages = [tickets_tienda, mant_tiendas, drive, colorado, galaxy]
elif rol in ("anfitriona", "asesor_ventas", "cajero"):
    # Estos roles solo tienen acceso al Sistema de Tickets — Tiendas (y solo
    # ven la tienda asignada a su usuario). El resto del personal de tienda
    # (acabados, express) no tiene usuario propio.
    pages = [tickets_tienda]
elif rol == "cotizadora":
    # El rol 'cotizadora' solo tiene acceso a la pestaña de Litografía, donde
    # tiene control total: crear/editar/eliminar cotizaciones y administrar
    # los catálogos de máquinas y papel (ver auth.puede_gestionar_litografia
    # y auth.puede_administrar_catalogos_litografia).
    pages = [litografia]
elif rol == "jefe_mantenimiento":
    # El rol 'jefe_mantenimiento' solo tiene acceso al tablero de
    # Mantenimiento de Tiendas, donde mueve las solicitudes por las columnas
    # (mismo concepto que 'disenador' con el tablero de Diseño Gráfico).
    pages = [mant_tiendas]
elif rol == "cliente_phara":
    # El rol 'cliente_phara' (el cliente externo) solo tiene acceso a la
    # pestaña Phara, y ahí solo puede consultar — no puede crear ni mover
    # nada (ver auth.puede_editar_phara).
    pages = [phara]
else:
    pages = [
        inicio, prospectos, llamadas, citas, mercadeo, cotizaciones, reclamos,
        diseno, diseno_alvaro, logistica, ventas, ventas_mes, capacitacion, tickets_tienda,
        mantenimiento, litografia, mant_tiendas, documentos, colorado, galaxy, generales, kpis,
    ]
    if rol == "admin":
        pages.append(admin)
        pages.append(drive)
        pages.append(phara)
        pages.append(nps)

# ---------------------------------------------------------------------------
# Acceso extra por usuario (independiente del rol) — un admin puede darle a
# un usuario en particular acceso a pestañas puntuales que su rol no incluye
# por defecto, sin tener que crear un rol nuevo (ver Administración de
# usuarios → 'Acceso extra a otras pestañas'). Dentro de cada pestaña extra
# el usuario sigue viendo solo lo que su rol normalmente le permite hacer —
# esto solo le abre la puerta para entrar a verla. 'administracion' se
# excluye explícitamente aquí (además de no ofrecerse en la UI) para que
# esta vía nunca pueda usarse para dar acceso de administrador completo.
# ---------------------------------------------------------------------------
paginas_ya_incluidas = set(pages)
for key_extra in (user.get("paginas_extra") or []):
    if key_extra == "administracion":
        continue
    pagina_extra = paginas_por_key.get(key_extra)
    if pagina_extra and pagina_extra not in paginas_ya_incluidas:
        pages.append(pagina_extra)
        paginas_ya_incluidas.add(pagina_extra)

nav = st.navigation(pages)
nav.run()
