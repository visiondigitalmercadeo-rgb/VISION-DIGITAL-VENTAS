import base64
from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import MANTENIMIENTO_ARCHIVO_MAX_BYTES, PLANTAS_MAQUINARIA
from utils import archivo_a_b64, download_excel_button, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🔧 Mantenimiento de Maquinaria")
st.caption(
    "Registro de máquinas por planta (impresoras, troqueladoras, etc.) con su mantenimiento "
    "preventivo, correctivo e historial — facturas, repuestos cambiados y garantías incluidos."
)

puede_gestionar = auth.puede_gestionar_mantenimiento()

if "mant_maquina_sel" not in st.session_state:
    st.session_state["mant_maquina_sel"] = None


def _mostrar_adjunto(etiqueta, prefijo_key, nombre, tipo, b64):
    st.caption(etiqueta)
    if not b64:
        st.caption("Sin archivo adjunto.")
        return
    datos = base64.b64decode(b64)
    mostrado_como_imagen = False
    if tipo and tipo.startswith("image/"):
        try:
            st.image(datos, use_container_width=True)
            mostrado_como_imagen = True
        except Exception:
            # Si el archivo quedó dañado o no se puede decodificar como imagen,
            # no tumbamos la página: lo dejamos disponible para descargar.
            mostrado_como_imagen = False
    if not mostrado_como_imagen:
        st.download_button(
            f"📎 {nombre or 'archivo'}", data=datos, file_name=nombre or "archivo",
            mime=tipo or "application/octet-stream", use_container_width=True, key=prefijo_key,
        )


def _render_form_nuevo_mantenimiento(maquina_id, tipo):
    es_preventivo = tipo == "Preventivo"
    with st.form(f"nuevo_mant_{tipo}_{maquina_id}", clear_on_submit=True):
        fecha_m = st.date_input(
            "Fecha programada" if es_preventivo else "Fecha de reparación", value=date.today(),
        )
        c1, c2 = st.columns(2)
        proveedor_m = c1.text_input("Proveedor")
        costo_m = c2.number_input("Costo (Q)", min_value=0.0, step=0.01, format="%.2f")
        repuesto_m = st.text_input("¿Qué repuesto se cambió? (opcional)")
        garantia_m = st.text_input("Tiempo de garantía (ej. '6 meses', '1 año')")
        numero_factura_m = st.text_input(
            "Número de factura" + ("" if not es_preventivo else " (opcional)"),
        )
        factura_m = st.file_uploader(
            "Foto de la factura (PDF o JPEG)", type=["pdf", "jpg", "jpeg", "png"],
            key=f"mant_factura_{tipo}_{maquina_id}",
        )
        foto_repuesto_m = st.file_uploader(
            "Foto del repuesto viejo", type=["jpg", "jpeg", "png"],
            key=f"mant_foto_rep_{tipo}_{maquina_id}",
        )
        notas_m = st.text_area("Notas (opcional)")
        if st.form_submit_button(f"Guardar mantenimiento {tipo.lower()}", use_container_width=True):
            if not proveedor_m.strip():
                st.error("El proveedor es obligatorio.")
            elif not es_preventivo and not numero_factura_m.strip():
                st.error("El número de factura es obligatorio para mantenimiento correctivo.")
            else:
                try:
                    factura_nombre, factura_tipo, factura_b64 = archivo_a_b64(
                        factura_m, MANTENIMIENTO_ARCHIVO_MAX_BYTES,
                    )
                    foto_nombre, foto_tipo, foto_b64 = archivo_a_b64(
                        foto_repuesto_m, MANTENIMIENTO_ARCHIVO_MAX_BYTES,
                    )
                except ValueError as e:
                    st.error(str(e))
                else:
                    db.create_mantenimiento(
                        maquina_id, tipo,
                        fecha=str(fecha_m), proveedor=proveedor_m.strip(), costo=costo_m,
                        repuesto_cambiado=repuesto_m.strip() or None,
                        tiempo_garantia=garantia_m.strip() or None,
                        numero_factura=numero_factura_m.strip() or None,
                        factura_nombre=factura_nombre, factura_tipo=factura_tipo, factura_b64=factura_b64,
                        foto_repuesto_nombre=foto_nombre, foto_repuesto_tipo=foto_tipo,
                        foto_repuesto_b64=foto_b64, notas=notas_m.strip() or None,
                    )
                    st.success(f"Mantenimiento {tipo.lower()} registrado.")
                    st.rerun()


def _render_editar_mantenimiento(r, es_preventivo, editando_key):
    with st.form(f"editar_mant_{r['id']}"):
        fecha_ed = st.date_input(
            "Fecha programada" if es_preventivo else "Fecha de reparación",
            value=date.fromisoformat(r["fecha"]) if r.get("fecha") else date.today(),
        )
        c1, c2 = st.columns(2)
        proveedor_ed = c1.text_input("Proveedor", value=r.get("proveedor") or "")
        costo_ed = c2.number_input(
            "Costo (Q)", min_value=0.0, step=0.01, format="%.2f", value=float(r.get("costo") or 0),
        )
        repuesto_ed = st.text_input("¿Qué repuesto se cambió?", value=r.get("repuesto_cambiado") or "")
        garantia_ed = st.text_input("Tiempo de garantía", value=r.get("tiempo_garantia") or "")
        numero_factura_ed = st.text_input(
            "Número de factura" + ("" if not es_preventivo else " (opcional)"),
            value=r.get("numero_factura") or "",
        )
        st.caption(
            f"Factura actual: {r.get('factura_nombre') or 'ninguna'} · "
            f"Foto de repuesto actual: {r.get('foto_repuesto_nombre') or 'ninguna'}"
        )
        nueva_factura = st.file_uploader(
            "Reemplazar foto de factura (PDF o JPEG) — déjalo vacío para no cambiarla",
            type=["pdf", "jpg", "jpeg", "png"], key=f"mant_ed_factura_{r['id']}",
        )
        nueva_foto_rep = st.file_uploader(
            "Reemplazar foto del repuesto viejo — déjalo vacío para no cambiarla",
            type=["jpg", "jpeg", "png"], key=f"mant_ed_foto_rep_{r['id']}",
        )
        notas_ed = st.text_area("Notas", value=r.get("notas") or "")
        colf1, colf2 = st.columns(2)
        guardar = colf1.form_submit_button("💾 Guardar cambios", use_container_width=True)
        eliminar = colf2.form_submit_button("Eliminar registro", use_container_width=True)
        if guardar:
            if not proveedor_ed.strip():
                st.error("El proveedor es obligatorio.")
            elif not es_preventivo and not numero_factura_ed.strip():
                st.error("El número de factura es obligatorio para mantenimiento correctivo.")
            else:
                try:
                    update_kwargs = {
                        "fecha": str(fecha_ed), "proveedor": proveedor_ed.strip(), "costo": costo_ed,
                        "repuesto_cambiado": repuesto_ed.strip() or None,
                        "tiempo_garantia": garantia_ed.strip() or None,
                        "numero_factura": numero_factura_ed.strip() or None,
                        "notas": notas_ed.strip() or None,
                    }
                    if nueva_factura is not None:
                        n, t, b = archivo_a_b64(nueva_factura, MANTENIMIENTO_ARCHIVO_MAX_BYTES)
                        update_kwargs.update(factura_nombre=n, factura_tipo=t, factura_b64=b)
                    if nueva_foto_rep is not None:
                        n2, t2, b2 = archivo_a_b64(nueva_foto_rep, MANTENIMIENTO_ARCHIVO_MAX_BYTES)
                        update_kwargs.update(foto_repuesto_nombre=n2, foto_repuesto_tipo=t2, foto_repuesto_b64=b2)
                except ValueError as e:
                    st.error(str(e))
                else:
                    db.update_mantenimiento(r["id"], **update_kwargs)
                    st.session_state.pop(editando_key, None)
                    st.success("Mantenimiento actualizado.")
                    st.rerun()
        if eliminar:
            db.delete_mantenimiento(r["id"])
            st.session_state.pop(editando_key, None)
            st.success("Registro eliminado.")
            st.rerun()


def _render_seccion_mantenimiento(maquina_id, tipo):
    es_preventivo = tipo == "Preventivo"
    registros = db.list_mantenimientos_maquina(maquina_id, tipo=tipo)

    if puede_gestionar:
        with st.expander(f"➕ Registrar mantenimiento {tipo.lower()}"):
            _render_form_nuevo_mantenimiento(maquina_id, tipo)

    st.divider()

    if not registros:
        st.caption(f"Todavía no hay mantenimientos {tipo.lower()}s registrados para esta máquina.")
        return

    hoy_str = str(date.today())
    for r in registros:
        with st.container(border=True):
            estado_txt = ""
            if es_preventivo and r.get("fecha"):
                estado_txt = " · 🗓️ Programado" if r["fecha"] >= hoy_str else " · ✅ Realizado"
            st.markdown(f"**📅 {r.get('fecha') or '—'}**{estado_txt}")
            st.caption(f"Proveedor: {r.get('proveedor') or '—'} · Costo: Q{r.get('costo') or 0:,.2f}")
            if r.get("repuesto_cambiado"):
                st.caption(f"🔩 Repuesto cambiado: {r['repuesto_cambiado']}")
            if r.get("tiempo_garantia"):
                st.caption(f"🛡️ Garantía: {r['tiempo_garantia']}")
            if r.get("numero_factura"):
                st.caption(f"🧾 N° factura: {r['numero_factura']}")
            if r.get("notas"):
                st.caption(f"📝 {r['notas']}")

            fc1, fc2 = st.columns(2)
            with fc1:
                _mostrar_adjunto(
                    "Factura", f"mant_dl_factura_{r['id']}",
                    r.get("factura_nombre"), r.get("factura_tipo"), r.get("factura_b64"),
                )
            with fc2:
                _mostrar_adjunto(
                    "Repuesto viejo", f"mant_dl_repuesto_{r['id']}",
                    r.get("foto_repuesto_nombre"), r.get("foto_repuesto_tipo"), r.get("foto_repuesto_b64"),
                )

            if puede_gestionar:
                editando_key = f"mant_editando_{r['id']}"
                if st.button("✏️ Editar / eliminar", key=f"mant_toggle_{r['id']}", use_container_width=True):
                    st.session_state[editando_key] = not st.session_state.get(editando_key, False)
                    st.rerun()
                if st.session_state.get(editando_key):
                    _render_editar_mantenimiento(r, es_preventivo, editando_key)


def _render_historial(maquina_id):
    registros = db.list_mantenimientos_maquina(maquina_id)
    if not registros:
        st.info("Todavía no hay mantenimientos registrados para esta máquina.")
        return
    df = pd.DataFrame([{
        "Tipo": r["tipo"], "Fecha": r.get("fecha") or "—", "Proveedor": r.get("proveedor") or "—",
        "Costo (Q)": r.get("costo") or 0, "Repuesto cambiado": r.get("repuesto_cambiado") or "—",
        "Garantía": r.get("tiempo_garantia") or "—", "N° factura": r.get("numero_factura") or "—",
        "Notas": r.get("notas") or "—",
    } for r in registros])
    st.dataframe(df, use_container_width=True, hide_index=True)
    download_excel_button(
        df, "historial_mantenimiento.xlsx", key=f"mant_descargar_historial_{maquina_id}",
    )


maquina_sel_id = st.session_state.get("mant_maquina_sel")

if maquina_sel_id:
    maquina = db.get_maquina(maquina_sel_id)
    if not maquina:
        st.session_state["mant_maquina_sel"] = None
        st.rerun()

    if st.button("⬅️ Volver a la lista de máquinas", key="mant_volver"):
        st.session_state["mant_maquina_sel"] = None
        st.rerun()

    st.header(f"🖨️ {maquina['nombre']}")
    detalle = f"Planta {maquina['planta']}"
    if maquina.get("tipo_maquina"):
        detalle = f"{maquina['tipo_maquina']} · {detalle}"
    if maquina.get("numero_serie"):
        detalle += f" · Serie: {maquina['numero_serie']}"
    st.caption(detalle)

    preventivos = db.list_mantenimientos_maquina(maquina_sel_id, tipo="Preventivo")
    hoy_str = str(date.today())
    proximos = sorted(
        [p for p in preventivos if p.get("fecha") and p["fecha"] >= hoy_str], key=lambda p: p["fecha"],
    )
    if proximos:
        st.info(
            f"🗓️ Próximo mantenimiento preventivo: **{proximos[0]['fecha']}** — "
            f"{proximos[0].get('proveedor') or 'proveedor sin definir'}"
        )

    tab_prev, tab_corr, tab_hist = st.tabs(
        ["🛠️ Mantenimiento preventivo", "🔧 Mantenimiento correctivo", "📋 Historial"]
    )
    with tab_prev:
        _render_seccion_mantenimiento(maquina_sel_id, "Preventivo")
    with tab_corr:
        _render_seccion_mantenimiento(maquina_sel_id, "Correctivo")
    with tab_hist:
        _render_historial(maquina_sel_id)

    if puede_gestionar:
        st.divider()
        with st.expander("⚙️ Editar / eliminar esta máquina"):
            with st.form(f"editar_maquina_{maquina_sel_id}"):
                nombre_maq_ed = st.text_input("Nombre", value=maquina["nombre"])
                tipo_maq_ed = st.text_input(
                    "Tipo de máquina (ej. Impresora, Troqueladora)", value=maquina.get("tipo_maquina") or "",
                )
                serie_maq_ed = st.text_input("Número de serie", value=maquina.get("numero_serie") or "")
                planta_maq_ed = st.selectbox(
                    "Planta", PLANTAS_MAQUINARIA,
                    index=PLANTAS_MAQUINARIA.index(maquina["planta"]) if maquina["planta"] in PLANTAS_MAQUINARIA else 0,
                )
                if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
                    if not nombre_maq_ed.strip():
                        st.error("El nombre es obligatorio.")
                    else:
                        db.update_maquina(
                            maquina_sel_id, nombre=nombre_maq_ed.strip(),
                            tipo_maquina=tipo_maq_ed.strip() or None,
                            numero_serie=serie_maq_ed.strip() or None, planta=planta_maq_ed,
                        )
                        st.success("Máquina actualizada.")
                        st.rerun()

            st.caption(
                "⚠️ Eliminar la máquina también elimina todo su historial de mantenimientos "
                "(preventivos y correctivos) — no se puede deshacer."
            )
            confirmar_borrar_maq = st.checkbox(
                "Confirmo que deseo eliminar esta máquina por completo", key=f"mant_confirmar_del_{maquina_sel_id}",
            )
            if st.button(
                "🗑️ Eliminar máquina", key=f"mant_del_{maquina_sel_id}", disabled=not confirmar_borrar_maq,
            ):
                db.delete_maquina(maquina_sel_id)
                st.session_state["mant_maquina_sel"] = None
                st.success("Máquina eliminada.")
                st.rerun()

else:
    tabs_plantas = st.tabs([f"🏭 Planta {p}" for p in PLANTAS_MAQUINARIA])
    for tab, planta in zip(tabs_plantas, PLANTAS_MAQUINARIA):
        with tab:
            maquinas_planta = db.list_maquinas(planta=planta)
            if not maquinas_planta:
                st.caption("No hay máquinas registradas en esta planta todavía.")
            else:
                cols = st.columns(3)
                for i, maq in enumerate(maquinas_planta):
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.markdown(f"**🖨️ {maq['nombre']}**")
                            st.caption(maq.get("tipo_maquina") or "Tipo no especificado")
                            if maq.get("numero_serie"):
                                st.caption(f"Serie: {maq['numero_serie']}")
                            n_prev = len(db.list_mantenimientos_maquina(maq["id"], tipo="Preventivo"))
                            n_corr = len(db.list_mantenimientos_maquina(maq["id"], tipo="Correctivo"))
                            st.caption(f"🛠️ {n_prev} preventivo(s) · 🔧 {n_corr} correctivo(s)")
                            if st.button("Abrir", key=f"mant_abrir_{maq['id']}", use_container_width=True):
                                st.session_state["mant_maquina_sel"] = maq["id"]
                                st.rerun()

            if puede_gestionar:
                st.divider()
                with st.expander(f"➕ Registrar máquina en Planta {planta}"):
                    with st.form(f"nueva_maquina_{planta}", clear_on_submit=True):
                        nombre_maq = st.text_input("Nombre de la máquina")
                        tipo_maq = st.text_input(
                            "¿Qué máquina es? (ej. Impresora, Troqueladora, Guillotina, Plotter...)",
                        )
                        serie_maq = st.text_input("Número de serie (si aplica)")
                        if st.form_submit_button("Registrar máquina", use_container_width=True):
                            if not nombre_maq.strip():
                                st.error("El nombre de la máquina es obligatorio.")
                            else:
                                db.create_maquina(
                                    nombre_maq.strip(), tipo_maq.strip() or None, planta,
                                    serie_maq.strip() or None,
                                )
                                st.success(f"Máquina '{nombre_maq}' registrada en Planta {planta}.")
                                st.rerun()
