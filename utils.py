import base64
import io
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

import auth
import database as db
from config import CATEGORICAL, EMPRESA_NOMBRE, GRIDLINE, INK_MUTED, INK_PRIMARY, ROLES_LABEL, SURFACE


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


def hora_24_a_12(hhmm):
    """Convierte 'HH:MM' (24 horas) a (hora_1_12, minuto, 'AM'/'PM')."""
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
    """Convierte (hora_1_12, minuto, 'AM'/'PM') a texto 'HH:MM' (24 horas)."""
    h = hora12 % 12
    if ampm == "PM":
        h += 12
    return f"{h:02d}:{minuto:02d}"


def selector_hora(label_prefix, key_prefix, hora12=12, minuto=0, ampm="AM"):
    """Muestra 3 selectores (Hora 1-12 / Minuto / AM-PM) y retorna el texto
    'HH:MM' en formato 24 horas, listo para guardar en la base de datos."""
    c1, c2, c3 = st.columns(3)
    hora_sel = c1.selectbox(
        f"{label_prefix} (hora)", list(range(1, 13)),
        index=list(range(1, 13)).index(hora12), key=f"{key_prefix}_hora",
    )
    minutos_opciones = list(range(0, 60))
    minuto_sel = c2.selectbox(
        f"{label_prefix} (minutos)", minutos_opciones,
        index=minutos_opciones.index(minuto), format_func=lambda m: f"{m:02d}",
        key=f"{key_prefix}_minuto",
    )
    ampm_sel = c3.selectbox(
        f"{label_prefix} (AM/PM)", ["AM", "PM"],
        index=["AM", "PM"].index(ampm), key=f"{key_prefix}_ampm",
    )
    return hora_12_a_24(hora_sel, minuto_sel, ampm_sel)


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


def archivo_a_b64(archivo_subido, max_bytes):
    """Convierte un archivo subido con st.file_uploader a (nombre, tipo, base64).
    Retorna (None, None, None) si no hay archivo. Lanza ValueError si excede
    max_bytes (límite práctico por documento en Firestore)."""
    if archivo_subido is None:
        return None, None, None
    datos = archivo_subido.getvalue()
    if len(datos) > max_bytes:
        raise ValueError(
            f"El archivo pesa {len(datos) / 1000:.0f} KB; el máximo permitido es "
            f"{max_bytes / 1000:.0f} KB. Comprime la imagen o el PDF e intenta de nuevo."
        )
    return archivo_subido.name, archivo_subido.type, base64.b64encode(datos).decode("ascii")


def _pdf_safe(texto):
    """Los PDFs con fuentes estándar (Helvetica) solo soportan Latin-1. Si el
    vendedor pegó texto con símbolos raros (emojis, comillas curvas, etc.),
    los reemplaza por '?' en vez de hacer fallar la generación del PDF."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def diseno_pdf_bytes(d: dict, vendedor_nombre: str) -> bytes:
    """Genera un PDF tipo 'orden de compra' con toda la información inicial
    de una solicitud de diseño gráfico."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _pdf_safe(EMPRESA_NOMBRE), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, _pdf_safe("Solicitud de Diseño Gráfico"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _pdf_safe(f"Folio: {d.get('id', '')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    campos = [
        ("Vendedor", vendedor_nombre or "-"),
        ("Cliente", d.get("cliente") or "-"),
        ("Producto", d.get("producto") or "-"),
        ("Material", d.get("material") or "-"),
        ("Acabado", d.get("acabado") or "-"),
        ("Medida", d.get("medida") or "-"),
        ("Fecha en que se necesita", d.get("fecha_necesaria") or "-"),
        ("Fecha de solicitud", (d.get("creado_en") or "-")[:10]),
                ("Estado actual", d.get("estado") or "-"),
        ("Cambios necesarios", d.get("cambios_necesarios") or "-"),
        ("Archivo adjunto", d.get("archivo_nombre") or "Sin archivo adjunto"),
    ]
    for etiqueta, valor in campos:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _pdf_safe(f"{etiqueta}:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, _pdf_safe(valor))
        pdf.ln(1)

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, _pdf_safe("Documento generado automáticamente por la Plataforma Comercial - Visión Digital."))

    return bytes(pdf.output())
