from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_PHARA
from utils import sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_editar = auth.puede_editar_phara()

st.title("📦 Phara")
st.caption(
    "Pestaña exclusiva para el cliente Phara: arriba, el cronograma con la fecha de entrega de cada "
    "pedido; abajo, el tablero de producción (igual que el de Diseño Gráfico) para dar seguimiento a "
    "cada uno — cada pedido es la misma tarjeta en los dos lugares."
    + ("" if puede_editar else " Tu acceso es solo de consulta: puedes ver todo, pero no crear ni mover nada.")
)

COLUMN_EMOJI = {"Pre prensa": "🖋️", "Impresión": "🖨️", "Acabados": "✂️", "En logística": "🚚"}
VENCIDO_BG = "#fbe3e3"  # rojo leve — mismo estilo que el resaltado magenta de 'Ventas por mes'

pedidos = db.list_phara_pedidos()
hoy = date.today()


def _es_vencido(p):
    fe = p.get("fecha_entrega")
    return bool(fe) and fe < str(hoy)


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
            c1, c2 = st.columns(2)
            cantidad_n = c1.number_input("Cantidad (opcional)", min_value=0, step=1, value=0)
            fecha_entrega_n = c2.date_input("Fecha de entrega programada", value=hoy)
            notas_n = st.text_area("Notas (opcional)")
            if st.form_submit_button("Agregar a Pre prensa", use_container_width=True):
                if not producto_n.strip():
                    st.error("El producto / descripción del pedido es obligatorio.")
                else:
                    db.create_phara_pedido(
                        producto_n.strip(), cantidad_n or None, fecha_entrega_n,
                        notas=notas_n.strip() or None, creado_por_id=user["id"],
                    )
                    st.success("Pedido agregado al cronograma y a la columna 'Pre prensa' del tablero.")
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

                title_col, edit_col = st.columns([5, 1])
                with title_col:
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

                if puede_editar and st.session_state.get(editando_key):
                    with st.form(f"phara_gestionar_{pid}"):
                        producto_ed = st.text_input("Producto / descripción", value=p.get("producto") or "")
                        c1, c2 = st.columns(2)
                        cantidad_ed = c1.number_input(
                            "Cantidad (opcional)", min_value=0, step=1, value=int(p.get("cantidad") or 0),
                        )
                        fecha_entrega_ed = c2.date_input(
                            "Fecha de entrega",
                            value=date.fromisoformat(p["fecha_entrega"]) if p.get("fecha_entrega") else hoy,
                        )
                        notas_ed = st.text_area("Notas", value=p.get("notas") or "")
                        estado_ed = st.selectbox(
                            "Etapa (columna del tablero)", ESTADOS_PHARA,
                            index=ESTADOS_PHARA.index(p["estado"]) if p.get("estado") in ESTADOS_PHARA else 0,
                        )

                        colf1, colf2, colf3 = st.columns(3)
                        guardar = colf1.form_submit_button("💾 Guardar", use_container_width=True)
                        eliminar = colf2.form_submit_button("Eliminar", use_container_width=True)
                        cancelar = colf3.form_submit_button("Cancelar", use_container_width=True)

                        if guardar:
                            if not producto_ed.strip():
                                st.error("El producto / descripción del pedido es obligatorio.")
                            else:
                                db.update_phara_pedido(
                                    pid, producto=producto_ed.strip(), cantidad=cantidad_ed or None,
                                    fecha_entrega=str(fecha_entrega_ed), notas=notas_ed.strip() or None,
                                    estado=estado_ed,
                                )
                                st.session_state.pop(editando_key, None)
                                st.success("Pedido actualizado.")
                                st.rerun()
                        if eliminar:
                            db.delete_phara_pedido(pid)
                            st.session_state.pop(editando_key, None)
                            st.success("Pedido eliminado.")
                            st.rerun()
                        if cancelar:
                            st.session_state.pop(editando_key, None)
                            st.rerun()
