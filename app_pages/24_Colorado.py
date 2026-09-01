from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import APP_URL, ESTADOS_COLORADO
from utils import sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_colorado()

st.title("🏭 Colorado")
st.caption(
    "Órdenes de producción de la planta Colorado: arriba, el cronograma con la fecha de entrega de "
    "cada orden; abajo, el tablero de producción (mismo concepto que Phara) para dar seguimiento a "
    "cada una — cada orden es la misma tarjeta en los dos lugares."
    + ("" if puede_editar else " Tu acceso es solo de consulta: puedes ver todo, pero no crear ni mover nada.")
)

COLUMN_EMOJI = {
    "Nuevo": "🆕", "En producción": "🏭", "Acabados": "✂️", "Entregado": "✅",
}
VENCIDO_BG = "#fbe3e3"  # rojo leve — mismo estilo que el resaltado magenta de 'Ventas por mes'

pedidos = db.list_colorado_pedidos()
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
    if estado_actual not in ESTADOS_COLORADO:
        return None
    i = ESTADOS_COLORADO.index(estado_actual)
    return ESTADOS_COLORADO[i + 1] if i + 1 < len(ESTADOS_COLORADO) else None


def _avisar_por_correo(asunto, cuerpo):
    """Manda un aviso a los correos configurados (ver abajo). No hace nada
    (ni muestra error) si todavía no hay correos guardados o si el correo
    remitente no está configurado — ver database.correo_disponible."""
    correos = db.get_colorado_correos_aviso()
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
        correos_actuales = db.get_colorado_correos_aviso()
        with st.form("colorado_correos_aviso"):
            correos_texto = st.text_area(
                "Correos que reciben el aviso — uno por línea (o separados por coma)",
                value="\n".join(correos_actuales),
                help="Se les avisa automáticamente cuando se agrega una orden nueva o cuando una tarjeta "
                     "cambia de columna en el tablero (no en otros cambios menores, como corregir una nota).",
            )
            if st.form_submit_button("💾 Guardar correos", use_container_width=True):
                nuevos_correos = [c.strip() for c in correos_texto.replace(",", "\n").split("\n") if c.strip()]
                db.set_colorado_correos_aviso(nuevos_correos)
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
    st.info("Todavía no hay órdenes registradas para Colorado.")
else:
    pedidos_cronograma = sorted(pedidos, key=lambda p: p.get("fecha_entrega") or "9999-99-99")
    df_cron = pd.DataFrame([{
        "Producto": p.get("producto") or "—",
        "Cantidad": p.get("cantidad") if p.get("cantidad") not in (None, "") else "—",
        "Fecha de entrega": p.get("fecha_entrega") or "Sin definir",
        "Etapa": f"{COLUMN_EMOJI.get(p.get('estado'), '')} {p.get('estado') or '—'}",
        "Notas": p.get("notas") or "—",
        "_vencido": _es_vencido(p),
    } for p in pedidos_cronograma])
    styler = df_cron.drop(columns=["_vencido"]).style.apply(
        lambda _: [f"background-color: {VENCIDO_BG}" if v else "" for v in df_cron["_vencido"]], axis=0,
    )
    st.dataframe(styler, use_container_width=True, hide_index=True)

if puede_editar:
    with st.expander("➕ Agregar orden nueva"):
        with st.form("colorado_nuevo_pedido", clear_on_submit=True):
            producto_n = st.text_input("Producto / descripción de la orden")
            c1, c2 = st.columns(2)
            cantidad_n = c1.number_input("Cantidad (opcional)", min_value=0, step=1, value=0)
            fecha_entrega_n = c2.date_input("Fecha de entrega programada (opcional)", value=None)
            notas_n = st.text_area("Notas (opcional)")
            if st.form_submit_button(f"Agregar a {ESTADOS_COLORADO[0]}", use_container_width=True):
                if not producto_n.strip():
                    st.error("El producto / descripción de la orden es obligatorio.")
                else:
                    db.create_colorado_pedido(
                        producto_n.strip(), cantidad_n or None, fecha_entrega_n,
                        notas=notas_n.strip() or None, creado_por_id=user["id"],
                    )
                    _avisar_por_correo(
                        f"Colorado — Nueva orden: {producto_n.strip()}",
                        f"Se agregó una nueva orden de producción en Colorado.\n\n"
                        f"Producto: {producto_n.strip()}\n"
                        f"Cantidad: {cantidad_n or '—'}\n"
                        f"Fecha de entrega: {fecha_entrega_n or 'sin definir'}\n"
                        f"Notas: {notas_n.strip() or '—'}\n\n"
                        f"Etapa: {ESTADOS_COLORADO[0]}",
                    )
                    st.success(f"Orden agregada al cronograma y a la columna '{ESTADOS_COLORADO[0]}' del tablero.")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Tablero de producción (abajo) — mismo concepto que Phara.
# ---------------------------------------------------------------------------
st.markdown("#### 🗂️ Tablero de producción")
if not puede_editar:
    st.caption("Tu acceso es de solo consulta para este tablero.")

cols = st.columns(len(ESTADOS_COLORADO))
for col, estado in zip(cols, ESTADOS_COLORADO):
    items = [p for p in pedidos if p.get("estado") == estado]
    with col:
        st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
        if not items:
            st.caption("Sin órdenes.")
        for p in items:
            with st.container(border=True):
                pid = p["id"]
                editando_key = f"colorado_editando_{pid}"

                title_col2, edit_col = st.columns([5, 1])
                with title_col2:
                    vencido_marca = "🔴 " if _es_vencido(p) else ""
                    st.markdown(f"{vencido_marca}**{p.get('producto') or 'Sin producto'}**")
                with edit_col:
                    if puede_editar:
                        if st.button("✏️", key=f"colorado_editar_{pid}", help="Editar esta orden"):
                            st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                            st.rerun()
                if p.get("cantidad") not in (None, "", 0):
                    st.caption(f"Cantidad: {p['cantidad']}")
                st.caption(f"📅 Entrega: {p.get('fecha_entrega') or 'sin definir'}")
                if p.get("notas"):
                    st.caption(f"📝 {p['notas']}")
                st.caption(f"🕒 {(p.get('creado_en') or '')[:16].replace('T', ' ')}")

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
                                f"➡️ {siguiente}", key=f"colorado_avanzar_{pid}", use_container_width=True,
                                help=f"Pasar a la columna «{siguiente}»",
                            ):
                                db.update_colorado_pedido(pid, estado=siguiente)
                                _avisar_por_correo(
                                    f"Colorado — {p.get('producto') or 'Orden'} pasó a '{siguiente}'",
                                    f"La orden '{p.get('producto') or 'Orden'}' cambió de columna en el tablero.\n\n"
                                    f"De: {p.get('estado') or '—'}\nA: {siguiente}\n\n"
                                    f"Fecha de entrega: {p.get('fecha_entrega') or 'sin definir'}",
                                )
                                st.success(f"Orden movida a «{siguiente}».")
                                st.rerun()
                    with accion_col2:
                        if st.button(
                            "🗑️ Eliminar", key=f"colorado_borrar_{pid}", use_container_width=True,
                        ):
                            db.delete_colorado_pedido(pid)
                            st.session_state.pop(editando_key, None)
                            st.success("Orden eliminada.")
                            st.rerun()

                if puede_editar and st.session_state.get(editando_key):
                    with st.form(f"colorado_gestionar_{pid}"):
                        producto_ed = st.text_input("Producto / descripción", value=p.get("producto") or "")
                        c1, c2 = st.columns(2)
                        cantidad_ed = c1.number_input(
                            "Cantidad (opcional)", min_value=0, step=1, value=int(p.get("cantidad") or 0),
                        )
                        fecha_entrega_ed = c2.date_input(
                            "Fecha de entrega (opcional)",
                            value=date.fromisoformat(p["fecha_entrega"]) if p.get("fecha_entrega") else None,
                        )
                        notas_ed = st.text_area("Notas", value=p.get("notas") or "")
                        estado_ed = st.selectbox(
                            "Etapa (columna del tablero)", ESTADOS_COLORADO,
                            index=ESTADOS_COLORADO.index(p["estado"]) if p.get("estado") in ESTADOS_COLORADO else 0,
                            help="Además de «➡️» (que avanza a la siguiente), aquí puedes mandar la "
                                 "orden a cualquier columna, incluso hacia atrás si fue un error.",
                        )

                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
                        cancelar = colf2.form_submit_button("Cancelar", use_container_width=True)

                        if guardar:
                            if not producto_ed.strip():
                                st.error("El producto / descripción de la orden es obligatorio.")
                            else:
                                cambio_de_columna = estado_ed != p.get("estado")
                                db.update_colorado_pedido(
                                    pid, producto=producto_ed.strip(), cantidad=cantidad_ed or None,
                                    fecha_entrega=str(fecha_entrega_ed) if fecha_entrega_ed else None,
                                    notas=notas_ed.strip() or None,
                                    estado=estado_ed,
                                )
                                if cambio_de_columna:
                                    _avisar_por_correo(
                                        f"Colorado — {producto_ed.strip()} pasó a '{estado_ed}'",
                                        f"La orden '{producto_ed.strip()}' cambió de columna en el tablero.\n\n"
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
