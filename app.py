import streamlit as st

import auth
import database as db
import public_tickets
from config import EMPRESA_NOMBRE, LOGO_PATH

st.set_page_config(page_title=f"{EMPRESA_NOMBRE} — Plataforma Comercial", page_icon=LOGO_PATH, layout="wide")

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
if _qp_ticket:
    public_tickets.render_checkin(_qp_ticket)
    st.stop()
elif _qp_pantalla:
    public_tickets.render_pantalla(_qp_pantalla)
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

inicio = st.Page("app_pages/1_Inicio.py", title="Inicio", icon="🏠", default=True)
prospectos = st.Page("app_pages/2_Prospectos_CRM.py", title="Prospección (CRM)", icon="🧾")
llamadas = st.Page("app_pages/11_Llamadas.py", title="Llamadas", icon="📞")
citas = st.Page("app_pages/3_Citas_Vendedores.py", title="Citas y visitas de vendedores", icon="📅")
mercadeo = st.Page("app_pages/4_Visitas_Mercadeo.py", title="Visitas de mercadeo", icon="🏪")
cotizaciones = st.Page("app_pages/5_Cotizaciones.py", title="Cotizaciones", icon="💰")
reclamos = st.Page("app_pages/6_Reclamos.py", title="Reclamos", icon="⚠️")
diseno = st.Page("app_pages/12_Diseno_Grafico.py", title="Diseño Gráfico - Nicolás", icon="🎨")
diseno_alvaro = st.Page("app_pages/14_Diseno_Grafico_Alvaro.py", title="Diseño Gráfico - Álvaro", icon="🖌️")
logistica = st.Page("app_pages/13_Logistica.py", title="Logística", icon="🚚")
ventas = st.Page("app_pages/7_Ventas_Diarias.py", title="Venta del día", icon="🧮")
ventas_mes = st.Page("app_pages/15_Ventas_Por_Mes.py", title="Ventas por mes", icon="📅")
capacitacion = st.Page("app_pages/16_Capacitacion.py", title="Capacitación", icon="🎓")
tickets_tienda = st.Page("app_pages/17_Tickets_Tienda.py", title="Sistema Tickets Tiendas", icon="🎫")
mantenimiento = st.Page("app_pages/18_Mantenimiento_Maquinaria.py", title="Mantenimiento de Maquinaria", icon="🔧")
generales = st.Page("app_pages/8_Prospectos_Generales.py", title="Prospectos generales (todos)", icon="🌐")
kpis = st.Page("app_pages/9_KPIs.py", title="KPIs", icon="📊")
admin = st.Page("app_pages/10_Administracion.py", title="Administración de usuarios", icon="👥")

if rol == "mercadeo":
    # El rol 'mercadeo' tiene acceso a Visitas de mercadeo y, además, a
    # Tickets — Tiendas (solo para configurar los tiempos meta / KPIs; no
    # puede avanzar ni gestionar tickets, eso lo hace el personal de tienda).
    pages = [mercadeo, tickets_tienda]
elif rol == "jefe_planta":
    # El rol 'jefe_planta' tiene acceso a Reclamos (donde puede cambiar el
    # estado de cada reclamo) y a Mantenimiento de Maquinaria (donde puede
    # registrar máquinas y sus mantenimientos preventivos/correctivos).
    pages = [reclamos, mantenimiento]
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
elif rol in ("anfitriona", "jefe_tienda", "subjefe_tienda", "asesor_ventas", "cajero"):
    # Estos roles solo tienen acceso al Sistema de Tickets — Tiendas (y solo
    # ven la tienda asignada a su usuario). El resto del personal de tienda
    # (acabados, express) no tiene usuario propio.
    pages = [tickets_tienda]
else:
    pages = [
        inicio, prospectos, llamadas, citas, mercadeo, cotizaciones, reclamos,
        diseno, diseno_alvaro, logistica, ventas, ventas_mes, capacitacion, tickets_tienda,
        mantenimiento, generales, kpis,
    ]
    if rol == "admin":
        pages.append(admin)

nav = st.navigation(pages)
nav.run()
