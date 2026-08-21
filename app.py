import streamlit as st

import auth
import database as db
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
ventas = st.Page("app_pages/7_Ventas_Diarias.py", title="Venta del día", icon="🧮")
generales = st.Page("app_pages/8_Prospectos_Generales.py", title="Prospectos generales (todos)", icon="🌐")
kpis = st.Page("app_pages/9_KPIs.py", title="KPIs", icon="📊")
admin = st.Page("app_pages/10_Administracion.py", title="Administración de usuarios", icon="👥")

if rol == "mercadeo":
    # El rol 'mercadeo' solo tiene acceso a la pestaña de Visitas de mercadeo.
    pages = [mercadeo]
elif rol == "jefe_planta":
    # El rol 'jefe_planta' solo tiene acceso a la pestaña de Reclamos
    # (allí puede cambiar el estado de cada reclamo).
    pages = [reclamos]
else:
    pages = [inicio, prospectos, llamadas, citas, mercadeo, cotizaciones, reclamos, ventas, generales, kpis]
    if rol == "admin":
        pages.append(admin)

nav = st.navigation(pages)
nav.run()
