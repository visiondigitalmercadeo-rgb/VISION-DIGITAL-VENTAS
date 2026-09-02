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
from config import (
    CATEGORICAL, EMPRESA_DIRECCION_LINEA1, EMPRESA_DIRECCION_LINEA2, EMPRESA_NOMBRE, FIRMA_STEVEN_NOMBRE,
    FIRMA_STEVEN_PATH, FIRMA_STEVEN_PUESTO, GRIDLINE, INK_MUTED, INK_PRIMARY, LOGO_PATH, ROLES_LABEL, SURFACE,
)


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
        # Botón de refrescar datos, justo debajo del logo. Solo vuelve a
        # ejecutar la página actual (st.rerun) — NO recarga el navegador, así
        # que la sesión (usuario ya logueado) se mantiene y no manda de
        # regreso a la pantalla de credenciales.
        _, col_refrescar = st.columns([5, 1])
        with col_refrescar:
            if st.button("🔄", key="btn_refrescar_datos", help="Actualizar datos (no cierra tu sesión)"):
                st.rerun()

        st.markdown("---")
        st.caption(f"Sesión: **{u['nombre']}**  \nRol: *{ROLES_LABEL.get(u['rol'], u['rol'])}*")
        if st.button("Cerrar sesión", use_container_width=True):
            auth.do_logout()
            st.rerun()


def base_layout(fig: go.Figure, title=None, height=380):
    # El título usa yref="container" (relativo a toda la figura) por defecto
    # en Plotly, mientras que la leyenda por defecto usa yref="paper"
    # (relativo solo al área de la gráfica) — con poco margen superior, esas
    # dos referencias distintas terminaban superponiéndose visualmente. Aquí
    # se fija la leyenda también a yref="container" y se coloca explícitamente
    # debajo del título, con margen de sobra para ambos.
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", y=0.97, yanchor="top", font=dict(size=16)) if title else None,
        height=height,
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(color=INK_PRIMARY, family="system-ui, -apple-system, Segoe UI, sans-serif"),
        legend=dict(
            orientation="h", yref="container", yanchor="top",
            y=0.84 if title else 0.97, xanchor="left", x=0,
        ),
        margin=dict(l=10, r=10, t=95 if title else 40, b=10),
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
    hay fin_iso, usa la hora actual de Guatemala (para tickets todavía en
    curso — los timestamps se guardan en hora de Guatemala, así que la hora
    actual con la que se comparan debe ser la misma). Devuelve None si
    inicio_iso no existe todavía (esa etapa no ha comenzado)."""
    if not inicio_iso:
        return None
    from datetime import datetime as _dt
    try:
        inicio = _dt.fromisoformat(inicio_iso)
        fin = _dt.fromisoformat(fin_iso) if fin_iso else db.ahora_guatemala()
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


def duracion_legible(minutos):
    """int -> '7 min', '3 h 20 min', o ya pasando de 24 horas, en días:
    '2 días 4 h'. None -> '—'. A diferencia de minutos_legible (que se usa
    en Diseño Gráfico y Tickets Tienda y no se toca), esta se usa donde el
    tiempo puede acumular varios días — como los KPIs de Mantenimiento de
    Tiendas — para que no se vea como '1500 min' o un número de horas
    gigante, sino que cambie a días automáticamente pasando las 24 horas."""
    if minutos is None:
        return "—"
    if minutos < 60:
        return f"{minutos} min"
    if minutos < 1440:
        h, m = divmod(minutos, 60)
        return f"{h} h {m} min"
    dias, resto = divmod(minutos, 1440)
    h, _ = divmod(resto, 60)
    texto = f"{dias} día{'s' if dias != 1 else ''}"
    if h:
        texto += f" {h} h"
    return texto


def mant_tienda_historial_o_reconstruido(row):
    """Historial de etapas de una solicitud de Mantenimiento de Tiendas —
    usa 'historial_etapas' si ya existe (ver database.avanzar_mant_tienda,
    que agrega una entrada cada vez que la solicitud entra a una columna
    nueva, desde que se agregó este campo en adelante). Si la solicitud es
    de antes de que existiera ese campo, lo reconstruye lo mejor posible a
    partir de los campos anteriores (creado_en, tipo_solicitud_inicial,
    fecha_cotizacion, fecha_en_proceso, fecha_finalizado) — esa
    reconstrucción asume que la solicitud siguió el camino normal sin
    saltos ni retrocesos, así que puede quedar incompleta para casos raros,
    pero nunca falla (en el peor caso retorna una lista corta o vacía)."""
    historial = row.get("historial_etapas")
    if historial:
        return historial
    entradas = []
    tipo_inicial = row.get("tipo_solicitud_inicial") or (
        row.get("estado") if row.get("estado") in ("Lista de tareas", "Emergencia") else None
    )
    if tipo_inicial and row.get("creado_en"):
        entradas.append({"estado": tipo_inicial, "entrada_en": row["creado_en"]})
    if row.get("fecha_cotizacion"):
        entradas.append({"estado": "En cotización", "entrada_en": row["fecha_cotizacion"]})
    if row.get("fecha_en_proceso"):
        entradas.append({"estado": "En proceso", "entrada_en": row["fecha_en_proceso"]})
    if row.get("fecha_finalizado"):
        entradas.append({"estado": "Finalizado", "entrada_en": row["fecha_finalizado"]})
    return entradas


def mant_tienda_segmentos_etapa(row):
    """A partir del historial de etapas de una solicitud de Mantenimiento de
    Tiendas (ver mant_tienda_historial_o_reconstruido), retorna una lista de
    tuplas (etapa, minutos, en_curso) — una por cada vez que la solicitud
    entró a una columna. 'en_curso' es True solo para el último tramo, y
    solo si la solicitud sigue en esa columna ahora mismo (en ese caso mide
    desde que entró hasta la hora actual, en vez de hasta la siguiente
    entrada, que todavía no existe); la columna terminal 'Finalizado' nunca
    se marca 'en_curso' (no tiene sentido medir cuánto lleva finalizada)."""
    historial = mant_tienda_historial_o_reconstruido(row)
    segmentos = []
    for i, entrada in enumerate(historial):
        estado_etapa = entrada.get("estado")
        siguiente = historial[i + 1] if i + 1 < len(historial) else None
        if siguiente is not None:
            minutos = minutos_entre(entrada.get("entrada_en"), siguiente.get("entrada_en"))
            en_curso = False
        elif estado_etapa == "Finalizado":
            continue
        else:
            minutos = minutos_entre(entrada.get("entrada_en"))
            en_curso = True
        if minutos is not None:
            segmentos.append((estado_etapa, minutos, en_curso))
    return segmentos


def mant_tienda_tiempo_en_etapa(row, etapa):
    """Suma de minutos que una solicitud de Mantenimiento de Tiendas estuvo
    en una etapa dada, sumando todas las veces que pasó por ahí (por si se
    movió hacia atrás y volvió a entrar) — solo cuenta tramos YA
    COMPLETADOS; si la solicitud está actualmente en esa columna, ese tramo
    en curso no se incluye aquí (ver mant_tienda_segmentos_etapa). None si
    nunca completó un tramo en esa etapa."""
    minutos = [m for (est, m, en_curso) in mant_tienda_segmentos_etapa(row) if est == etapa and not en_curso]
    return sum(minutos) if minutos else None


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


def mant_tiendas_resumen_html(rows, estados_orden, column_emoji, columnas_con_semaforo):
    """Genera el HTML de un 'resumen de pendientes' estilo lista para el
    tablero de Mantenimiento de Tiendas — mismo concepto y mismo estilo
    visual que diseno_resumen_html(), pero con las columnas/campos propios de
    este tablero (tienda, quién solicita) en vez de vendedor/producto/fecha."""
    secciones = []
    for estado in estados_orden:
        items = [r for r in rows if r.get("estado") == estado]
        filas_html = []
        for r in sorted(items, key=lambda x: x.get("creado_en") or "", reverse=True):
            quien = html.escape(r.get("quien_solicita") or "Sin especificar")
            tienda = html.escape(r.get("tienda") or "—")
            av_bg = avatar_color_para(quien)
            iniciales = html.escape(iniciales_nombre(quien))
            t_bg, t_fg = pastel_para_texto(tienda)

            pills = f'<span class="vd-pill" style="background:{t_bg};color:{t_fg};">{tienda}</span>'

            if estado in columnas_con_semaforo:
                if r.get("detenido_emergencia"):
                    pills += '<span class="vd-pill" style="background:#fde8e8;color:#c62828;">🔴 Emergencia</span>'
                else:
                    pills += '<span class="vd-pill" style="background:#e4f7e4;color:#0ca30c;">🟢 En proceso</span>'

            filas_html.append(
                '<div class="vd-resumen-row">'
                f'<span class="vd-avatar" style="background:{av_bg};" title="{quien}">{iniciales}</span>'
                f'<span class="vd-resumen-cliente">{quien}</span>'
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


def pedido_pdf_bytes(p: dict) -> bytes:
    """Genera el PDF de 'ENVÍO No. ____' de un pedido de Logística, con el
    mismo diseño que la libreta física de envíos que se usaba en papel
    (encabezado con logo y número de envío, datos de FECHA/ATENCIÓN A/
    CLIENTE/DIRECCIÓN, tabla de CANTIDAD/DESCRIPCIÓN y las líneas de firma
    ENVÍA/RECIBE al final)."""
    pdf = FPDF(format="Letter")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12)

    # -- Encabezado: logo a la izquierda, caja "ENVÍO No." a la derecha -----
    try:
        pdf.image(LOGO_PATH, x=10, y=10, w=42)
    except Exception:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(10, 12)
        pdf.cell(60, 8, _pdf_safe(EMPRESA_NOMBRE))

    caja_x, caja_w = 138, 64
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(caja_x, 12)
    pdf.cell(caja_w, 8, _pdf_safe("ENVÍO No."), border=0, align="C", fill=True)

    numero_envio = p.get("numero_envio")
    texto_numero = f"No. {numero_envio:04d}" if isinstance(numero_envio, int) else "No. ____"
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(caja_x, 20)
    pdf.cell(caja_w, 10, _pdf_safe(texto_numero), border=1, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.set_xy(caja_x, 32)
    pdf.cell(caja_w, 5, _pdf_safe(EMPRESA_DIRECCION_LINEA1), align="C")
    pdf.set_xy(caja_x, 37)
    pdf.cell(caja_w, 5, _pdf_safe(EMPRESA_DIRECCION_LINEA2), align="C")
    pdf.set_text_color(0, 0, 0)

    # -- Datos del envío: FECHA / ATENCIÓN A / CLIENTE / DIRECCIÓN / N° ORDEN --
    fecha_txt = p.get("fecha") or ""
    if len(fecha_txt) == 10 and fecha_txt[4] == "-":
        fecha_txt = f"{fecha_txt[8:10]}/{fecha_txt[5:7]}/{fecha_txt[0:4]}"

    campos = [
        ("FECHA:", fecha_txt or "—"),
        ("ATENCIÓN A:", p.get("atencion_a") or "—"),
        ("CLIENTE:", p.get("cliente") or "—"),
        ("DIRECCIÓN:", p.get("direccion") or "—"),
        ("N° ORDEN:", p.get("numero_orden") or "—"),
    ]
    box_y0, fila_h, box_w = 52, 9, 190
    pdf.set_draw_color(150, 150, 150)
    pdf.rect(10, box_y0, box_w, fila_h * len(campos))
    for i, (etiqueta, valor) in enumerate(campos):
        fila_y = box_y0 + i * fila_h
        if i > 0:
            pdf.line(10, fila_y, 10 + box_w, fila_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(13, fila_y + 2.3)
        pdf.cell(35, 5, _pdf_safe(etiqueta))
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(45, fila_y + 2.3)
        pdf.cell(box_w - 38, 5, _pdf_safe(valor))

    # -- Tabla CANTIDAD / DESCRIPCIÓN ----------------------------------------
    productos = [
        it for it in (p.get("productos") or [])
        if (it.get("cantidad") or "").strip() or (it.get("descripcion") or "").strip()
    ]
    if not productos and p.get("producto"):
        productos = [{"cantidad": "", "descripcion": p["producto"]}]

    tabla_y0 = box_y0 + fila_h * len(campos) + 6
    col_cant_w, col_desc_w = 35, box_w - 35
    fila_tabla_h = 8
    num_filas = max(10, len(productos) + 1)

    pdf.set_xy(10, tabla_y0)
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_cant_w, fila_tabla_h, _pdf_safe("CANTIDAD"), border=0, align="C", fill=True)
    pdf.cell(col_desc_w, fila_tabla_h, _pdf_safe("DESCRIPCIÓN"), border=0, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_draw_color(150, 150, 150)
    line_h = 5
    fila_y = tabla_y0 + fila_tabla_h
    for i in range(num_filas):
        cant = productos[i]["cantidad"] if i < len(productos) else ""
        desc = productos[i]["descripcion"] if i < len(productos) else ""
        desc_txt = _pdf_safe(f" {desc}") if desc else ""
        if desc_txt:
            # Calcula cuántas líneas necesita la descripción para no salirse
            # de su columna (pedidos con varios productos largos) y usa esa
            # altura para ambas celdas de la fila, para que el borde quede
            # parejo entre "Cantidad" y "Descripción".
            lineas = pdf.multi_cell(col_desc_w, line_h, desc_txt, dry_run=True, output="LINES")
            alto_fila = max(fila_tabla_h, len(lineas) * line_h + 3)
        else:
            alto_fila = fila_tabla_h
        pdf.set_xy(10, fila_y)
        pdf.cell(col_cant_w, alto_fila, _pdf_safe(cant), border=1, align="C")
        pdf.set_xy(10 + col_cant_w, fila_y)
        pdf.multi_cell(col_desc_w, line_h, desc_txt, border=1)
        fila_y += alto_fila

    # -- Firmas: ENVÍA / RECIBE ----------------------------------------------
    firmas_y = fila_y + 18
    pdf.set_draw_color(0, 0, 0)
    pdf.line(15, firmas_y, 95, firmas_y)
    pdf.line(115, firmas_y, 195, firmas_y)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(15, firmas_y + 2)
    pdf.cell(80, 5, _pdf_safe("ENVÍA"), align="C")
    pdf.set_xy(115, firmas_y + 2)
    pdf.cell(80, 5, _pdf_safe("RECIBE"), align="C")
    pdf.set_xy(15, firmas_y + 7)
    pdf.cell(80, 5, _pdf_safe("Firma y Nombre"), align="C")
    pdf.set_xy(115, firmas_y + 7)
    pdf.cell(80, 5, _pdf_safe("Firma, Nombre y Sello."), align="C")

    return bytes(pdf.output())


def mant_tienda_pdf_bytes(r: dict) -> bytes:
    """Genera el PDF de 'ORDEN DE TRABAJO No. ____' de una solicitud de
    Mantenimiento de Tiendas — mismo diseño que el PDF de 'ENVÍO No.' de
    Logística (encabezado con logo y número corrido, caja de datos, y las
    líneas de firma al final), adaptado a los campos propios de este
    tablero (tienda, quién solicita, descripción del problema) en vez de la
    tabla de productos de un envío."""
    pdf = FPDF(format="Letter")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12)

    # -- Encabezado: logo a la izquierda, caja "ORDEN DE TRABAJO No." a la derecha --
    try:
        pdf.image(LOGO_PATH, x=10, y=10, w=42)
    except Exception:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(10, 12)
        pdf.cell(60, 8, _pdf_safe(EMPRESA_NOMBRE))

    caja_x, caja_w = 128, 74
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(caja_x, 12)
    pdf.cell(caja_w, 8, _pdf_safe("ORDEN DE TRABAJO No."), border=0, align="C", fill=True)

    numero_solicitud = r.get("numero_solicitud")
    texto_numero = f"No. {numero_solicitud:04d}" if isinstance(numero_solicitud, int) else "No. ____"
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(caja_x, 20)
    pdf.cell(caja_w, 10, _pdf_safe(texto_numero), border=1, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.set_xy(caja_x, 32)
    pdf.cell(caja_w, 5, _pdf_safe(EMPRESA_DIRECCION_LINEA1), align="C")
    pdf.set_xy(caja_x, 37)
    pdf.cell(caja_w, 5, _pdf_safe(EMPRESA_DIRECCION_LINEA2), align="C")
    pdf.set_text_color(0, 0, 0)

    # -- Datos de la solicitud: FECHA / TIENDA / SOLICITA / ESTADO -----------
    fecha_txt = (r.get("creado_en") or "")[:10]
    if len(fecha_txt) == 10 and fecha_txt[4] == "-":
        fecha_txt = f"{fecha_txt[8:10]}/{fecha_txt[5:7]}/{fecha_txt[0:4]}"

    campos = [
        ("FECHA:", fecha_txt or "—"),
        ("TIENDA:", r.get("tienda") or "—"),
        ("SOLICITA:", r.get("quien_solicita") or "—"),
        ("ESTADO:", r.get("estado") or "—"),
    ]
    box_y0, fila_h, box_w = 52, 9, 190
    pdf.set_draw_color(150, 150, 150)
    pdf.rect(10, box_y0, box_w, fila_h * len(campos))
    for i, (etiqueta, valor) in enumerate(campos):
        fila_y = box_y0 + i * fila_h
        if i > 0:
            pdf.line(10, fila_y, 10 + box_w, fila_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_xy(13, fila_y + 2.3)
        pdf.cell(35, 5, _pdf_safe(etiqueta))
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(45, fila_y + 2.3)
        pdf.cell(box_w - 38, 5, _pdf_safe(valor))

    # -- Descripción del problema --------------------------------------------
    desc_y0 = box_y0 + fila_h * len(campos) + 6
    pdf.set_xy(10, desc_y0)
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(box_w, 8, _pdf_safe("DESCRIPCIÓN DEL PROBLEMA"), border=0, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_xy(10, desc_y0 + 8)
    texto_desc = _pdf_safe(r.get("descripcion") or "Sin descripción.")
    lineas = pdf.multi_cell(box_w, 6, texto_desc, dry_run=True, output="LINES")
    alto_desc = max(24, len(lineas) * 6 + 6)
    pdf.multi_cell(box_w, 6, texto_desc, border=1)
    pdf.rect(10, desc_y0 + 8, box_w, alto_desc)

    # -- Fotos de la solicitud inicial ---------------------------------------
    fotos_y0 = desc_y0 + 8 + alto_desc + 6
    fotos = r.get("fotos") or []
    pdf.set_xy(10, fotos_y0)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(90, 90, 90)
    if not fotos:
        pdf.cell(box_w, 5, _pdf_safe("Sin fotos adjuntas."))
        pdf.set_text_color(0, 0, 0)
        firmas_y = fotos_y0 + 20
    else:
        pdf.cell(box_w, 5, _pdf_safe(f"📷 Fotos de la solicitud ({len(fotos)}):"))
        pdf.set_text_color(0, 0, 0)
        img_w, img_h, gap = 58, 44, 4
        img_y = fotos_y0 + 7
        x_cursor = 10
        col_i = 0
        for foto in fotos:
            try:
                img_bytes = base64.b64decode(foto.get("b64") or "")
                img_stream = io.BytesIO(img_bytes)
                # Si la foto no cabe antes del margen inferior, se pasa a una
                # página nueva en vez de encimarse con las líneas de firma.
                if img_y + img_h > 235:
                    pdf.add_page()
                    img_y = 15
                    x_cursor = 10
                    col_i = 0
                pdf.image(img_stream, x=x_cursor, y=img_y, w=img_w, h=img_h)
            except Exception:
                # Foto dañada o formato no soportado por fpdf2 — se omite en
                # vez de hacer fallar la generación de todo el PDF.
                continue
            col_i += 1
            if col_i >= 3:
                col_i = 0
                x_cursor = 10
                img_y += img_h + gap
            else:
                x_cursor += img_w + gap
        if col_i != 0:
            img_y += img_h + gap
        firmas_y = img_y + 14

    # -- Firmas: SOLICITA / ATIENDE MANTENIMIENTO ----------------------------
    pdf.set_draw_color(0, 0, 0)
    pdf.line(15, firmas_y, 95, firmas_y)
    pdf.line(115, firmas_y, 195, firmas_y)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(15, firmas_y + 2)
    pdf.cell(80, 5, _pdf_safe("SOLICITA"), align="C")
    pdf.set_xy(115, firmas_y + 2)
    pdf.cell(80, 5, _pdf_safe("ATIENDE MANTENIMIENTO"), align="C")
    pdf.set_xy(15, firmas_y + 7)
    pdf.cell(80, 5, _pdf_safe("Firma y Nombre"), align="C")
    pdf.set_xy(115, firmas_y + 7)
    pdf.cell(80, 5, _pdf_safe("Firma y Nombre"), align="C")

    return bytes(pdf.output())


def orden_produccion_pdf_bytes(p: dict, linea: str) -> bytes:
    """Genera el PDF de 'ORDEN DE PRODUCCIÓN No. ____' de una orden de
    Colorado o Galaxy — mismo diseño que el PDF de 'ENVÍO No.' de Logística
    y el de 'ORDEN DE TRABAJO No.' de Mantenimiento de Tiendas (encabezado
    con logo y número corrido, cajas de datos, y las líneas de firma al
    final), adaptado a los campos propios de una orden de producción
    (cliente, pieza, dimensiones, material, color, acabados, precio,
    cantidad, notas). 'linea' es "Colorado" o "Galaxy", para identificar de
    cuál tablero viene la orden."""
    pdf = FPDF(format="Letter")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12)

    # -- Encabezado: logo a la izquierda, caja "ORDEN DE PRODUCCIÓN No." a la derecha --
    try:
        pdf.image(LOGO_PATH, x=10, y=10, w=42)
    except Exception:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(10, 12)
        pdf.cell(60, 8, _pdf_safe(EMPRESA_NOMBRE))

    caja_x, caja_w = 108, 92
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(caja_x, 12)
    pdf.cell(caja_w, 8, _pdf_safe("ORDEN DE PRODUCCIÓN No."), border=0, align="C", fill=True)

    numero_orden = p.get("numero_orden")
    texto_numero = f"No. {numero_orden:04d}" if isinstance(numero_orden, int) else "No. ____"
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(caja_x, 20)
    pdf.cell(caja_w, 10, _pdf_safe(texto_numero), border=1, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.set_xy(caja_x, 32)
    pdf.cell(caja_w, 5, _pdf_safe(EMPRESA_DIRECCION_LINEA1), align="C")
    pdf.set_xy(caja_x, 37)
    pdf.cell(caja_w, 5, _pdf_safe(EMPRESA_DIRECCION_LINEA2), align="C")
    pdf.set_text_color(0, 0, 0)

    def _fecha_legible(iso_txt):
        iso_txt = (iso_txt or "")[:10]
        if len(iso_txt) == 10 and iso_txt[4] == "-":
            return f"{iso_txt[8:10]}/{iso_txt[5:7]}/{iso_txt[0:4]}"
        return iso_txt

    total = None
    if p.get("precio_unidad") and p.get("cantidad_unidades"):
        total = float(p["precio_unidad"]) * float(p["cantidad_unidades"])

    dimensiones = None
    if p.get("dimension_ancho") or p.get("dimension_alto"):
        dimensiones = (
            f"{p.get('dimension_ancho') or '—'} x {p.get('dimension_alto') or '—'} "
            f"{p.get('dimension_unidad') or ''}"
        ).strip()

    box_w = 190

    def _caja(y0, titulo_caja, campos):
        fila_h = 8
        if titulo_caja:
            pdf.set_xy(10, y0)
            pdf.set_fill_color(20, 20, 20)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(box_w, 7, _pdf_safe(titulo_caja), border=0, align="C", fill=True)
            pdf.set_text_color(0, 0, 0)
            y0 += 7
        pdf.set_draw_color(150, 150, 150)
        pdf.rect(10, y0, box_w, fila_h * len(campos))
        for i, (etiqueta, valor) in enumerate(campos):
            fila_y = y0 + i * fila_h
            if i > 0:
                pdf.line(10, fila_y, 10 + box_w, fila_y)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_xy(13, fila_y + 2.3)
            pdf.cell(48, 5, _pdf_safe(etiqueta))
            pdf.set_font("Helvetica", "", 10)
            pdf.set_xy(61, fila_y + 2.3)
            pdf.cell(box_w - 54, 5, _pdf_safe(valor))
        return y0 + fila_h * len(campos)

    y = 52
    y = _caja(y, "DATOS DEL CLIENTE", [
        ("LÍNEA:", linea),
        ("FECHA:", _fecha_legible(p.get("creado_en")) or "—"),
        ("SOLICITA:", p.get("quien_solicita") or "—"),
        ("CLIENTE:", p.get("cliente_nombre") or "—"),
        ("TELÉFONO:", p.get("cliente_telefono") or "—"),
        ("CORREO:", p.get("cliente_correo") or "—"),
        ("NIT:", p.get("nit") or "—"),
        ("DIRECCIÓN DE ENTREGA:", p.get("direccion_entrega") or "—"),
    ])
    y += 6
    y = _caja(y, "DATOS DE LA PIEZA", [
        ("TIPO DE PIEZA:", p.get("tipo_pieza") or "—"),
        ("DIMENSIONES:", dimensiones or "—"),
        ("MATERIAL:", p.get("material") or "—"),
        ("TIPO DE COLOR:", p.get("tipo_color") or "—"),
        ("ACABADOS:", p.get("acabados") or "—"),
    ])
    y += 6
    y = _caja(y, "PRECIO Y ENTREGA", [
        ("PRECIO POR UNIDAD:", money(p["precio_unidad"]) if p.get("precio_unidad") else "—"),
        ("CANTIDAD:", str(p["cantidad_unidades"]) if p.get("cantidad_unidades") not in (None, "") else "—"),
        ("TOTAL:", money(total) if total is not None else "—"),
        ("FECHA DE ENTREGA:", _fecha_legible(p.get("fecha_entrega")) or "Sin definir"),
    ])
    y += 6

    # -- Notas adicionales ----------------------------------------------------
    pdf.set_xy(10, y)
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(box_w, 7, _pdf_safe("NOTAS ADICIONALES"), border=0, align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    y += 7
    pdf.set_font("Helvetica", "", 10)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_xy(10, y)
    texto_notas = _pdf_safe(p.get("notas") or "Sin notas.")
    lineas = pdf.multi_cell(box_w, 6, texto_notas, dry_run=True, output="LINES")
    alto_notas = max(16, len(lineas) * 6 + 4)
    pdf.multi_cell(box_w, 6, texto_notas, border=1)
    pdf.rect(10, y, box_w, alto_notas)
    y += alto_notas + 6

    # -- Archivos adjuntos (solo el nombre — pueden ser PDF, Word, Excel,
    # PSD o AI, formatos que fpdf2 no puede dibujar como imagen) ------------
    archivos = p.get("archivos") or []
    if y > 250:
        pdf.add_page()
        y = 15
    pdf.set_xy(10, y)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(90, 90, 90)
    if archivos:
        nombres = ", ".join(a.get("nombre") or "archivo" for a in archivos)
        pdf.multi_cell(box_w, 5, _pdf_safe(f"Archivos adjuntos ({len(archivos)}): {nombres}"))
    else:
        pdf.cell(box_w, 5, _pdf_safe("Sin archivos adjuntos."))
    pdf.set_text_color(0, 0, 0)
    y = pdf.get_y() + 14

    # -- Firmas: SOLICITA / PRODUCCIÓN ---------------------------------------
    if y > 255:
        pdf.add_page()
        y = 20
    pdf.set_draw_color(0, 0, 0)
    pdf.line(15, y, 95, y)
    pdf.line(115, y, 195, y)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(15, y + 2)
    pdf.cell(80, 5, _pdf_safe("SOLICITA"), align="C")
    pdf.set_xy(115, y + 2)
    pdf.cell(80, 5, _pdf_safe("PRODUCCIÓN"), align="C")
    pdf.set_xy(15, y + 7)
    pdf.cell(80, 5, _pdf_safe("Firma y Nombre"), align="C")
    pdf.set_xy(115, y + 7)
    pdf.cell(80, 5, _pdf_safe("Firma y Nombre"), align="C")

    return bytes(pdf.output())


def _tamano_ajustado(pdf, texto, familia, estilo, ancho_max, tam_inicial, tam_minimo):
    """Reduce el tamaño de fuente hasta que 'texto' quepa en 'ancho_max' (mm),
    sin bajar de 'tam_minimo' — para que un nombre o módulo largo no se salga
    del diploma en vez de recortarse a la mitad."""
    tam = tam_inicial
    while tam > tam_minimo:
        pdf.set_font(familia, estilo, tam)
        if pdf.get_string_width(texto) <= ancho_max:
            break
        tam -= 1
    pdf.set_font(familia, estilo, tam)
    return tam


def diploma_pdf_bytes(persona_nombre: str, tienda: str, modulo_nombre: str, fecha) -> bytes:
    """Genera el PDF del diploma de finalización de un módulo de Capacitación
    (hoja horizontal tipo certificado): logo de Visión Digital, nombre del
    empleado, tienda, módulo completado, fecha, y la firma de Steven Gabriel
    (Gerente Comercial) al calce. 'fecha' puede ser un date o un string
    'YYYY-MM-DD'."""
    fecha_txt = str(fecha)
    if len(fecha_txt) == 10 and fecha_txt[4] == "-":
        fecha_txt = f"{fecha_txt[8:10]}/{fecha_txt[5:7]}/{fecha_txt[0:4]}"

    pdf = FPDF(orientation="L", format="Letter")
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    ancho, alto = 279.4, 215.9  # Letter horizontal, en mm

    # -- Fondo y marco decorativo --------------------------------------------
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, ancho, alto, style="F")
    pdf.set_draw_color(255, 12, 130)  # BRAND_PINK
    pdf.set_line_width(2.2)
    pdf.rect(8, 8, ancho - 16, alto - 16)
    pdf.set_draw_color(20, 20, 20)
    pdf.set_line_width(0.4)
    pdf.rect(12.5, 12.5, ancho - 25, alto - 25)
    pdf.set_line_width(0.2)

    # -- Logo, centrado arriba (el logo real es ancho:alto ≈ 1 : 0.51) ----------
    try:
        logo_w = 50
        logo_h = logo_w * 0.5135
        pdf.image(LOGO_PATH, x=(ancho - logo_w) / 2, y=14, w=logo_w)
        y_cursor = 14 + logo_h + 7
    except Exception:
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(20, 20, 20)
        pdf.set_xy(0, 22)
        pdf.cell(ancho, 10, _pdf_safe(EMPRESA_NOMBRE), align="C")
        y_cursor = 40

    # -- Título -----------------------------------------------------------------
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(0, y_cursor)
    pdf.cell(ancho, 14, _pdf_safe("DIPLOMA DE FINALIZACIÓN"), align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(90, 90, 90)
    pdf.set_xy(0, y_cursor + 13)
    pdf.cell(ancho, 8, _pdf_safe("Programa de Capacitación - Visión Digital"), align="C")

    # -- "Se otorga a" + nombre del empleado -------------------------------------
    pdf.set_text_color(90, 90, 90)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(0, y_cursor + 30)
    pdf.cell(ancho, 8, _pdf_safe("Se otorga el presente reconocimiento a"), align="C")

    pdf.set_text_color(255, 12, 130)  # BRAND_PINK
    nombre_txt = _pdf_safe(persona_nombre or "—")
    _tamano_ajustado(pdf, nombre_txt, "Times", "BI", ancho - 40, 34, 14)
    pdf.set_xy(0, y_cursor + 39)
    pdf.cell(ancho, 16, nombre_txt, align="C")

    # -- Texto de logro + módulo --------------------------------------------------
    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(0, y_cursor + 58)
    pdf.cell(
        ancho, 7,
        _pdf_safe("por haber completado satisfactoriamente el módulo de capacitación"), align="C",
    )

    pdf.set_text_color(20, 20, 20)
    modulo_txt = _pdf_safe(f"«{modulo_nombre or '—'}»")
    _tamano_ajustado(pdf, modulo_txt, "Helvetica", "B", ancho - 40, 18, 11)
    pdf.set_xy(0, y_cursor + 67)
    pdf.cell(ancho, 10, modulo_txt, align="C")

    pdf.set_text_color(90, 90, 90)
    pdf.set_font("Helvetica", "I", 11)
    pdf.set_xy(0, y_cursor + 79)
    pdf.cell(ancho, 7, _pdf_safe(f"Tienda: {tienda or '—'}"), align="C")

    # -- Firma y fecha, al calce --------------------------------------------------
    firmas_y = alto - 42
    # Izquierda: fecha
    pdf.set_draw_color(120, 120, 120)
    pdf.line(38, firmas_y, 118, firmas_y)
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(38, firmas_y + 2)
    pdf.cell(80, 6, _pdf_safe(fecha_txt or "—"), align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.set_xy(38, firmas_y + 8)
    pdf.cell(80, 5, _pdf_safe("Fecha de finalización"), align="C")

    # Derecha: firma escaneada + nombre y puesto — la firma se centra sobre
    # el mismo bloque (161 a 241) que la línea, el nombre y el puesto, para
    # que quede justo encima de "Steven Gabriel" y no desplazada.
    try:
        firma_w = 46
        pdf.image(FIRMA_STEVEN_PATH, x=161 + (80 - firma_w) / 2, y=firmas_y - 18, w=firma_w)
    except Exception:
        pass
    pdf.set_draw_color(120, 120, 120)
    pdf.line(161, firmas_y, 241, firmas_y)
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(161, firmas_y + 2)
    pdf.cell(80, 6, _pdf_safe(FIRMA_STEVEN_NOMBRE), align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.set_xy(161, firmas_y + 8)
    pdf.cell(80, 5, _pdf_safe(FIRMA_STEVEN_PUESTO), align="C")

    return bytes(pdf.output())
