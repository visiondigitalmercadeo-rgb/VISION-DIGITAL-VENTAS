from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import APP_URL, ESTADOS_PHARA, PHARA_ETAPA_FECHA_OBLIGATORIA, PHARA_LOGO_PATH
from utils import sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_phara()

logo_col, title_col = st.columns([1, 8])
with logo_col:
    st.image(PHARA_LOGO_PATH, width=70)
with title_col:
    st.markdown("<h1 style='margin-bottom:0;padding-top:0.3rem;'>Phara</h1>", unsafe_allow_html=True)

st.caption(
    "Pestaña exclusiva para el cliente Phara: arriba, el cronograma con la fecha de entrega de cada "
    "pedido; abajo, el tablero de producción (igual que el de Diseño Gráfico) para dar seguimiento a "
    "cada uno — cada pedido es la misma tarjeta en los dos lugares."
    + ("" if puede_editar else " Tu acceso es solo de consulta: puedes ver todo, pero no crear ni mover nada.")
)

COLUMN_EMOJI = {
    "Sherpa": "🎒", "Pre prensa": "🖋️", "Impresión": "🖨️", "Acabados": "✂️", "En logística": "🚚", "Entregado": "✅",
}
VENCIDO_BG = "#fbe3e3"  # rojo leve — mismo estilo que el resaltado magenta de 'Ventas por mes'

pedidos = db.list_phara_pedidos()
hoy = date.today()


def _es_vencido(p):
    # Un pedido ya entregado no cuenta como "vencido" aunque su fecha de
    # entrega programada haya quedado en el pasado.
    if p.get("estado") == "Entregado":
        return False
    fe = p.get("fecha_entrega")
    return bool(fe) and fe < str(hoy)


def _siguiente_estado(estado_actual):
    """Etapa que sigue en el orden del tablero, o None si ya está en la
    última columna ('Entregado')."""
    if estado_actual not in ESTADOS_PHARA:
        return None
    i = ESTADOS_PHARA.index(estado_actual)
    return ESTADOS_PHARA[i + 1] if i + 1 < len(ESTADOS_PHARA) else None


def _requiere_fecha(estado):
    """A partir de la etapa PHARA_ETAPA_FECHA_OBLIGATORIA (inclusive, y todas
    las que siguen) es obligatorio tener una fecha de entrega asignada. Solo
    la etapa inicial 'Sherpa' puede quedar sin fecha."""
    if estado not in ESTADOS_PHARA or PHARA_ETAPA_FECHA_OBLIGATORIA not in ESTADOS_PHARA:
        return False
    return ESTADOS_PHARA.index(estado) >= ESTADOS_PHARA.index(PHARA_ETAPA_FECHA_OBLIGATORIA)


def _avisar_por_correo(asunto, cuerpo):
    """Manda un aviso a los correos configurados (ver abajo). No hace nada
    (ni muestra error) si todavía no hay correos guardados o si el correo
    remitente no está configurado — ver database.correo_disponible."""
    correos = db.get_phara_correos_aviso()
    if correos:
        db.enviar_correo_aviso(correos, asunto, cuerpo + f"\n\nVer en la plataforma: {APP_URL}")


if puede_editar:
    with st.expander("✉️ Avisos por correo (nuevo pedido o cambio de columna)"):
        if not db.correo_disponible():
            st.info(
                "Todavía no está configurado el correo que manda los avisos (falta conectar una cuenta "
                "de Gmail en la configuración de la plataforma) — mientras tanto, esta sección no manda "
                "nada, pero puedes ir guardando los correos de una vez."
            )
        correos_actuales = db.get_phara_correos_aviso()
        with st.form("phara_correos_aviso"):
            correos_texto = st.text_area(
                "Correos que reciben el aviso — uno por línea (o separados por coma)",
                value="\n".join(correos_actuales),
                help="Se les avisa automáticamente cuando se agrega un pedido nuevo o cuando una tarjeta "
                     "cambia de columna en el tablero (no en otros cambios menores, como corregir una nota).",
            )
            if st.form_submit_button("💾 Guardar correos", use_container_width=True):
                nuevos_correos = [c.strip() for c in correos_texto.replace(",", "\n").split("\n") if c.strip()]
                db.set_phara_correos_aviso(nuevos_correos)
                st.success("Correos actualizados.")
                st.rerun()


# ---------------------------------------------------------------------------
# Cronograma de entregas (arriba)
# ---------------------------------------------------------------------------
st.markdown("#### 📅 Cronograma de entregas")

vencidos = [p for p in pedidos if _es_vencido(p)]
if vencidos:
    st.warning(f"⚠️ Hay {len(vencidos)} pedido(s) con la fecha de entrega ya vencida (resaltados abajo en rojo).")

if not pedidos:
    st.info("Todavía no hay pedidos registrados para Phara.")
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
    with st.expander("➕ Agregar pedido nuevo"):
        with st.form("phara_nuevo_pedido", clear_on_submit=True):
            producto_n = st.text_input("Producto / descripción del pedido")
            cantidad_n = st.number_input("Cantidad (opcional)", min_value=0, step=1, value=0)
            notas_n = st.text_area("Notas (opcional)")
            st.caption(
                "La fecha de entrega no se pide aquí — se pedirá más adelante, cuando el pedido pase "
                "de la columna «Sherpa» a «Pre prensa» en el tablero."
            )
            if st.form_submit_button("Agregar a Sherpa", use_container_width=True):
                if not producto_n.strip():
                    st.error("El producto / descripción del pedido es obligatorio.")
                else:
                    db.create_phara_pedido(
                        producto_n.strip(), cantidad_n or None, None,
                        notas=notas_n.strip() or None, creado_por_id=user["id"],
                    )
                    _avisar_por_correo(
                        f"Phara — Nuevo pedido: {producto_n.strip()}",
                        f"Se agregó un nuevo pedido a Phara.\n\n"
                        f"Producto: {producto_n.strip()}\n"
                        f"Cantidad: {cantidad_n or '—'}\n"
                        f"Notas: {notas_n.strip() or '—'}\n\n"
                        f"Etapa: Sherpa",
                    )
                    st.success("Pedido agregado al cronograma y a la columna 'Sherpa' del tablero.")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Tablero de producción (abajo) — mismo concepto que Diseño Gráfico.
# ---------------------------------------------------------------------------
st.markdown("#### 🗂️ Tablero de producción")
if not puede_editar:
    st.caption("Tu acceso es de solo consulta para este tablero.")

cols = st.columns(len(ESTADOS_PHARA))
for col, estado in zip(cols, ESTADOS_PHARA):
    items = [p for p in pedidos if p.get("estado") == estado]
    with col:
        st.markdown(f"##### {COLUMN_EMOJI.get(estado, '')} {estado} ({len(items)})")
        if not items:
            st.caption("Sin pedidos.")
        for p in items:
            with st.container(border=True):
                pid = p["id"]
                editando_key = f"phara_editando_{pid}"

                title_col2, edit_col = st.columns([5, 1])
                with title_col2:
                    vencido_marca = "🔴 " if _es_vencido(p) else ""
                    st.markdown(f"{vencido_marca}**{p.get('producto') or 'Sin producto'}**")
                with edit_col:
                    if puede_editar:
                        if st.button("✏️", key=f"phara_editar_{pid}", help="Editar este pedido"):
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
                # de edición) — mismo estilo que el botón "➡️ Mover a «...»"
                # de Mantenimiento de Tiendas.
                # ------------------------------------------------------------
                if puede_editar:
                    siguiente = _siguiente_estado(p.get("estado"))
                    falta_fecha = bool(siguiente) and _requiere_fecha(siguiente) and not p.get("fecha_entrega")
                    accion_col1, accion_col2 = st.columns(2)
                    with accion_col1:
                        if siguiente and not falta_fecha:
                            if st.button(
                                f"➡️ {siguiente}", key=f"phara_avanzar_{pid}", use_container_width=True,
                                help=f"Pasar a la columna «{siguiente}»",
                            ):
                                db.update_phara_pedido(pid, estado=siguiente)
                                _avisar_por_correo(
                                    f"Phara — {p.get('producto') or 'Pedido'} pasó a '{siguiente}'",
                                    f"El pedido '{p.get('producto') or 'Pedido'}' cambió de columna en el tablero.\n\n"
                                    f"De: {p.get('estado') or '—'}\nA: {siguiente}\n\n"
                                    f"Fecha de entrega: {p.get('fecha_entrega') or 'sin definir'}",
                                )
                                st.success(f"Pedido movido a «{siguiente}».")
                                st.rerun()
                    with accion_col2:
                        if st.button(
                            "🗑️ Eliminar", key=f"phara_borrar_{pid}", use_container_width=True,
                        ):
                            db.delete_phara_pedido(pid)
                            st.session_state.pop(editando_key, None)
                            st.success("Pedido eliminado.")
                            st.rerun()

                    if falta_fecha:
                        with st.form(f"phara_fecha_obligatoria_{pid}"):
                            st.caption(f"Para pasar a «{siguiente}» hay que indicar la fecha de entrega.")
                            fecha_avance = st.date_input(
                                "Fecha de entrega", value=None, key=f"phara_fecha_avance_{pid}",
                            )
                            if st.form_submit_button(f"➡️ Pasar a «{siguiente}»", use_container_width=True):
                                if not fecha_avance:
                                    st.error("Hay que indicar la fecha de entrega antes de pasar a esta etapa.")
                                else:
                                    db.update_phara_pedido(pid, estado=siguiente, fecha_entrega=str(fecha_avance))
                                    _avisar_por_correo(
                                        f"Phara — {p.get('producto') or 'Pedido'} pasó a '{siguiente}'",
                                        f"El pedido '{p.get('producto') or 'Pedido'}' cambió de columna en el tablero.\n\n"
                                        f"De: {p.get('estado') or '—'}\nA: {siguiente}\n\n"
                                        f"Fecha de entrega: {fecha_avance}",
                                    )
                                    st.success(f"Pedido movido a «{siguiente}».")
                                    st.rerun()

                if puede_editar and st.session_state.get(editando_key):
                    with st.form(f"phara_gestionar_{pid}"):
                        producto_ed = st.text_input("Producto / descripción", value=p.get("producto") or "")
                        c1, c2 = st.columns(2)
                        cantidad_ed = c1.number_input(
                            "Cantidad (opcional)", min_value=0, step=1, value=int(p.get("cantidad") or 0),
                        )
                        fecha_entrega_ed = c2.date_input(
                            "Fecha de entrega" + ("" if p.get("fecha_entrega") else " (obligatoria salvo en 'Sherpa')"),
                            value=date.fromisoformat(p["fecha_entrega"]) if p.get("fecha_entrega") else None,
                        )
                        notas_ed = st.text_area("Notas", value=p.get("notas") or "")
                        estado_ed = st.selectbox(
                            "Etapa (columna del tablero)", ESTADOS_PHARA,
                            index=ESTADOS_PHARA.index(p["estado"]) if p.get("estado") in ESTADOS_PHARA else 0,
                            help="Además de «➡️» (que avanza a la siguiente), aquí puedes mandar el "
                                 "pedido a cualquier columna, incluso hacia atrás si fue un error.",
                        )

                        colf1, colf2 = st.columns(2)
                        guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
                        cancelar = colf2.form_submit_button("Cancelar", use_container_width=True)

                        if guardar:
                            if not producto_ed.strip():
                                st.error("El producto / descripción del pedido es obligatorio.")
                            elif _requiere_fecha(estado_ed) and not fecha_entrega_ed:
                                st.error(
                                    f"La fecha de entrega es obligatoria para la etapa «{estado_ed}» "
                                    f"(solo puede quedar sin fecha mientras está en «Sherpa»)."
                                )
                            else:
                                cambio_de_columna = estado_ed != p.get("estado")
                                db.update_phara_pedido(
                                    pid, producto=producto_ed.strip(), cantidad=cantidad_ed or None,
                                    fecha_entrega=str(fecha_entrega_ed) if fecha_entrega_ed else None,
                                    notas=notas_ed.strip() or None,
                                    estado=estado_ed,
                                )
                                if cambio_de_columna:
                                    _avisar_por_correo(
                                        f"Phara — {producto_ed.strip()} pasó a '{estado_ed}'",
                                        f"El pedido '{producto_ed.strip()}' cambió de columna en el tablero.\n\n"
                                        f"De: {p.get('estado') or '—'}\n"
                                        f"A: {estado_ed}\n\n"
                                        f"Fecha de entrega: {fecha_entrega_ed or 'sin definir'}",
                                    )
                                st.session_state.pop(editando_key, None)
                                st.success("Pedido actualizado.")
                                st.rerun()
                        if cancelar:
                            st.session_state.pop(editando_key, None)
                            st.rerun()
