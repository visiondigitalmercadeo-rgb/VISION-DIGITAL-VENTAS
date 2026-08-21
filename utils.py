import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import auth
import database as db
from config import CATEGORICAL, GRIDLINE, INK_MUTED, INK_PRIMARY, ROLES_LABEL, SURFACE


def money(v):
    try:
        return f"Q {float(v):,.2f}"
    except (TypeError, ValueError):
        return "Q 0.00"


def scope_vendedor_id():
    """Para un vendedor, retorna su propio id (los datos se filtran a lo suyo).
    Para admin/vista, retorna None (ven todo, con selector opcional)."""
    u = auth.current_user()
    if u["rol"] == "vendedor":
        return u["id"]
    return None


def vendedor_filter_selector(label="Vendedor", key="vendedor_filter"):
    """Selector de vendedor para admin/vista. Devuelve el id elegido o None (todos)."""
    u = auth.current_user()
    if u["rol"] == "vendedor":
        return u["id"]
    vendedores = db.list_vendedores(solo_activos=False)
    opciones = {"Todos": None}
    opciones.update({v["nombre"]: v["id"] for v in vendedores})
    elegido = st.selectbox(label, list(opciones.keys()), key=key)
    return opciones[elegido]


def sidebar_user_box():
    u = auth.current_user()
    with st.sidebar:
        st.markdown("---")
        st.caption(f"Sesión: **{u['nombre']}**  \nRol: *{ROLES_LABEL.get(u['rol'], u['rol'])}*")
        if st.button("Cerrar sesión", use_container_width=True):
            auth.do_logout()
            st.rerun()


def base_layout(fig: go.Figure, title=None, height=380):
    fig.update_layout(
        title=title,
        height=height,
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(color=INK_PRIMARY, family="system-ui, -apple-system, Segoe UI, sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        colorway=CATEGORICAL,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRIDLINE, tickfont=dict(color=INK_MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=GRIDLINE, tickfont=dict(color=INK_MUTED), zeroline=False)
    return fig


def df_or_empty(rows, columns=None):
    if not rows:
        return pd.DataFrame(columns=columns or [])
    return pd.DataFrame(rows)


def today_str():
    return str(date.today())
    
def as_lineas_venta(value):
    """Normaliza el campo 'linea_venta': acepta datos viejos (texto único) o
    nuevos (lista de productos seleccionados) y siempre retorna una lista."""
    if isinstance(value, list):
        return [v for v in value if v]
    if value:
        return [value]
    return []


def lineas_venta_display(value):
    """Texto legible (separado por comas) para mostrar en tablas/reportes."""
    return ", ".join(as_lineas_venta(value)) or "—"

def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
    """Convierte un DataFrame a los bytes de un archivo .xlsx en memoria."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


def download_excel_button(df: pd.DataFrame, filename: str, key: str,
                           label: str = "⬇️ Descargar Excel", sheet_name: str = "Datos"):
    """Botón para descargar un DataFrame como archivo Excel (.xlsx). Disponible
    para cualquier rol que pueda ver la tabla correspondiente (vendedor, mercadeo,
    administrador, etc.) — solo exporta lo que ya está filtrado en pantalla."""
    st.download_button(
        label, data=to_excel_bytes(df, sheet_name=sheet_name), file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, key=key,
    )
def hora_24_a_12(hhmm):
    """Convierte 'HH:MM' (24h) a (hora_1_12, minuto, 'AM'/'PM')."""
    from datetime import datetime as _dt
    try:
        t = _dt.strptime(hhmm, "%H:%M")
    except (ValueError, TypeError):
        t = _dt.now()
    hora12 = t.hour % 12
    hora12 = 12 if hora12 == 0 else hora12
    ampm = "PM" if t.hour >= 12 else "AM"
    return hora12, t.minute, ampm


def hora_12_a_24(hora12, minuto, ampm):
    """Convierte (hora_1_12, minuto, 'AM'/'PM') a texto 'HH:MM' (24h)."""
    h = hora12 % 12
    if ampm == "PM":
        h += 12
    return f"{h:02d}:{minuto:02d}"


def selector_hora(label_prefix, key_prefix, hora12=12, minuto=0, ampm="AM"):
    """Muestra 3 selectores (Hora 1-12 / Minutos / AM-PM) y retorna
    el texto 'HH:MM' en formato 24 horas, listo para guardar."""
    c1, c2, c3 = st.columns(3)
    horas_op = list(range(1, 13))
    hora_sel = c1.selectbox(
        f"{label_prefix} (hora)", horas_op,
        index=horas_op.index(hora12),
        key=f"{key_prefix}_hora",
    )
    minutos_op = list(range(0, 60))
    minuto_sel = c2.selectbox(
        f"{label_prefix} (minutos)", minutos_op,
        index=minutos_op.index(minuto),
        format_func=lambda m: f"{m:02d}",
        key=f"{key_prefix}_minuto",
    )
    ampm_sel = c3.selectbox(
        f"{label_prefix} (AM/PM)", ["AM", "PM"],
        index=["AM", "PM"].index(ampm),
        key=f"{key_prefix}_ampm",
    )
    return hora_12_a_24(hora_sel, minuto_sel, ampm_sel)
