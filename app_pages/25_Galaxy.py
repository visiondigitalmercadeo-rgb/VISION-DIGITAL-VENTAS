import base64
from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import (
    APP_URL, COLORADO_DIMENSION_UNIDADES, COLORADO_TIPOS_COLOR, DISENO_ARCHIVO_MAX_BYTES,
    DISENO_ARCHIVO_MAX_BYTES_STORAGE, ESTADOS_GALAXY, PRODUCCION_ARCHIVOS_MAX,
)
from utils import (
    archivo_a_b64, archivos_a_b64_lista, download_excel_button, money, orden_produccion_pdf_bytes,
    sidebar_user_box,
)

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_galaxy()

_usa_storage = db.storage_disponible()
_archivo_max_bytes = DISENO_ARCHIVO_MAX_BYTES_STORAGE if _usa_storage else DISENO_ARCHIVO_MAX_BYTES
_TIPOS_ARCHIVO_ORDEN = ["pdf", "ai", "psd", "jpg", "jpeg", "doc", "docx", "xls", "xlsx"]
_TIPOS_BOLETA_PAGO = ["pdf", "jpg", "jpeg", "png"]


def _caption_limite_archivo():
    if _usa_storage:
        st.caption(f"Tamaño máximo por archivo: {_archivo_max_bytes // 1_000_000} MB.")
    else:
        st.caption(f"Tamaño máximo por archivo: {_archivo_max_bytes // 1000} KB.")


def _subir_archivos_orden(archivos_subidos):
    """Sube los archivos adjuntos a Firebase Storage si está disponible; si
    no, cae al guardado anterior (base64 dentro del documento)."""
    if _usa_storage:
        return db.subir_archivos_storage_lista(
            "galaxy", archivos_subidos, _archivo_max_bytes, PRODUCCION_ARCHIVOS_MAX,
        )
    return archivos_a_b64_lista(archivos_subidos, _archivo_max_bytes, PRODUCCION_ARCHIVOS_MAX)


def _subir_boleta_pago(archivo_subido):
    """Sube la boleta de pago (un solo archivo, aparte de los archivos de
    diseño) a Firebase Storage si está disponible; si no, cae al guardado
    anterior (base64 dentro del documento). Retorna None si no se subió
    ningún archivo."""
    if archivo_subido is None:
        return None
    if len(archivo_subido.getvalue()) > _archivo_max_bytes:
        raise ValueError(
            f"La boleta de pago pesa {len(archivo_subido.getvalue()) / 1_000_000:.1f} MB; el máximo "
            f"permitido por archivo es {_archivo_max_bytes / 1_000_000:.0f} MB."
        )
    if _usa_storage:
        return db.subir_archivo_storage("galaxy_boletas", archivo_subido)
    nombre, tipo, b64 = archivo_a_b64(archivo_subido, _archivo_max_bytes)
    return {"nombre": nombre, "tipo": tipo, "b64": b64}


st.title("🖨️ Galaxy")
st.caption(
    "Órdenes de producción de la planta Galaxy: arriba, el cronograma con la fecha de entrega de "
    "cada orden; abajo, el tablero de producción (mismo concepto que Phara) para dar seguimiento a "
    "cada una — cada orden es la misma tarjeta en los dos lugares."
    + ("" if puede_editar else " Tu acceso es solo de consulta: puedes ver todo, pero no crear ni mover nada.")
)

COLUMN_EMOJI = {
    "Nuevo": "🆕", "En producción": "🏭", "Acabados": "✂️", "Entregado": "✅",
}
VENCIDO_BG = "#fbe3e3"  # rojo leve — mismo estilo que el resaltado magenta de 'Ventas por mes'

pedidos = db.list_galaxy_pedidos()
hoy = date.today()


def _es_vencido(p):
    # Una orden ya entregada no cuenta como "vencida" aunque su fecha de
    # entrega programada haya quedado en el pasado.
    if p.get("estado") == "Entregado":
        return False
    fe = p.get("fecha_entrega")
    return bool(fe) and fe < str(hoy)


def _siguiente_estado(estado_actual):
    """Etapa que sigue en el orden del tablero, o None si ya está en la
    última columna ('Entregado')."""
    if estado_actual not in ESTADOS_GALAXY:
        return None
    i = ESTADOS_GALAXY.index(estado_actual)
    return ESTADOS_GALAXY[i + 1] if i + 1 < len(ESTADOS_GALAXY) else None


def _total_pedido(p):
    """Precio por unidad × cantidad de unidades, o None si falta alguno de
    los dos datos (se calcula, no se guarda aparte, para que nunca quede
    desactualizado si se corrige el precio o la cantidad)."""
    precio = p.get("precio_unidad")
    cantidad = p.get("cantidad_unidades")
    if not precio or not cantidad:
        return None
    return float(precio) * float(cantidad)


def _dimensiones_texto(p):
    ancho, alto, unidad = p.get("dimension_ancho"), p.get("dimension_alto"), p.get("dimension_unidad")
    if not ancho and not alto:
        return None
    return f"{ancho or '—'} x {alto or '—'} {unidad or ''}".strip()


def _render_detalle_pedido(p, key_prefix):
    """Bloque de datos + descargas de una orden (contacto, pieza, precio,
    archivos adjuntos, boleta de pago) — compartido entre la tarjeta del
    tablero y el detalle del Historial de abajo, para no repetir la misma
    lógica en dos lugares. 'key_prefix' evita choques de key entre ambos
    lugares cuando se muestra la MISMA orden en los dos a la vez."""
    pid = p["id"]
    if p.get("quien_solicita"):
        st.caption(f"🙋 Solicita: {p['quien_solicita']}")
    if p.get("tipo_pieza"):
        st.caption(f"🧩 {p['tipo_pieza']}")
    if p.get("cliente_telefono") or p.get("cliente_correo"):
        st.caption(f"☎️ {p.get('cliente_telefono') or '—'}  ·  ✉️ {p.get('cliente_correo') or '—'}")
    if p.get("nit"):
        st.caption(f"🧾 NIT: {p['nit']}")
    if p.get("direccion_entrega"):
        st.caption(f"📍 {p['direccion_entrega']}")
    dimensiones_txt = _dimensiones_texto(p)
    if dimensiones_txt:
        st.caption(f"📐 {dimensiones_txt}")
    if p.get("material"):
        st.caption(f"🧵 Material: {p['material']}")
    if p.get("tipo_color"):
        st.caption(f"🎨 {p['tipo_color']}")
    if p.get("acabados"):
        st.caption(f"✨ Acabados: {p['acabados']}")
    if p.get("cantidad_unidades") not in (None, "", 0):
        st.caption(f"Cantidad: {p['cantidad_unidades']}")
    if p.get("precio_unidad") not in (None, "", 0):
        st.caption(f"Precio por unidad: {money(p['precio_unidad'])}")
    total_pedido = _total_pedido(p)
    if total_pedido is not None:
        st.caption(f"💲 Total: {money(total_pedido)}")
    if p.get("notas"):
        st.caption(f"📝 {p['notas']}")
    st.caption(f"📅 Entrega: {p.get('fecha_entrega') or 'sin definir'}")
    st.caption(f"🕒 {(p.get('creado_en') or '')[:16].replace('T', ' ')}")

    pdf_bytes = orden_produccion_pdf_bytes(p, linea="Galaxy")
    st.download_button(
        "📄 Orden de producción (PDF)", data=pdf_bytes,
        file_name=f"orden_produccion_galaxy_{pid}.pdf",
        mime="application/pdf", use_container_width=True, key=f"{key_prefix}_pdf_{pid}",
    )
    for i, arch in enumerate(p.get("archivos") or []):
        if arch.get("storage_path"):
            url_archivo = db.url_descarga_archivo_storage(
                arch["storage_path"], nombre_descarga=arch["nombre"],
            )
            if url_archivo:
                st.link_button(
                    f"📎 {arch['nombre']}", url_archivo,
                    use_container_width=True, key=f"{key_prefix}_file_{pid}_{i}",
                )
            else:
                st.caption(f"📎 {arch['nombre']} (no se pudo generar el enlace de descarga)")
        else:
            st.download_button(
                f"📎 {arch['nombre']}",
                data=base64.b64decode(arch["b64"]),
                file_name=arch["nombre"],
                mime=arch.get("tipo") or "application/octet-stream",
                use_container_width=True, key=f"{key_prefix}_file_{pid}_{i}",
            )

    boleta_pago = p.get("boleta_pago")
    if boleta_pago:
        if boleta_pago.get("storage_path"):
            url_boleta = db.url_descarga_archivo_storage(
                boleta_pago["storage_path"], nombre_descarga=boleta_pago["nombre"],
            )
            if url_boleta:
                st.link_button(
                    f"🧾 Boleta de pago: {boleta_pago['nombre']}", url_boleta,
                    use_container_width=True, key=f"{key_prefix}_boleta_{pid}",
                )
            else:
                st.caption(
                    f"🧾 Boleta de pago: {boleta_pago['nombre']} (no se pudo generar el enlace de descarga)"
                )
        else:
            st.download_button(
                f"🧾 Boleta de pago: {boleta_pago['nombre']}",
                data=base64.b64decode(boleta_pago["b64"]),
                file_name=boleta_pago["nombre"],
                mime=boleta_pago.get("tipo") or "application/octet-stream",
                use_container_width=True, key=f"{key_prefix}_boleta_{pid}",
            )
    else:
        st.caption("🧾 Boleta de pago: no se ha subido.")


def _avisar_por_correo(asunto, cuerpo):
    """Manda un aviso a los correos configurados (ver abajo). No hace nada
    (ni muestra error) si todavía no hay correos guardados o si el correo
    remitente no está configurado — ver database.correo_disponible."""
    correos = db.get_galaxy_correos_aviso()
    if correos:
        db.enviar_correo_aviso(correos, asunto, cuerpo + f"\n\nVer en la plataforma: {APP_URL}")


if puede_editar:
    with st.expander("✉️ Avisos por correo (orden nueva o cambio de columna)"):
        if not db.correo_disponible():
            st.info(
                "Todavía no está configurado el correo que manda los avisos (falta conectar una cuenta "
                "de Gmail en la configuración de la plataforma) — mientras tanto, esta sección no manda "
                "nada, pero puedes ir guardando los correos de una vez."
            )
        correos_actuales = db.get_galaxy_correos_aviso()
        with st.form("galaxy_correos_aviso"):
            correos_texto = st.text_area(
                "Correos que reciben el aviso — uno por línea (o separados por coma)",
                value="\n".join(correos_actuales),
                help="Se les avisa automáticamente cuando se agrega una orden nueva o cuando una tarjeta "
                     "cambia de columna en el tablero (no en otros cambios menores, como corregir una nota).",
            )
            if st.form_submit_button("💾 Guardar correos", use_container_width=True):
                nuevos_correos = [c.strip() for c in correos_texto.replace(",", "\n").split("\n") if c.strip()]
                db.set_galaxy_correos_aviso(nuevos_correos)
                st.success("Correos actualizados.")
                st.rerun()


# ---------------------------------------------------------------------------
# Cronograma de entregas (arriba)
# ---------------------------------------------------------------------------
st.markdown("#### 📅 Cronograma de entregas")

vencidos = [p for p in pedidos if _es_vencido(p)]
if vencidos:
    st.warning(f"⚠️ Hay {len(vencidos)} orden(es) con la fecha de entrega ya vencida (resaltadas abajo en rojo).")

if not pedidos:
    st.info("Todavía no hay órdenes registradas para Galaxy.")
else:
    pedidos_cronograma = sorted(pedidos, key=lambda p: p.get("fecha_entrega") or "9999-99-99")
    df_cron = pd.DataFrame([{
        "Solicita": p.get("quien_solicita") or "—",
        "Cliente": p.get("cliente_nombre") or "—",
        "Tipo de pieza": p.get("tipo_pieza") or "—",
        "Cantidad": p.get("cantidad_unidades") if p.get("cantidad_unidades") not in (None, "") else "—",
        "Total": money(_total_pedido(p)) if _total_pedido(p) is not None else "—",
        "Fecha de entrega": p.get("fecha_entrega") or "Sin definir",
        "Etapa": f"{COLUMN_EMOJI.get(p.get('estado'), '')} {p.get('estado') or '—'}",
        "_vencido": _es_vencido(p),
    } for p in pedidos_cronograma])
    styler = df_cron.drop(columns=["_vencido"]).style.apply(
        lambda _: [f"background-color: {VENCIDO_BG}" if v else "" for v in df_cron["_vencido"]], axis=0,
    )
    st.dataframe(styler, use_container_width=True, hide_index=True)

    total_cantidad_cron = sum(
        p["cantidad_unidades"] for p in pedidos_cronograma if p.get("cantidad_unidades") not in (None, "")
    )
    total_monto_cron = sum(_total_pedido(p) or 0 for p in pedidos_cronograma)
    kpi_cron1, kpi_cron2, kpi_cron3 = st.columns(3)
    kpi_cron1.metric("📦 Órdenes en el cronograma", len(pedidos_cronograma))
    kpi_cron2.metric("🔢 Cantidad total de unidades", f"{total_cantidad_cron:,.0f}")
    kpi_cron3.metric("💲 Monto total", money(total_monto_cron))

if puede_editar:
    with st.expander("➕ Agregar orden nueva"):
        with st.form("galaxy_nuevo_pedido", clear_on_submit=True):
            quien_solicita_n = st.text_input(
                "¿Quién solicita? (persona interna que hace el pedido, opcional)",
            )
            st.markdown("**Datos del cliente**")
            cliente_nombre_n = st.text_input("Nombre del cliente")
            c1, c2 = st.columns(2)
            cliente_telefono_n = c1.text_input("Número tel. del cliente (opcional)")
            cliente_correo_n = c2.text_input("Correo electrónico del cliente (opcional)")
            nit_n = st.text_input("NIT del cliente (opcional)")
            direccion_entrega_n = st.text_area("Dirección de entrega (opcional)")

            st.markdown("**Datos de la pieza**")
            tipo_pieza_n = st.text_input("Tipo de pieza (opcional)")
            c3, c4, c5 = st.columns(3)
            dim_ancho_n = c3.number_input("Ancho del arte", min_value=0.0, step=0.1, value=0.0)
            dim_alto_n = c4.number_input("Alto del arte", min_value=0.0, step=0.1, value=0.0)
            dim_unidad_n = c5.selectbox("Unidad", COLORADO_DIMENSION_UNIDADES)
            material_n = st.text_input("Papel o material a usar (opcional)")
            tipo_color_n = st.selectbox("Tipo de color", COLORADO_TIPOS_COLOR)
            acabados_n = st.text_input("Acabados (opcional)")

            st.markdown("**Precio y cantidad**")
            c6, c7 = st.columns(2)
            precio_unidad_n = c6.number_input("Precio por unidad (Q)", min_value=0.0, step=0.01, value=0.0)
            cantidad_unidades_n = c7.number_input("Cantidad de unidades", min_value=0, step=1, value=0)
            if precio_unidad_n and cantidad_unidades_n:
                st.caption(f"Total: {money(precio_unidad_n * cantidad_unidades_n)}")

            notas_n = st.text_area("Notas adicionales (opcional)")
            fecha_entrega_n = st.date_input("Fecha de entrega (opcional)", value=None)

            archivos_n = st.file_uploader(
                f"Adjuntar archivos (opcional, máximo {PRODUCCION_ARCHIVOS_MAX}) — "
                "PDF, AI, PSD, JPEG, Word o Excel",
                type=_TIPOS_ARCHIVO_ORDEN, accept_multiple_files=True,
            )
            _caption_limite_archivo()
            boleta_pago_n = st.file_uploader(
                "🧾 Boleta de pago (comprobante de pago, opcional) — PDF, JPG o PNG",
                type=_TIPOS_BOLETA_PAGO, accept_multiple_files=False,
            )
            _caption_limite_archivo()

            if st.form_submit_button(f"Agregar a {ESTADOS_GALAXY[0]}", use_container_width=True):
                error_msg = None
                if not cliente_nombre_n.strip():
                    error_msg = "El nombre del cliente es obligatorio."
                else:
                    try:
                        archivos_subidos = _subir_archivos_orden(archivos_n)
                        boleta_pago_subida = _subir_boleta_pago(boleta_pago_n)
                    except ValueError as e:
                        error_msg = str(e)

                if error_msg:
                    st.error(error_msg)
                else:
                    datos = {
                        "quien_solicita": quien_solicita_n.strip() or None,
                        "cliente_nombre": cliente_nombre_n.strip(),
                        "cliente_telefono": cliente_telefono_n.strip() or None,
                        "cliente_correo": cliente_correo_n.strip() or None,
                        "nit": nit_n.strip() or None,
                        "direccion_entrega": direccion_entrega_n.strip() or None,
                        "tipo_pieza": tipo_pieza_n.strip() or None,
                        "dimension_ancho": dim_ancho_n or None,
                        "dimension_alto": dim_alto_n or None,
                        "dimension_unidad": dim_unidad_n,
                        "material": material_n.strip() or None,
                        "tipo_color": tipo_color_n,
                        "acabados": acabados_n.strip() or None,
                        "precio_unidad": precio_unidad_n or None,
                        "cantidad_unidades": cantidad_unidades_n or None,
                        "notas": notas_n.strip() or None,
                        "fecha_entrega": str(fecha_entrega_n) if fecha_entrega_n else None,
                        "archivos": archivos_subidos,
                        "boleta_pago": boleta_pago_subida,
                    }
                    db.create_galaxy_pedido(datos, creado_por_id=user["id"])
                    total_txt = money(precio_unidad_n * cantidad_unidades_n) if (precio_unidad_n and cantidad_unidades_n) else "—"
                    _avisar_por_correo(
                        f"Galaxy — Nueva orden: {cliente_nombre_n.strip()}",
                        f"Se agregó una nueva orden de producción en Galaxy.\n\n"
                        f"Solicita: {quien_solicita_n.strip() or '—'}\n"
                        f"Cliente: {cliente_nombre_n.strip()}\n"
                        f"Tipo de pieza: {tipo_pieza_n.strip() or '—'}\n"
                        f"Cantidad: {cantidad_unidades_n or '—'}\n"
                        f"Total: {total_txt}\n"
                        f"Fecha de entrega: {fecha_entrega_n or 'sin definir'}\n\n"
                        f"Etapa: {ESTADOS_GALAXY[0]}",
                    )
                    st.success(f"Orden agregada al cronograma y a la columna '{ESTADOS_GALAXY[0]}' del tablero.")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Tablero de producción e Historial de órdenes entregadas, como dos pestañas.
# ---------------------------------------------------------------------------
tab_tablero, tab_historial = st.tabs([
    "🗂️ Tablero de producción", "📜 Historial de órdenes entregadas",
])

with tab_tablero:
    if not puede_editar:
        st.caption("Tu acceso es de solo consulta para este tablero.")

    cols = st.columns(len(ESTADOS_GALAXY))
    for col, estado in zip(cols, ESTADOS_GALAXY):
        items = [p for p in pedidos if p.get("estado") == estado]
        with col:
            st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
            if not items:
                st.caption("Sin órdenes.")
            for p in items:
                with st.container(border=True):
                    pid = p["id"]
                    editando_key = f"galaxy_editando_{pid}"

                    title_col2, edit_col = st.columns([5, 1])
                    with title_col2:
                        vencido_marca = "🔴 " if _es_vencido(p) else ""
                        st.markdown(f"{vencido_marca}**{p.get('cliente_nombre') or 'Sin cliente'}**")
                    with edit_col:
                        if puede_editar:
                            if st.button("✏️", key=f"galaxy_editar_{pid}", help="Editar esta orden"):
                                st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                                st.rerun()

                    _render_detalle_pedido(p, "galaxy")

                    # ------------------------------------------------------------
                    # Acciones rápidas: pasar a la siguiente etapa y eliminar,
                    # directo desde la tarjeta (sin tener que abrir el formulario
                    # de edición) — mismo estilo que Phara.
                    # ------------------------------------------------------------
                    if puede_editar:
                        siguiente = _siguiente_estado(p.get("estado"))
                        accion_col1, accion_col2 = st.columns(2)
                        with accion_col1:
                            if siguiente:
                                if st.button(
                                    f"➡️ {siguiente}", key=f"galaxy_avanzar_{pid}", use_container_width=True,
                                    help=f"Pasar a la columna «{siguiente}»",
                                ):
                                    db.update_galaxy_pedido(pid, estado=siguiente)
                                    _avisar_por_correo(
                                        f"Galaxy — {p.get('cliente_nombre') or 'Orden'} pasó a '{siguiente}'",
                                        f"La orden de '{p.get('cliente_nombre') or 'cliente'}' cambió de columna en "
                                        f"el tablero.\n\n"
                                        f"De: {p.get('estado') or '—'}\nA: {siguiente}\n\n"
                                        f"Fecha de entrega: {p.get('fecha_entrega') or 'sin definir'}",
                                    )
                                    st.success(f"Orden movida a «{siguiente}».")
                                    st.rerun()
                        with accion_col2:
                            if st.button(
                                "🗑️ Eliminar", key=f"galaxy_borrar_{pid}", use_container_width=True,
                            ):
                                db.delete_galaxy_pedido(pid)
                                st.session_state.pop(editando_key, None)
                                st.success("Orden eliminada.")
                                st.rerun()

                    if puede_editar and st.session_state.get(editando_key):
                        with st.form(f"galaxy_gestionar_{pid}"):
                            quien_solicita_ed = st.text_input(
                                "¿Quién solicita? (persona interna que hace el pedido, opcional)",
                                value=p.get("quien_solicita") or "",
                            )
                            st.markdown("**Datos del cliente**")
                            cliente_nombre_ed = st.text_input(
                                "Nombre del cliente", value=p.get("cliente_nombre") or "",
                            )
                            ce1, ce2 = st.columns(2)
                            cliente_telefono_ed = ce1.text_input(
                                "Número tel. del cliente (opcional)", value=p.get("cliente_telefono") or "",
                            )
                            cliente_correo_ed = ce2.text_input(
                                "Correo electrónico del cliente (opcional)", value=p.get("cliente_correo") or "",
                            )
                            nit_ed = st.text_input("NIT del cliente (opcional)", value=p.get("nit") or "")
                            direccion_entrega_ed = st.text_area(
                                "Dirección de entrega (opcional)", value=p.get("direccion_entrega") or "",
                            )

                            st.markdown("**Datos de la pieza**")
                            tipo_pieza_ed = st.text_input("Tipo de pieza (opcional)", value=p.get("tipo_pieza") or "")
                            ce3, ce4, ce5 = st.columns(3)
                            dim_ancho_ed = ce3.number_input(
                                "Ancho del arte", min_value=0.0, step=0.1, value=float(p.get("dimension_ancho") or 0),
                            )
                            dim_alto_ed = ce4.number_input(
                                "Alto del arte", min_value=0.0, step=0.1, value=float(p.get("dimension_alto") or 0),
                            )
                            dim_unidad_ed = ce5.selectbox(
                                "Unidad", COLORADO_DIMENSION_UNIDADES,
                                index=COLORADO_DIMENSION_UNIDADES.index(p["dimension_unidad"])
                                if p.get("dimension_unidad") in COLORADO_DIMENSION_UNIDADES else 0,
                            )
                            material_ed = st.text_input(
                                "Papel o material a usar (opcional)", value=p.get("material") or "",
                            )
                            tipo_color_ed = st.selectbox(
                                "Tipo de color", COLORADO_TIPOS_COLOR,
                                index=COLORADO_TIPOS_COLOR.index(p["tipo_color"])
                                if p.get("tipo_color") in COLORADO_TIPOS_COLOR else 0,
                            )
                            acabados_ed = st.text_input("Acabados (opcional)", value=p.get("acabados") or "")

                            st.markdown("**Precio y cantidad**")
                            ce6, ce7 = st.columns(2)
                            precio_unidad_ed = ce6.number_input(
                                "Precio por unidad (Q)", min_value=0.0, step=0.01,
                                value=float(p.get("precio_unidad") or 0),
                            )
                            cantidad_unidades_ed = ce7.number_input(
                                "Cantidad de unidades", min_value=0, step=1,
                                value=int(p.get("cantidad_unidades") or 0),
                            )
                            if precio_unidad_ed and cantidad_unidades_ed:
                                st.caption(f"Total: {money(precio_unidad_ed * cantidad_unidades_ed)}")

                            notas_ed = st.text_area("Notas adicionales", value=p.get("notas") or "")

                            archivos_actuales = p.get("archivos") or []
                            st.caption(
                                f"Archivos actuales: {', '.join(a['nombre'] for a in archivos_actuales)}"
                                if archivos_actuales else "Archivos actuales: ninguno."
                            )
                            nuevos_archivos_ed = st.file_uploader(
                                f"Reemplazar archivos adjuntos (opcional, máximo {PRODUCCION_ARCHIVOS_MAX})",
                                type=_TIPOS_ARCHIVO_ORDEN, accept_multiple_files=True,
                                key=f"galaxy_archivo_ed_{pid}",
                                help="Si subes archivos aquí, reemplazan a TODOS los actuales. Déjalo vacío para no cambiarlos.",
                            )
                            _caption_limite_archivo()

                            boleta_pago_actual = p.get("boleta_pago")
                            st.caption(
                                f"Boleta de pago actual: {boleta_pago_actual['nombre']}"
                                if boleta_pago_actual else "Boleta de pago actual: ninguna."
                            )
                            nueva_boleta_ed = st.file_uploader(
                                "🧾 Reemplazar boleta de pago (opcional) — PDF, JPG o PNG",
                                type=_TIPOS_BOLETA_PAGO, accept_multiple_files=False,
                                key=f"galaxy_boleta_ed_{pid}",
                                help="Si subes un archivo aquí, reemplaza la boleta actual. Déjalo vacío para no cambiarla.",
                            )
                            _caption_limite_archivo()

                            fecha_entrega_ed = st.date_input(
                                "Fecha de entrega (opcional)",
                                value=date.fromisoformat(p["fecha_entrega"]) if p.get("fecha_entrega") else None,
                            )
                            estado_ed = st.selectbox(
                                "Etapa (columna del tablero)", ESTADOS_GALAXY,
                                index=ESTADOS_GALAXY.index(p["estado"]) if p.get("estado") in ESTADOS_GALAXY else 0,
                                help="Además de «➡️» (que avanza a la siguiente), aquí puedes mandar la "
                                     "orden a cualquier columna, incluso hacia atrás si fue un error.",
                            )

                            colf1, colf2 = st.columns(2)
                            guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
                            cancelar = colf2.form_submit_button("Cancelar", use_container_width=True)

                            if guardar:
                                error_msg = None
                                update_kwargs = {
                                    "quien_solicita": quien_solicita_ed.strip() or None,
                                    "cliente_nombre": cliente_nombre_ed.strip(),
                                    "cliente_telefono": cliente_telefono_ed.strip() or None,
                                    "cliente_correo": cliente_correo_ed.strip() or None,
                                    "nit": nit_ed.strip() or None,
                                    "direccion_entrega": direccion_entrega_ed.strip() or None,
                                    "tipo_pieza": tipo_pieza_ed.strip() or None,
                                    "dimension_ancho": dim_ancho_ed or None,
                                    "dimension_alto": dim_alto_ed or None,
                                    "dimension_unidad": dim_unidad_ed,
                                    "material": material_ed.strip() or None,
                                    "tipo_color": tipo_color_ed,
                                    "acabados": acabados_ed.strip() or None,
                                    "precio_unidad": precio_unidad_ed or None,
                                    "cantidad_unidades": cantidad_unidades_ed or None,
                                    "notas": notas_ed.strip() or None,
                                    "fecha_entrega": str(fecha_entrega_ed) if fecha_entrega_ed else None,
                                    "estado": estado_ed,
                                }
                                archivos_a_reemplazar = None
                                boleta_a_reemplazar = None
                                if not cliente_nombre_ed.strip():
                                    error_msg = "El nombre del cliente es obligatorio."
                                else:
                                    if nuevos_archivos_ed:
                                        try:
                                            update_kwargs["archivos"] = _subir_archivos_orden(nuevos_archivos_ed)
                                            # Los archivos actuales se borran de Storage recién
                                            # después de guardar el reemplazo con éxito (más abajo).
                                            archivos_a_reemplazar = archivos_actuales
                                        except ValueError as e:
                                            error_msg = str(e)
                                    if not error_msg and nueva_boleta_ed is not None:
                                        try:
                                            update_kwargs["boleta_pago"] = _subir_boleta_pago(nueva_boleta_ed)
                                            boleta_a_reemplazar = boleta_pago_actual
                                        except ValueError as e:
                                            error_msg = str(e)

                                if error_msg:
                                    st.error(error_msg)
                                else:
                                    cambio_de_columna = estado_ed != p.get("estado")
                                    db.update_galaxy_pedido(pid, **update_kwargs)
                                    if archivos_a_reemplazar:
                                        db.eliminar_archivos_storage(archivos_a_reemplazar)
                                    if boleta_a_reemplazar:
                                        db.eliminar_archivos_storage([boleta_a_reemplazar])
                                    if cambio_de_columna:
                                        _avisar_por_correo(
                                            f"Galaxy — {cliente_nombre_ed.strip()} pasó a '{estado_ed}'",
                                            f"La orden de '{cliente_nombre_ed.strip()}' cambió de columna en el "
                                            f"tablero.\n\n"
                                            f"De: {p.get('estado') or '—'}\n"
                                            f"A: {estado_ed}\n\n"
                                            f"Fecha de entrega: {fecha_entrega_ed or 'sin definir'}",
                                        )
                                    st.session_state.pop(editando_key, None)
                                    st.success("Orden actualizada.")
                                    st.rerun()
                            if cancelar:
                                st.session_state.pop(editando_key, None)
                                st.rerun()

with tab_historial:
    st.caption(
        "Busca cualquier orden ya entregada para volver a ver sus datos, descargar su PDF, sus archivos "
        "adjuntos o su boleta de pago."
    )

    entregados = [p for p in pedidos if p.get("estado") == "Entregado"]

    if not entregados:
        st.info("Todavía no hay órdenes marcadas como 'Entregado'.")
    else:
        busqueda_hist = st.text_input(
            "🔎 Buscar por cliente, quién solicita, tipo de pieza o NIT",
            key="galaxy_hist_buscar",
        )

        def _coincide_busqueda_galaxy(p, texto):
            texto = texto.strip().lower()
            if not texto:
                return True
            campos = [p.get("cliente_nombre"), p.get("quien_solicita"), p.get("tipo_pieza"), p.get("nit")]
            return any(texto in str(c).lower() for c in campos if c)

        entregados_filtrados = [p for p in entregados if _coincide_busqueda_galaxy(p, busqueda_hist)]
        entregados_filtrados = sorted(
            entregados_filtrados, key=lambda p: p.get("creado_en") or "", reverse=True,
        )

        if not entregados_filtrados:
            st.caption("Ninguna orden entregada coincide con esa búsqueda.")
        else:
            opciones_hist = {
                f"{p.get('cliente_nombre') or 'Sin cliente'} — {p.get('tipo_pieza') or 'sin tipo'} "
                f"({(p.get('creado_en') or '')[:10]})": p["id"]
                for p in entregados_filtrados
            }
            seleccion_hist = st.selectbox(
                "Elegir orden para ver el detalle", list(opciones_hist.keys()), key="galaxy_hist_selector",
            )
            if seleccion_hist:
                pid_hist = opciones_hist[seleccion_hist]
                p_hist = next(p for p in entregados_filtrados if p["id"] == pid_hist)
                with st.container(border=True):
                    st.markdown(f"**{p_hist.get('cliente_nombre') or 'Sin cliente'}**")
                    _render_detalle_pedido(p_hist, "galaxy_hist")

            st.divider()
            df_hist = pd.DataFrame([{
                "Solicita": p.get("quien_solicita") or "—",
                "Cliente": p.get("cliente_nombre") or "—",
                "Tipo de pieza": p.get("tipo_pieza") or "—",
                "NIT": p.get("nit") or "—",
                "Cantidad": p.get("cantidad_unidades") if p.get("cantidad_unidades") not in (None, "") else "—",
                "Total": money(_total_pedido(p)) if _total_pedido(p) is not None else "—",
                "Fecha de entrega": p.get("fecha_entrega") or "—",
                "Creado": (p.get("creado_en") or "")[:10],
            } for p in entregados_filtrados])
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            download_excel_button(
                df_hist, "historial_galaxy_entregados.xlsx", key="galaxy_hist_descargar_excel",
            )
