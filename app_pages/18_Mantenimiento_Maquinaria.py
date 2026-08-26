import base64
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import auth
import database as db
from config import CATEGORICAL, MANTENIMIENTO_ARCHIVO_MAX_BYTES, MOTIVOS_CAMBIO_PIEZA, PLANTAS_MAQUINARIA
from utils import archivo_a_b64, base_layout, download_excel_button, sidebar_user_box

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
            st.image(datos, width="stretch")
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


def _preventivo_realizado(r, hoy_str):
    """True/False si el registro (de tipo Preventivo) ya se realizó.

    Los registros nuevos guardan el campo explícito 'realizado' (True/False).
    Los registros viejos, creados antes de que existiera esta casilla, no
    tienen ese campo — para esos usamos como respaldo la lógica anterior
    (naive): si la fecha programada ya pasó, se asume realizado; si no, se
    asume programado/pendiente. Así no se reclasifica de golpe el historial
    viejo al lanzar esta función."""
    val = r.get("realizado")
    if val is not None:
        return bool(val)
    return bool(r.get("fecha")) and r["fecha"] < hoy_str


def _preventivo_vencido(r, hoy_str):
    """True si es un preventivo programado (con fecha) que ya pasó de fecha y
    todavía no se ha marcado como realizado."""
    return bool(r.get("fecha")) and r["fecha"] < hoy_str and not _preventivo_realizado(r, hoy_str)


def _ultimos_meses(n):
    """Lista de los últimos n meses como 'YYYY-MM', del más antiguo al más
    reciente (incluye el mes actual). Se usa para la gráfica de mantenimientos
    realizados por mes — comparación de strings 'YYYY-MM' alcanza porque el
    formato ISO ordena igual que el orden cronológico."""
    hoy = date.today()
    meses = []
    y, m = hoy.year, hoy.month
    for _ in range(n):
        meses.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(meses))


_MESES_LABEL = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
    "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic",
}


def _label_mes(mes_iso):
    y, m = mes_iso.split("-")
    return f"{_MESES_LABEL.get(m, m)} {y}"


def _construir_kpi_mensual(mantenimientos, hoy_str, n_meses=6):
    """DataFrame en formato largo (Mes, Tipo, Cantidad) con los mantenimientos
    realizados por mes en los últimos n_meses — un preventivo cuenta en el mes
    de su fecha solo si ya se marcó como realizado; un correctivo siempre
    cuenta (se registra cuando ya ocurrió la reparación)."""
    meses = _ultimos_meses(n_meses)
    filas = []
    for mes in meses:
        n_prev = sum(
            1 for r in mantenimientos
            if r.get("tipo") == "Preventivo" and (r.get("fecha") or "").startswith(mes)
            and _preventivo_realizado(r, hoy_str)
        )
        n_corr = sum(
            1 for r in mantenimientos
            if r.get("tipo") == "Correctivo" and (r.get("fecha") or "").startswith(mes)
        )
        filas.append({"Mes": _label_mes(mes), "_orden": mes, "Tipo": "Preventivo", "Cantidad": n_prev})
        filas.append({"Mes": _label_mes(mes), "_orden": mes, "Tipo": "Correctivo", "Cantidad": n_corr})
    return pd.DataFrame(filas)


def _label_motivos(motivos, detalle_otro):
    """Texto legible de los motivos de cambio de pieza seleccionados — si
    incluye 'Otro', muestra el detalle específico en vez de la palabra sola."""
    if not motivos:
        return None
    partes = []
    for m in motivos:
        if m == "Otro" and detalle_otro:
            partes.append(f"Otro: {detalle_otro}")
        else:
            partes.append(m)
    return ", ".join(partes)


def _render_form_nuevo_mantenimiento(maquina_id, tipo):
    es_preventivo = tipo == "Preventivo"
    with st.form(f"nuevo_mant_{tipo}_{maquina_id}", clear_on_submit=True):
        fecha_m = st.date_input(
            "Fecha programada" if es_preventivo else "Fecha de reparación", value=date.today(),
        )
        c1, c2 = st.columns(2)
        proveedor_m = c1.text_input("Proveedor")
        tecnico_m = c2.text_input("Técnico responsable")

        st.markdown("###### 🧾 Factura")
        f1, f2 = st.columns(2)
        serie_factura_m = f1.text_input("Serie de la factura")
        numero_factura_m = f2.text_input(
            "Número de factura" + ("" if not es_preventivo else " (opcional)"),
        )

        st.markdown("###### 🔩 Repuesto")
        r1, r2 = st.columns(2)
        repuesto_m = r1.text_input("¿Qué repuesto se cambió? (opcional)")
        codigo_repuesto_m = r2.text_input("Código de repuesto (opcional)")
        r3, r4 = st.columns(2)
        cantidad_repuestos_m = r3.number_input("Cantidad de repuestos", min_value=0, value=0, step=1)
        garantia_m = r4.text_input("Tiempo de garantía (ej. '6 meses', '1 año')")
        motivo_m = st.multiselect(
            "Motivo de cambio de pieza", MOTIVOS_CAMBIO_PIEZA,
            key=f"mant_motivo_{tipo}_{maquina_id}",
        )
        motivo_otro_m = st.text_input(
            "Si el motivo es 'Otro', especifica cuál",
            key=f"mant_motivo_otro_{tipo}_{maquina_id}",
        )

        st.markdown("###### 💵 Costo")
        co1, co2 = st.columns(2)
        costo_repuestos_m = co1.number_input(
            "Costo de repuestos (Q)", min_value=0.0, step=0.01, format="%.2f",
            key=f"mant_costo_rep_{tipo}_{maquina_id}",
        )
        costo_mano_obra_m = co2.number_input(
            "Costo de mano de obra (Q)", min_value=0.0, step=0.01, format="%.2f",
            key=f"mant_costo_mo_{tipo}_{maquina_id}",
        )
        st.caption(f"**Total del gasto: Q{costo_repuestos_m + costo_mano_obra_m:,.2f}**")

        factura_m = st.file_uploader(
            "Foto de la factura (PDF o JPEG)", type=["pdf", "jpg", "jpeg", "png"],
            key=f"mant_factura_{tipo}_{maquina_id}",
        )
        foto_repuesto_m = st.file_uploader(
            "Foto del repuesto viejo", type=["jpg", "jpeg", "png"],
            key=f"mant_foto_rep_{tipo}_{maquina_id}",
        )
        notas_m = st.text_area("Notas (opcional)")
        realizado_m = True
        if es_preventivo:
            realizado_m = st.checkbox(
                "✅ Ya se realizó este mantenimiento",
                value=fecha_m <= date.today(),
                help="Desmárcalo si estás programando un mantenimiento preventivo que todavía no se ha hecho.",
                key=f"mant_realizado_{tipo}_{maquina_id}",
            )
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
                        fecha=str(fecha_m), proveedor=proveedor_m.strip(), tecnico_responsable=tecnico_m.strip() or None,
                        costo=costo_repuestos_m + costo_mano_obra_m,
                        costo_repuestos=costo_repuestos_m, costo_mano_obra=costo_mano_obra_m,
                        repuesto_cambiado=repuesto_m.strip() or None,
                        codigo_repuesto=codigo_repuesto_m.strip() or None,
                        cantidad_repuestos=int(cantidad_repuestos_m) or None,
                        motivo_cambio_pieza=motivo_m or [], motivo_otro_detalle=motivo_otro_m.strip() or None,
                        tiempo_garantia=garantia_m.strip() or None,
                        serie_factura=serie_factura_m.strip() or None,
                        numero_factura=numero_factura_m.strip() or None,
                        factura_nombre=factura_nombre, factura_tipo=factura_tipo, factura_b64=factura_b64,
                        foto_repuesto_nombre=foto_nombre, foto_repuesto_tipo=foto_tipo,
                        foto_repuesto_b64=foto_b64, notas=notas_m.strip() or None,
                        realizado=bool(realizado_m) if es_preventivo else True,
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
        tecnico_ed = c2.text_input("Técnico responsable", value=r.get("tecnico_responsable") or "")

        st.markdown("###### 🧾 Factura")
        f1, f2 = st.columns(2)
        serie_factura_ed = f1.text_input("Serie de la factura", value=r.get("serie_factura") or "")
        numero_factura_ed = f2.text_input(
            "Número de factura" + ("" if not es_preventivo else " (opcional)"),
            value=r.get("numero_factura") or "",
        )

        st.markdown("###### 🔩 Repuesto")
        r1, r2 = st.columns(2)
        repuesto_ed = r1.text_input("¿Qué repuesto se cambió?", value=r.get("repuesto_cambiado") or "")
        codigo_repuesto_ed = r2.text_input("Código de repuesto", value=r.get("codigo_repuesto") or "")
        r3, r4 = st.columns(2)
        cantidad_repuestos_ed = r3.number_input(
            "Cantidad de repuestos", min_value=0, step=1, value=int(r.get("cantidad_repuestos") or 0),
        )
        garantia_ed = r4.text_input("Tiempo de garantía", value=r.get("tiempo_garantia") or "")
        motivo_ed = st.multiselect(
            "Motivo de cambio de pieza", MOTIVOS_CAMBIO_PIEZA,
            default=[m for m in (r.get("motivo_cambio_pieza") or []) if m in MOTIVOS_CAMBIO_PIEZA],
            key=f"mant_ed_motivo_{r['id']}",
        )
        motivo_otro_ed = st.text_input(
            "Si el motivo es 'Otro', especifica cuál", value=r.get("motivo_otro_detalle") or "",
            key=f"mant_ed_motivo_otro_{r['id']}",
        )

        st.markdown("###### 💵 Costo")
        # Registros creados antes de este desglose solo tienen "costo" (total)
        # — por defecto se muestra completo en "repuestos" para no perder el
        # dato; se puede repartir manualmente al editar.
        costo_rep_default = float(r["costo_repuestos"]) if r.get("costo_repuestos") is not None else float(r.get("costo") or 0)
        costo_mo_default = float(r.get("costo_mano_obra") or 0)
        co1, co2 = st.columns(2)
        costo_repuestos_ed = co1.number_input(
            "Costo de repuestos (Q)", min_value=0.0, step=0.01, format="%.2f", value=costo_rep_default,
        )
        costo_mano_obra_ed = co2.number_input(
            "Costo de mano de obra (Q)", min_value=0.0, step=0.01, format="%.2f", value=costo_mo_default,
        )
        st.caption(f"**Total del gasto: Q{costo_repuestos_ed + costo_mano_obra_ed:,.2f}**")
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
        realizado_ed = True
        if es_preventivo:
            realizado_ed = st.checkbox(
                "✅ Ya se realizó este mantenimiento",
                value=_preventivo_realizado(r, str(date.today())),
                key=f"mant_ed_realizado_{r['id']}",
            )
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
                        "fecha": str(fecha_ed), "proveedor": proveedor_ed.strip(),
                        "tecnico_responsable": tecnico_ed.strip() or None,
                        "costo": costo_repuestos_ed + costo_mano_obra_ed,
                        "costo_repuestos": costo_repuestos_ed, "costo_mano_obra": costo_mano_obra_ed,
                        "repuesto_cambiado": repuesto_ed.strip() or None,
                        "codigo_repuesto": codigo_repuesto_ed.strip() or None,
                        "cantidad_repuestos": int(cantidad_repuestos_ed) or None,
                        "motivo_cambio_pieza": motivo_ed or [],
                        "motivo_otro_detalle": motivo_otro_ed.strip() or None,
                        "tiempo_garantia": garantia_ed.strip() or None,
                        "serie_factura": serie_factura_ed.strip() or None,
                        "numero_factura": numero_factura_ed.strip() or None,
                        "notas": notas_ed.strip() or None,
                    }
                    if es_preventivo:
                        update_kwargs["realizado"] = bool(realizado_ed)
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


def _render_detalle_mantenimiento(r):
    """Bloque de texto (st.caption) con todos los datos de un registro de
    mantenimiento — compartido entre la tarjeta de la lista y el detalle del
    historial, para no repetir la lógica en dos lugares."""
    costo_rep = r.get("costo_repuestos")
    costo_mo = r.get("costo_mano_obra")
    if costo_rep is not None or costo_mo is not None:
        st.caption(
            f"Proveedor: {r.get('proveedor') or '—'} · Técnico responsable: {r.get('tecnico_responsable') or '—'}  \n"
            f"💵 Repuestos: Q{costo_rep or 0:,.2f} · Mano de obra: Q{costo_mo or 0:,.2f} · "
            f"**Total: Q{r.get('costo') or 0:,.2f}**"
        )
    else:
        st.caption(
            f"Proveedor: {r.get('proveedor') or '—'} · Técnico responsable: {r.get('tecnico_responsable') or '—'} · "
            f"Costo: Q{r.get('costo') or 0:,.2f}"
        )
    if r.get("repuesto_cambiado"):
        detalle_repuesto = f"🔩 Repuesto cambiado: {r['repuesto_cambiado']}"
        if r.get("codigo_repuesto"):
            detalle_repuesto += f" (código: {r['codigo_repuesto']})"
        if r.get("cantidad_repuestos"):
            detalle_repuesto += f" · Cantidad: {r['cantidad_repuestos']}"
        st.caption(detalle_repuesto)
    motivo_txt = _label_motivos(r.get("motivo_cambio_pieza"), r.get("motivo_otro_detalle"))
    if motivo_txt:
        st.caption(f"❓ Motivo de cambio: {motivo_txt}")
    if r.get("tiempo_garantia"):
        st.caption(f"🛡️ Garantía: {r['tiempo_garantia']}")
    if r.get("numero_factura") or r.get("serie_factura"):
        st.caption(f"🧾 Factura — Serie: {r.get('serie_factura') or '—'} · N°: {r.get('numero_factura') or '—'}")
    if r.get("notas"):
        st.caption(f"📝 {r['notas']}")


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
            marcar_realizado = False
            if es_preventivo:
                if _preventivo_realizado(r, hoy_str):
                    estado_txt = " · ✅ Realizado"
                elif _preventivo_vencido(r, hoy_str):
                    estado_txt = " · 🔴 Vencido"
                    marcar_realizado = True
                else:
                    estado_txt = " · 🗓️ Programado"
                    marcar_realizado = True
            st.markdown(f"**📅 {r.get('fecha') or '—'}**{estado_txt}")
            _render_detalle_mantenimiento(r)

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
                if marcar_realizado:
                    if st.button(
                        "✅ Marcar como realizado", key=f"mant_marcar_realizado_{r['id']}",
                        use_container_width=True,
                    ):
                        db.update_mantenimiento(r["id"], realizado=True)
                        st.success("Mantenimiento marcado como realizado.")
                        st.rerun()
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
        "Técnico responsable": r.get("tecnico_responsable") or "—",
        "Costo repuestos (Q)": r.get("costo_repuestos") or 0, "Costo mano de obra (Q)": r.get("costo_mano_obra") or 0,
        "Costo total (Q)": r.get("costo") or 0,
        "Repuesto cambiado": r.get("repuesto_cambiado") or "—", "Código de repuesto": r.get("codigo_repuesto") or "—",
        "Cantidad de repuestos": r.get("cantidad_repuestos") or 0,
        "Motivo de cambio": _label_motivos(r.get("motivo_cambio_pieza"), r.get("motivo_otro_detalle")) or "—",
        "Garantía": r.get("tiempo_garantia") or "—",
        "Serie de factura": r.get("serie_factura") or "—", "N° factura": r.get("numero_factura") or "—",
        "Notas": r.get("notas") or "—",
    } for r in registros])
    st.dataframe(df, use_container_width=True, hide_index=True)
    download_excel_button(
        df, "historial_mantenimiento.xlsx", key=f"mant_descargar_historial_{maquina_id}",
    )

    st.divider()
    st.markdown("**🔎 Ver ficha completa de un mantenimiento**")
    hoy_str = str(date.today())

    def _opcion_label(r):
        return f"{r['tipo']} · {r.get('fecha') or '—'} · {r.get('proveedor') or 'sin proveedor'}"

    opciones = {r["id"]: _opcion_label(r) for r in registros}
    sel_id = st.selectbox(
        "Selecciona un registro", options=list(opciones.keys()), format_func=lambda i: opciones[i],
        key=f"mant_hist_sel_{maquina_id}",
    )
    if sel_id:
        r = next((x for x in registros if x["id"] == sel_id), None)
        if r:
            es_preventivo = r["tipo"] == "Preventivo"
            with st.container(border=True):
                estado_txt = ""
                if es_preventivo:
                    if _preventivo_realizado(r, hoy_str):
                        estado_txt = " · ✅ Realizado"
                    elif _preventivo_vencido(r, hoy_str):
                        estado_txt = " · 🔴 Vencido"
                    else:
                        estado_txt = " · 🗓️ Programado"
                st.markdown(f"**{r['tipo']} · 📅 {r.get('fecha') or '—'}**{estado_txt}")
                _render_detalle_mantenimiento(r)
                fc1, fc2 = st.columns(2)
                with fc1:
                    _mostrar_adjunto(
                        "Factura", f"mant_hist_dl_factura_{r['id']}",
                        r.get("factura_nombre"), r.get("factura_tipo"), r.get("factura_b64"),
                    )
                with fc2:
                    _mostrar_adjunto(
                        "Repuesto viejo", f"mant_hist_dl_repuesto_{r['id']}",
                        r.get("foto_repuesto_nombre"), r.get("foto_repuesto_tipo"), r.get("foto_repuesto_b64"),
                    )


def _render_editar_maquina_inline(maquina, key_suffix):
    """Edición rápida (nombre / tipo / serie / planta) desde la tarjeta de la
    máquina en la vista de lista — para eliminar la máquina se usa el
    expander completo '⚙️ Editar / eliminar esta máquina' dentro de su
    ficha detallada, no aquí."""
    with st.form(f"editar_maquina_inline_{key_suffix}"):
        nombre_ed = st.text_input("Nombre", value=maquina["nombre"])
        tipo_ed = st.text_input(
            "Tipo de máquina (ej. Impresora, Troqueladora)", value=maquina.get("tipo_maquina") or "",
        )
        serie_ed = st.text_input("Número de serie", value=maquina.get("numero_serie") or "")
        codigo_gasto_ed = st.text_input(
            "Código alterno de gasto", value=maquina.get("codigo_alterno_gasto") or "",
        )
        planta_ed = st.selectbox(
            "Planta", PLANTAS_MAQUINARIA,
            index=PLANTAS_MAQUINARIA.index(maquina["planta"]) if maquina["planta"] in PLANTAS_MAQUINARIA else 0,
            key=f"mant_planta_ed_{key_suffix}",
        )
        if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
            if not nombre_ed.strip():
                st.error("El nombre es obligatorio.")
            else:
                db.update_maquina(
                    maquina["id"], nombre=nombre_ed.strip(), tipo_maquina=tipo_ed.strip() or None,
                    numero_serie=serie_ed.strip() or None, planta=planta_ed,
                    codigo_alterno_gasto=codigo_gasto_ed.strip() or None,
                )
                st.session_state.pop(f"mant_editando_maq_{key_suffix}", None)
                st.success("Máquina actualizada.")
                st.rerun()


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
    if maquina.get("codigo_alterno_gasto"):
        detalle += f" · Código alterno de gasto: {maquina['codigo_alterno_gasto']}"
    st.caption(detalle)

    preventivos = db.list_mantenimientos_maquina(maquina_sel_id, tipo="Preventivo")
    hoy_str = str(date.today())
    vencidos_maquina = sorted(
        [p for p in preventivos if _preventivo_vencido(p, hoy_str)], key=lambda p: p["fecha"],
    )
    proximos = sorted(
        [p for p in preventivos if p.get("fecha") and p["fecha"] >= hoy_str
         and not _preventivo_realizado(p, hoy_str)],
        key=lambda p: p["fecha"],
    )
    if vencidos_maquina:
        st.error(
            f"🔴 Hay {len(vencidos_maquina)} mantenimiento(s) preventivo(s) **vencido(s)** — el más antiguo "
            f"estaba programado para **{vencidos_maquina[0]['fecha']}** y todavía no se ha marcado como realizado."
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
                codigo_gasto_maq_ed = st.text_input(
                    "Código alterno de gasto", value=maquina.get("codigo_alterno_gasto") or "",
                )
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
                            codigo_alterno_gasto=codigo_gasto_maq_ed.strip() or None,
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
    mantenimientos_todos = db.list_mantenimientos_todos()
    maquinas_por_id = {m["id"]: m for m in db.list_maquinas()}
    hoy_str = str(date.today())
    mes_actual = hoy_str[:7]

    preventivos_todos = [r for r in mantenimientos_todos if r.get("tipo") == "Preventivo"]
    vencidos_todos = sorted(
        [r for r in preventivos_todos if _preventivo_vencido(r, hoy_str)], key=lambda r: r["fecha"],
    )
    vencen_este_mes = sorted(
        [r for r in preventivos_todos
         if (r.get("fecha") or "").startswith(mes_actual) and not _preventivo_realizado(r, hoy_str)],
        key=lambda r: r["fecha"],
    )
    realizados_este_mes = sum(
        1 for r in mantenimientos_todos
        if (r.get("fecha") or "").startswith(mes_actual)
        and (r.get("tipo") != "Preventivo" or _preventivo_realizado(r, hoy_str))
    )

    st.subheader("📊 Resumen general de mantenimiento")

    if vencidos_todos:
        st.error(f"🔴 Hay {len(vencidos_todos)} mantenimiento(s) preventivo(s) **vencido(s)** sin realizar.")
        with st.expander(f"Ver los {len(vencidos_todos)} vencido(s)"):
            for r in vencidos_todos:
                maq = maquinas_por_id.get(r.get("maquina_id"))
                nombre_maq = maq["nombre"] if maq else "Máquina eliminada"
                st.caption(
                    f"🔴 **{nombre_maq}** — programado para {r['fecha']} · "
                    f"{r.get('proveedor') or 'sin proveedor'}"
                )

    with st.expander(f"🗓️ Preventivos que vencen este mes ({len(vencen_este_mes)})"):
        if not vencen_este_mes:
            st.caption("No hay mantenimientos preventivos programados para este mes que sigan pendientes.")
        else:
            for r in vencen_este_mes:
                maq = maquinas_por_id.get(r.get("maquina_id"))
                nombre_maq = maq["nombre"] if maq else "Máquina eliminada"
                st.caption(f"🗓️ **{nombre_maq}** — {r['fecha']} · {r.get('proveedor') or 'sin proveedor'}")

    m1, m2, m3 = st.columns(3)
    m1.metric("✅ Realizados este mes", realizados_este_mes)
    m2.metric("🗓️ Preventivos que vencen este mes", len(vencen_este_mes))
    m3.metric("🔴 Preventivos vencidos", len(vencidos_todos))

    df_kpi = _construir_kpi_mensual(mantenimientos_todos, hoy_str)
    if df_kpi["Cantidad"].sum() > 0:
        df_kpi = df_kpi.sort_values("_orden")
        fig = px.bar(
            df_kpi, x="Mes", y="Cantidad", color="Tipo", barmode="group",
            category_orders={"Mes": [_label_mes(m) for m in _ultimos_meses(6)]},
            color_discrete_map={"Preventivo": CATEGORICAL[0], "Correctivo": CATEGORICAL[1]},
        )
        st.plotly_chart(
            base_layout(fig, title="Mantenimientos realizados por mes (últimos 6 meses)", height=340),
            use_container_width=True,
        )
    else:
        st.caption("Todavía no hay suficientes mantenimientos realizados para mostrar la gráfica mensual.")

    st.divider()

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
                            title_col, edit_col = st.columns([5, 1])
                            title_col.markdown(f"**🖨️ {maq['nombre']}**")
                            editando_maq_key = f"mant_editando_maq_{maq['id']}"
                            if puede_gestionar:
                                if edit_col.button("✏️", key=f"mant_editar_maq_{maq['id']}"):
                                    st.session_state[editando_maq_key] = not st.session_state.get(
                                        editando_maq_key, False,
                                    )
                                    st.rerun()
                            st.caption(maq.get("tipo_maquina") or "Tipo no especificado")
                            if maq.get("numero_serie"):
                                st.caption(f"Serie: {maq['numero_serie']}")
                            if maq.get("codigo_alterno_gasto"):
                                st.caption(f"Código alterno de gasto: {maq['codigo_alterno_gasto']}")
                            n_prev = len(db.list_mantenimientos_maquina(maq["id"], tipo="Preventivo"))
                            n_corr = len(db.list_mantenimientos_maquina(maq["id"], tipo="Correctivo"))
                            st.caption(f"🛠️ {n_prev} preventivo(s) · 🔧 {n_corr} correctivo(s)")
                            if st.session_state.get(editando_maq_key):
                                _render_editar_maquina_inline(maq, maq["id"])
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
                        codigo_gasto_maq = st.text_input("Código alterno de gasto (opcional)")
                        if st.form_submit_button("Registrar máquina", use_container_width=True):
                            if not nombre_maq.strip():
                                st.error("El nombre de la máquina es obligatorio.")
                            else:
                                db.create_maquina(
                                    nombre_maq.strip(), tipo_maq.strip() or None, planta,
                                    serie_maq.strip() or None,
                                    codigo_alterno_gasto=codigo_gasto_maq.strip() or None,
                                )
                                st.success(f"Máquina '{nombre_maq}' registrada en Planta {planta}.")
                                st.rerun()
