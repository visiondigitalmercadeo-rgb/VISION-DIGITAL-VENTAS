import base64
import hashlib
import html
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


def hora_legible(iso_ts):
    """'2026-08-25T09:14:32' -> '09:14 a.m.'. Devuelve '—' si no hay valor."""
    if not iso_ts:
        return "—"
    from datetime import datetime as _dt
    try:
        t = _dt.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return "—"
    hora12 = t.hour % 12
    hora12 = 12 if hora12 == 0 else hora12
    ampm = "a.m." if t.hour < 12 else "p.m."
    return f"{hora12:02d}:{t.minute:02d} {ampm}"


def minutos_entre(inicio_iso, fin_iso=None):
    """Minutos transcurridos entre dos timestamps ISO ('...T09:14:32'). Si no
    hay fin_iso, usa la hora actual (para tickets todavía en curso). Devuelve
    None si inicio_iso no existe todavía (esa etapa no ha comenzado)."""
    if not inicio_iso:
        return None
    from datetime import datetime as _dt
    try:
        inicio = _dt.fromisoformat(inicio_iso)
        fin = _dt.fromisoformat(fin_iso) if fin_iso else _dt.now()
    except (ValueError, TypeError):
        return None
    return max(0, int((fin - inicio).total_seconds() // 60))


def minutos_legible(minutos):
    """int -> '7 min' o '1 h 12 min'. None -> '—'."""
    if minutos is None:
        return "—"
    if minutos < 60:
        return f"{minutos} min"
    h, m = divmod(minutos, 60)
    return f"{h} h {m} min"


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


def archivos_a_b64_lista(archivos_subidos, max_bytes, max_archivos=3):
    """Convierte una lista de archivos subidos con
    st.file_uploader(accept_multiple_files=True) a una lista de
    {"nombre", "tipo", "b64"}. Retorna [] si no hay archivos. Lanza ValueError
    si se suben más de max_archivos, o si alguno pesa más de max_bytes."""
    archivos_subidos = archivos_subidos or []
    if len(archivos_subidos) > max_archivos:
        raise ValueError(
            f"Puedes adjuntar máximo {max_archivos} archivos (subiste {len(archivos_subidos)}). "
            "Quita alguno e intenta de nuevo."
        )
    resultado = []
    for archivo in archivos_subidos:
        datos = archivo.getvalue()
        if len(datos) > max_bytes:
            raise ValueError(
                f"El archivo '{archivo.name}' pesa {len(datos) / 1000:.0f} KB; el máximo permitido "
                f"por archivo es {max_bytes / 1000:.0f} KB. Comprime la imagen o el PDF e intenta de nuevo."
            )
        resultado.append({
            "nombre": archivo.name, "tipo": archivo.type,
            "b64": base64.b64encode(datos).decode("ascii"),
        })
    return resultado


def diseno_archivos_lista(d: dict) -> list:
    """Normaliza los archivos adjuntos de una solicitud de diseño: soporta
    tanto el formato nuevo (lista 'archivos') como el formato viejo (un solo
    archivo en 'archivo_nombre'/'archivo_tipo'/'archivo_b64'), para que las
    solicitudes creadas antes de este cambio se sigan viendo bien."""
    if d.get("archivos"):
        return d["archivos"]
    if d.get("archivo_b64"):
        return [{
            "nombre": d.get("archivo_nombre") or "archivo",
            "tipo": d.get("archivo_tipo") or "application/octet-stream",
            "b64": d["archivo_b64"],
        }]
    return []


# Versión pastel de la paleta de marca (CATEGORICAL), en el mismo orden, para
# las etiquetas de producto del resumen de Diseño Gráfico: (fondo, texto).
_CATEGORICAL_PASTEL = [
    ("#dce9fb", "#1c5cab"),
    ("#fbe3d5", "#b14d1f"),
    ("#d7f3e7", "#0f7a52"),
    ("#fdeecb", "#8a6100"),
    ("#fbe0ea", "#a83866"),
    ("#dcefdc", "#0a5c0a"),
    ("#e6e2f7", "#392a7a"),
    ("#fbdcdb", "#a32b2b"),
]


def _color_index(texto, cuantos):
    """Índice determinístico 0..cuantos-1 a partir de un texto (mismo texto
    siempre da el mismo índice, para que un vendedor o producto siempre
    tenga el mismo color)."""
    if not texto:
        return 0
    return int(hashlib.md5(texto.encode("utf-8")).hexdigest(), 16) % cuantos


def iniciales_nombre(nombre):
    """'Juan Pérez' -> 'JP'. Con un solo nombre, usa las primeras 2 letras."""
    partes = (nombre or "?").split()
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    return (partes[0][:2] if partes and partes[0] else "?").upper()


def pastel_para_texto(texto):
    """Color pastel determinístico (fondo, texto) para una etiqueta tipo
    'tag' — mismo texto siempre da el mismo color, tomado de la paleta de marca."""
    return _CATEGORICAL_PASTEL[_color_index(texto, len(_CATEGORICAL_PASTEL))]


def avatar_color_para(texto):
    """Color sólido determinístico (de la paleta de marca) para el círculo
    de iniciales de un vendedor."""
    return CATEGORICAL[_color_index(texto, len(CATEGORICAL))]


def diseno_resumen_html(rows, estados_orden, column_emoji, columnas_con_semaforo, vendedores, hoy, manana):
    """Genera el HTML de un 'resumen de pendientes' estilo lista (como un
    tablero de Asana/Trello en modo lista), agrupado por columna del tablero
    de Diseño Gráfico, con avatar del vendedor, tag del producto y — donde
    aplica — el semáforo y una urgencia por fecha (Hoy / Mañana)."""
    hoy_s, manana_s = str(hoy), str(manana)
    secciones = []
    for estado in estados_orden:
        items = [r for r in rows if r.get("estado") == estado]
        filas_html = []
        for r in sorted(items, key=lambda x: x.get("fecha_necesaria") or "9999-99-99"):
            cliente = html.escape(r.get("cliente") or "Sin cliente")
            producto = html.escape(r.get("producto") or "—")
            fecha = r.get("fecha_necesaria")
            nombre_vend = db.nombre_vendedor(r.get("vendedor_id"), vendedores)
            av_bg = avatar_color_para(nombre_vend)
            iniciales = html.escape(iniciales_nombre(nombre_vend))
            p_bg, p_fg = pastel_para_texto(producto)

            pills = f'<span class="vd-pill" style="background:{p_bg};color:{p_fg};">{producto}</span>'

            if estado in columnas_con_semaforo:
                if r.get("detenido_emergencia"):
                    pills += '<span class="vd-pill" style="background:#fde8e8;color:#c62828;">🔴 Emergencia</span>'
                else:
                    pills += '<span class="vd-pill" style="background:#e4f7e4;color:#0ca30c;">🟢 En proceso</span>'

            if fecha and estado != "Entregado":
                if fecha == hoy_s:
                    pills += '<span class="vd-pill" style="background:#fde8e8;color:#c62828;">⏰ Hoy</span>'
                elif fecha == manana_s:
                    pills += '<span class="vd-pill" style="background:#fdeecb;color:#8a6100;">⏰ Mañana</span>'
                else:
                    pills += f'<span class="vd-pill" style="background:#eceae3;color:#52514e;">📅 {html.escape(fecha)}</span>'

            filas_html.append(
                '<div class="vd-resumen-row">'
                f'<span class="vd-avatar" style="background:{av_bg};" title="{html.escape(nombre_vend)}">{iniciales}</span>'
                f'<span class="vd-resumen-cliente">{cliente}</span>'
                f'<span class="vd-resumen-spacer">{pills}</span>'
                '</div>'
            )

        cuerpo = "".join(filas_html) or '<div class="vd-resumen-empty">Sin solicitudes en esta columna.</div>'
        secciones.append(
            '<div class="vd-resumen-section">'
            '<div class="vd-resumen-section-header">'
            f'<span>{column_emoji.get(estado, "")} {html.escape(estado)}</span>'
            f'<span class="vd-resumen-count">{len(items)}</span>'
            '</div>'
            f'{cuerpo}'
            '</div>'
        )

    estilo = (
        "<style>"
        ".vd-resumen-wrap{display:flex;flex-direction:column;gap:14px;margin-bottom:6px;}"
        ".vd-resumen-section{border:1px solid #e1e0d9;border-radius:10px;overflow:hidden;background:#fcfcfb;}"
        ".vd-resumen-section-header{display:flex;align-items:center;gap:8px;padding:10px 14px;"
        "background:#f5f4f0;border-bottom:1px solid #e1e0d9;font-weight:600;color:#0b0b0b;font-size:0.95rem;}"
        ".vd-resumen-count{margin-left:auto;background:#e1e0d9;color:#52514e;border-radius:999px;"
        "padding:1px 10px;font-size:0.78rem;font-weight:600;}"
        ".vd-resumen-row{display:flex;align-items:center;gap:10px;padding:9px 14px;"
        "border-bottom:1px solid #efeee9;font-size:0.87rem;}"
        ".vd-resumen-row:last-child{border-bottom:none;}"
        ".vd-resumen-cliente{font-weight:600;color:#0b0b0b;}"
        ".vd-avatar{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;"
        "justify-content:center;color:white;font-size:0.66rem;font-weight:700;flex-shrink:0;}"
        ".vd-pill{border-radius:999px;padding:2px 10px;font-size:0.72rem;font-weight:600;white-space:nowrap;}"
        ".vd-resumen-spacer{margin-left:auto;display:flex;gap:6px;align-items:center;"
        "flex-wrap:wrap;justify-content:flex-end;}"
        ".vd-resumen-empty{padding:12px 14px;color:#898781;font-size:0.85rem;font-style:italic;}"
        "</style>"
    )
    return estilo + '<div class="vd-resumen-wrap">' + "".join(secciones) + "</div>"


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
        (
            "Archivos adjuntos",
            ", ".join(a["nombre"] for a in diseno_archivos_lista(d)) or "Sin archivos adjuntos",
        ),
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
