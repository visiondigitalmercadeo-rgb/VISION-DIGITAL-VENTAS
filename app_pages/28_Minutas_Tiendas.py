from datetime import date

import pandas as pd
import streamlit as st

import auth
import database as db
from config import APP_URL, ESTADOS_PENDIENTE_MINUTA, PUESTOS_ASESOR_VENTAS, TICKET_TIENDAS
from utils import download_excel_button, minuta_tienda_pdf_bytes, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("📝 Minutas de Tienda")
st.caption(
    "El jefe (o sub jefe) de tienda deja constancia de su reunión: un checklist de los temas que se "
    "tocaron y los pendientes que quedaron abiertos. El jefe de línea (y los administradores) le dan "
    "seguimiento a cada pendiente hasta que queda resuelto."
)

ESCRIBIR_RESPONSABLE_NUEVO = "✍️ Escribir otro nombre"
MESES_ES = {
    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril", "05": "Mayo", "06": "Junio",
    "07": "Julio", "08": "Agosto", "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
}

puede_crear = auth.puede_crear_minuta_tienda()
puede_seguimiento = auth.puede_gestionar_pendientes_minuta()
puede_administrar_temas = auth.puede_administrar_temas_minuta()
puede_gestionar_metas = auth.puede_gestionar_metas_tienda()
tienda_usuario = auth.current_user_tienda()


def _opciones_responsable(tienda):
    personal = db.list_personal_tiendas(tienda=tienda) if tienda else []
    nombres = [p["nombre"] for p in personal if p.get("nombre")]
    return [ESCRIBIR_RESPONSABLE_NUEVO] + nombres


def _emoji_estado(estado):
    return {"Pendiente": "🔴", "En proceso": "🟡", "Resuelto": "🟢"}.get(estado, "⚪")


def _etiqueta_mes(mes: str) -> str:
    """'2026-09' -> 'Septiembre 2026'."""
    if not mes or "-" not in mes:
        return mes or "—"
    anio, num_mes = mes.split("-")
    return f"{MESES_ES.get(num_mes, num_mes)} {anio}"


def _pct(venta, meta):
    if not meta:
        return None
    return (venta / meta) * 100


_PUESTOS_ASESOR_VENTAS_NORM = {p.strip().lower() for p in PUESTOS_ASESOR_VENTAS}


def _es_asesor_ventas(persona):
    """"personal_tiendas" no tiene un campo 'rol' real (solo 'puesto',
    texto libre) — se identifica a los asesores de ventas comparando el
    puesto (sin mayúsculas/acentos) contra config.PUESTOS_ASESOR_VENTAS
    ('Diseñador' es el puesto que quedó de la carga inicial para ellos)."""
    return (persona.get("puesto") or "").strip().lower() in _PUESTOS_ASESOR_VENTAS_NORM


def _metas_del_mes_de_minuta(tienda, fecha_reunion):
    """Metas/ventas de los asesores de una tienda para el mes de la
    reunión (no necesariamente el mes actual) — lo que va en la sección 3
    del PDF de la minuta (ver utils.minuta_tienda_pdf_bytes)."""
    mes = str(fecha_reunion or "")[:7]
    if not tienda or not mes:
        return []
    return db.list_metas_tienda(tienda=tienda, mes=mes)


def _avisar_nueva_minuta_por_correo(minuta_id):
    """Manda por correo el PDF de la minuta recién creada (checklist +
    pendientes + metas vs. ventas) a los correos configurados en '✉️
    Correos que reciben el PDF de la minuta'. No hace nada (ni muestra
    error) si todavía no hay correos guardados o si el remitente no está
    configurado — ver database.correo_disponible. Nunca interrumpe el
    guardado de la minuta si el correo falla (enviar_correo_aviso_adjunto
    nunca lanza excepción)."""
    correos = db.get_minutas_tiendas_correos_aviso()
    if not correos:
        return
    minuta_completa = db.get_minuta_tienda(minuta_id)
    if not minuta_completa:
        return
    metas_pdf = _metas_del_mes_de_minuta(minuta_completa.get("tienda"), minuta_completa.get("fecha_reunion"))
    pdf_bytes = minuta_tienda_pdf_bytes(minuta_completa, metas_pdf)
    numero = minuta_completa.get("numero")
    numero_txt = f"MIN-{numero:04d}" if isinstance(numero, int) else "MIN-____"
    asunto = f"📝 Nueva minuta de tienda {numero_txt} — {minuta_completa.get('tienda') or '—'}"
    cuerpo = (
        f"Se registró una nueva minuta de tienda.\n\n"
        f"N° de minuta: {numero_txt}\n"
        f"Tienda: {minuta_completa.get('tienda') or '—'}\n"
        f"Fecha de la reunión: {minuta_completa.get('fecha_reunion') or '—'}\n"
        f"Elaborada por: {minuta_completa.get('creado_por_nombre') or '—'}\n\n"
        f"Se adjunta el PDF con el checklist de temas tratados, los pendientes solicitados y las metas "
        f"vs. ventas por asesor de ventas del mes.\n\n"
        f"Ver en la plataforma: {APP_URL}"
    )
    db.enviar_correo_aviso_adjunto(
        correos, asunto, cuerpo, adjunto_bytes=pdf_bytes, adjunto_nombre=f"{numero_txt}.pdf",
    )


tab_pendientes, tab_minutas, tab_metas, tab_nueva = st.tabs(
    ["📌 Pendientes", "🗒️ Minutas", "🎯 Metas", "➕ Nueva minuta"]
)

# --------------------------------------------------------------------------
# Pendientes — vista consolidada de TODOS los pendientes de TODAS las
# minutas (con el filtro de tienda cuando aplica), para que el jefe de
# línea/admin les dé seguimiento sin tener que abrir minuta por minuta.
# --------------------------------------------------------------------------
with tab_pendientes:
    if tienda_usuario:
        minutas_p = db.list_minutas_tiendas(tienda=tienda_usuario)
        st.caption(f"Mostrando solo la tienda: **{tienda_usuario}**")
    else:
        elegido_tienda_p = st.selectbox("Filtrar por tienda", ["Todas"] + TICKET_TIENDAS, key="mn_pend_filtro_tienda")
        minutas_p = db.list_minutas_tiendas(tienda=None if elegido_tienda_p == "Todas" else elegido_tienda_p)

    mostrar_resueltos = st.checkbox("Mostrar también los pendientes ya resueltos", key="mn_pend_mostrar_resueltos")

    filas_pendientes = []
    for m in minutas_p:
        for i, p in enumerate(m.get("pendientes") or []):
            if not mostrar_resueltos and p.get("estado") == "Resuelto":
                continue
            filas_pendientes.append((m, i, p))

    if not filas_pendientes:
        st.caption("No hay pendientes que mostrar con este filtro.")
    else:
        download_excel_button(
            pd.DataFrame([{
                "Minuta": f"MIN-{m['numero']:04d}" if isinstance(m.get("numero"), int) else "—",
                "Tienda": m.get("tienda"), "Fecha reunión": m.get("fecha_reunion"),
                "Pendiente": p.get("descripcion"), "Responsable": p.get("responsable") or "—",
                "Fecha límite": p.get("fecha_limite") or "—", "Estado": p.get("estado"),
            } for m, i, p in filas_pendientes]),
            "pendientes_minutas_tienda.xlsx", key="mn_pend_descargar_excel",
        )

        orden_estado = {"Pendiente": 0, "En proceso": 1, "Resuelto": 2}
        filas_pendientes.sort(key=lambda t: (orden_estado.get(t[2].get("estado"), 9), t[2].get("fecha_limite") or ""))

        for m, i, p in filas_pendientes:
            numero_txt = f"MIN-{m['numero']:04d} · " if isinstance(m.get("numero"), int) else ""
            with st.container(border=True):
                st.markdown(f"{_emoji_estado(p.get('estado'))} **{p.get('descripcion')}**")
                st.caption(
                    f"🏬 {m.get('tienda') or '—'} · 🙋 Responsable: {p.get('responsable') or '—'} · "
                    f"📅 Límite: {p.get('fecha_limite') or 'sin fecha'} · {numero_txt}reunión del {m.get('fecha_reunion') or '—'}"
                )
                seguimiento_previo = p.get("seguimiento") or []
                if seguimiento_previo:
                    with st.expander(f"📜 Historial de seguimiento ({len(seguimiento_previo)})"):
                        for s in seguimiento_previo:
                            st.caption(f"🕒 {(s.get('creado_en') or '')[:16].replace('T', ' ')} — **{s.get('autor_nombre')}**: {s.get('comentario')}")

                if puede_seguimiento:
                    with st.form(f"mn_seguimiento_{m['id']}_{i}"):
                        nuevo_estado = st.selectbox(
                            "Estado", ESTADOS_PENDIENTE_MINUTA,
                            index=ESTADOS_PENDIENTE_MINUTA.index(p.get("estado")) if p.get("estado") in ESTADOS_PENDIENTE_MINUTA else 0,
                            key=f"mn_estado_{m['id']}_{i}",
                        )
                        comentario_nuevo = st.text_input(
                            "Comentario de seguimiento (opcional)", key=f"mn_comentario_{m['id']}_{i}",
                            placeholder="Ej. Ya se coordinó con el proveedor, entrega la próxima semana.",
                        )
                        if st.form_submit_button("💾 Guardar seguimiento", use_container_width=True):
                            db.update_pendiente_minuta(
                                m["id"], i, estado=nuevo_estado, comentario=comentario_nuevo,
                                autor_nombre=user["nombre"],
                            )
                            st.success("Seguimiento guardado.")
                            st.rerun()

# --------------------------------------------------------------------------
# Minutas — historial de reuniones, con su checklist completo.
# --------------------------------------------------------------------------
with tab_minutas:
    if tienda_usuario:
        minutas = db.list_minutas_tiendas(tienda=tienda_usuario)
        st.caption(f"Mostrando solo la tienda: **{tienda_usuario}**")
    else:
        elegido_tienda_m = st.selectbox("Filtrar por tienda", ["Todas"] + TICKET_TIENDAS, key="mn_lista_filtro_tienda")
        minutas = db.list_minutas_tiendas(tienda=None if elegido_tienda_m == "Todas" else elegido_tienda_m)

    if not minutas:
        st.caption("Todavía no hay minutas registradas.")
    else:
        download_excel_button(
            pd.DataFrame([{
                "N° Minuta": m.get("numero"), "Tienda": m.get("tienda"), "Fecha reunión": m.get("fecha_reunion"),
                "Elaborada por": m.get("creado_por_nombre"),
                "Temas tratados": len(m.get("checklist") or []),
                "Pendientes": len(m.get("pendientes") or []),
                "Pendientes resueltos": sum(1 for p in (m.get("pendientes") or []) if p.get("estado") == "Resuelto"),
            } for m in minutas]),
            "minutas_tienda.xlsx", key="mn_lista_descargar_excel",
        )

        for m in minutas:
            mid = m["id"]
            numero_txt = f"MIN-{m['numero']:04d}" if isinstance(m.get("numero"), int) else "—"
            puede_editar_esta = puede_seguimiento or (
                puede_crear and (user["rol"] == "admin" or m.get("creado_por_id") == user["id"])
            )
            with st.expander(f"🗒️ {numero_txt} — {m.get('tienda') or '—'} · {m.get('fecha_reunion') or '—'}"):
                st.caption(f"Elaborada por: {m.get('creado_por_nombre') or '—'}")
                if m.get("notas_generales"):
                    st.caption(f"📝 Notas generales: {m['notas_generales']}")

                checklist = m.get("checklist") or []
                if checklist:
                    st.markdown("**Temas del checklist:**")
                    for item in checklist:
                        marca = "✅" if item.get("tratado") else "⬜"
                        etiqueta_extra = " _(agregado, no estaba en la lista)_" if item.get("extra") else ""
                        st.markdown(f"- {marca} {item.get('tema')}{etiqueta_extra}")
                else:
                    st.caption("Sin temas registrados.")

                pendientes_m = m.get("pendientes") or []
                if pendientes_m:
                    st.markdown("**Pendientes:**")
                    for p in pendientes_m:
                        st.markdown(
                            f"- {_emoji_estado(p.get('estado'))} {p.get('descripcion')} "
                            f"(👤 {p.get('responsable') or '—'}, estado: {p.get('estado')})"
                        )
                else:
                    st.caption("Sin pendientes.")

                st.divider()
                metas_pdf_hist = _metas_del_mes_de_minuta(m.get("tienda"), m.get("fecha_reunion"))
                st.download_button(
                    "📄 Ver minuta (PDF)", data=minuta_tienda_pdf_bytes(m, metas_pdf_hist),
                    file_name=f"minuta_{m.get('numero') if isinstance(m.get('numero'), int) else mid}.pdf",
                    mime="application/pdf", use_container_width=True, key=f"mn_pdf_{mid}",
                )

                if puede_editar_esta:
                    if st.button("🗑️ Eliminar esta minuta", key=f"mn_eliminar_{mid}"):
                        db.delete_minuta_tienda(mid)
                        st.success("Minuta eliminada.")
                        st.rerun()

# --------------------------------------------------------------------------
# Metas — meta mensual y venta actual de cada asesor de ventas, con
# historial mes a mes.
# --------------------------------------------------------------------------
with tab_metas:
    st.caption(
        "El jefe (o sub jefe) de tienda le pone una meta mensual, en quetzales, a cada asesor de ventas "
        "de su sucursal y va actualizando su venta del mes. Cada mes queda guardado por separado, así "
        "se tiene el historial mes a mes."
    )

    if not puede_gestionar_metas:
        st.info("Solo el jefe de tienda, sub jefe de tienda, jefe de línea y los administradores usan esta sección.")
    else:
        if tienda_usuario:
            tienda_metas = tienda_usuario
            st.caption(f"Tienda: **{tienda_usuario}**")
        else:
            tienda_metas = st.selectbox("Tienda", TICKET_TIENDAS, key="mt_tienda_sel")

        mes_actual = db.mes_actual()
        sub_mes_actual, sub_historial = st.tabs([f"📅 {_etiqueta_mes(mes_actual)} (mes actual)", "📊 Historial"])

        with sub_mes_actual:
            asesores = [p for p in db.list_personal_tiendas(tienda=tienda_metas) if _es_asesor_ventas(p)]
            if not asesores:
                st.info(
                    "Todavía no hay asesores de ventas cargados para esta tienda (personal con puesto "
                    "'Diseñador' o 'Asesor de ventas'). Se agregan desde 'Administración de usuarios' → "
                    "'📥 Carga inicial de personal', o desde 'Capacitación' → 'Personal por tienda' → "
                    "'➕ Agregar personal'."
                )
            else:
                registros_mes = {
                    r["asesor_nombre"]: r for r in db.list_metas_tienda(tienda=tienda_metas, mes=mes_actual)
                }
                valores_form = {}
                for asesor in asesores:
                    nombre = asesor["nombre"]
                    existente = registros_mes.get(nombre)
                    with st.container(border=True):
                        st.markdown(f"**{nombre}**")
                        c1, c2, c3 = st.columns(3)
                        meta_val = c1.number_input(
                            "Meta (Q)", min_value=0.0, step=500.0,
                            value=float(existente["meta"]) if existente else 0.0,
                            key=f"mt_meta_{nombre}",
                        )
                        venta_val = c2.number_input(
                            "Venta actual (Q)", min_value=0.0, step=100.0,
                            value=float(existente["venta_actual"]) if existente else 0.0,
                            key=f"mt_venta_{nombre}",
                        )
                        pct = _pct(venta_val, meta_val)
                        with c3:
                            st.markdown("&nbsp;")
                            if pct is None:
                                st.caption("Pon una meta para ver el % de cumplimiento.")
                            else:
                                st.progress(min(pct / 100, 1.0), text=f"{pct:.0f}% de la meta")
                        valores_form[nombre] = (meta_val, venta_val)

                if st.button("💾 Guardar metas y ventas del mes", key="mt_guardar", use_container_width=True):
                    for nombre, (meta_val, venta_val) in valores_form.items():
                        db.upsert_meta_tienda(
                            tienda_metas, nombre, mes_actual, meta=meta_val, venta_actual=venta_val,
                            actualizado_por_id=user["id"],
                        )
                    st.success("Metas y ventas del mes actualizadas.")
                    st.rerun()

        with sub_historial:
            todos_los_registros = db.list_metas_tienda(tienda=tienda_metas)
            meses_disponibles = sorted({r["mes"] for r in todos_los_registros if r.get("mes")}, reverse=True)

            if not meses_disponibles:
                st.caption("Todavía no hay historial guardado para esta tienda.")
            else:
                mes_elegido = st.selectbox(
                    "Mes", meses_disponibles, format_func=_etiqueta_mes, key="mt_hist_mes",
                )
                registros_hist = [r for r in todos_los_registros if r.get("mes") == mes_elegido]
                registros_hist.sort(key=lambda r: r.get("asesor_nombre") or "")

                df_hist = pd.DataFrame([{
                    "Asesor": r["asesor_nombre"], "Meta (Q)": r.get("meta") or 0.0,
                    "Venta actual (Q)": r.get("venta_actual") or 0.0,
                    "% de la meta": round(_pct(r.get("venta_actual") or 0.0, r.get("meta") or 0.0) or 0.0, 1),
                } for r in registros_hist])
                st.dataframe(df_hist, use_container_width=True, hide_index=True)

                total_meta = sum(r.get("meta") or 0.0 for r in registros_hist)
                total_venta = sum(r.get("venta_actual") or 0.0 for r in registros_hist)
                pct_total = _pct(total_venta, total_meta)
                c1, c2, c3 = st.columns(3)
                c1.metric("Meta total de la tienda", f"Q {total_meta:,.2f}")
                c2.metric("Venta total de la tienda", f"Q {total_venta:,.2f}")
                c3.metric("% de cumplimiento", f"{pct_total:.0f}%" if pct_total is not None else "—")

                download_excel_button(
                    df_hist, f"metas_{tienda_metas}_{mes_elegido}.xlsx", key="mt_hist_descargar_excel",
                )

# --------------------------------------------------------------------------
# Nueva minuta
# --------------------------------------------------------------------------
with tab_nueva:
    if puede_administrar_temas:
        with st.expander("⚙️ Temas predeterminados del checklist"):
            st.caption(
                "Esta lista es la misma para todas las tiendas — cada jefe de tienda solo la marca al "
                "crear su minuta. Escribe un tema por línea."
            )
            temas_actuales_admin = db.get_temas_predeterminados_minuta()
            temas_texto_admin = st.text_area(
                "Temas predeterminados", value="\n".join(temas_actuales_admin),
                key="mn_temas_admin_texto", height=200,
            )
            if st.button("💾 Guardar temas predeterminados", key="mn_temas_admin_guardar"):
                nuevos_temas_admin = [t.strip() for t in temas_texto_admin.split("\n") if t.strip()]
                db.set_temas_predeterminados_minuta(nuevos_temas_admin)
                st.success("Temas predeterminados actualizados.")
                st.rerun()

        with st.expander("✉️ Correos que reciben el PDF de la minuta"):
            if not db.correo_disponible():
                st.info(
                    "Todavía no está configurado el correo que manda los avisos (falta conectar una cuenta "
                    "de Gmail en la configuración de la plataforma) — mientras tanto, esta sección no manda "
                    "nada, pero puedes ir guardando los correos de una vez."
                )
            correos_actuales_mn = db.get_minutas_tiendas_correos_aviso()
            with st.form("mn_correos_aviso"):
                correos_texto_mn = st.text_area(
                    "Correos que reciben la minuta — uno por línea (o separados por coma)",
                    value="\n".join(correos_actuales_mn),
                    help=(
                        "Cada vez que se guarda una minuta nueva, se les manda automáticamente por correo el "
                        "PDF con el checklist, los pendientes y las metas vs. ventas del mes."
                    ),
                )
                if st.form_submit_button("💾 Guardar correos", use_container_width=True):
                    nuevos_correos_mn = [c.strip() for c in correos_texto_mn.replace(",", "\n").split("\n") if c.strip()]
                    db.set_minutas_tiendas_correos_aviso(nuevos_correos_mn)
                    st.success("Correos actualizados.")
                    st.rerun()

    if not puede_crear:
        st.info("Solo el jefe de tienda, sub jefe de tienda, jefe de línea y los administradores pueden crear minutas.")
    else:
        st.session_state.setdefault("mn_pendientes_borrador", [])

        if tienda_usuario:
            tienda_nueva = tienda_usuario
            st.caption(f"Tienda: **{tienda_usuario}**")
        else:
            tienda_nueva = st.selectbox("Tienda", TICKET_TIENDAS, key="mn_nueva_tienda")
        fecha_reunion = st.date_input("Fecha de la reunión", value=date.today(), key="mn_nueva_fecha")

        st.divider()
        st.markdown("#### ✅ Temas tratados en la reunión")
        temas_predeterminados = db.get_temas_predeterminados_minuta()
        if not temas_predeterminados:
            st.caption(
                "Todavía no hay temas predeterminados configurados"
                + (" — ábrelo arriba en '⚙️ Temas predeterminados del checklist' para agregarlos."
                   if puede_administrar_temas else
                   " — pide a un administrador o al jefe de línea que los configure.")
            )
        temas_marcados = {}
        for idx, tema in enumerate(temas_predeterminados):
            temas_marcados[tema] = st.checkbox(tema, key=f"mn_tema_pred_{idx}")

        agregar_extra = st.checkbox(
            "➕ Se tocó un tema que no está en la lista", key="mn_tema_extra_toggle",
        )
        temas_extra_texto = ""
        if agregar_extra:
            temas_extra_texto = st.text_area(
                "Escribe el/los tema(s) extra (uno por línea)", key="mn_temas_extra_texto",
            )

        notas_generales = st.text_area("Notas generales de la reunión (opcional)", key="mn_notas_generales")

        st.divider()
        st.markdown("#### 📌 Pendientes que quedaron de la reunión")
        # Widgets sueltos, no un st.form: "Responsable" necesita revelar un
        # campo de texto en cuanto se elige "Escribir otro nombre", y eso
        # solo pasa con un rerun inmediato — dentro de un form los widgets
        # no reaccionan hasta que se presiona el botón de enviar, así que el
        # campo nuevo aparecería demasiado tarde para poder escribir en él.
        descripcion_nueva = st.text_input("¿Qué queda pendiente?", key="mn_pend_descripcion")
        colp1, colp2 = st.columns(2)
        opciones_resp = _opciones_responsable(tienda_nueva)
        responsable_sel = colp1.selectbox("Responsable", opciones_resp, key="mn_pend_responsable_sel")
        if responsable_sel == ESCRIBIR_RESPONSABLE_NUEVO:
            responsable_texto = colp1.text_input("Nombre del responsable", key="mn_pend_responsable_nuevo")
        else:
            responsable_texto = responsable_sel
        con_fecha = colp2.checkbox("Con fecha límite", key="mn_pend_con_fecha")
        fecha_limite_nueva = colp2.date_input("Fecha límite", value=date.today(), key="mn_pend_fecha_limite") if con_fecha else None
        if st.button("➕ Agregar pendiente", key="mn_btn_agregar_pendiente", use_container_width=True):
            if not descripcion_nueva.strip():
                st.error("Escribe qué queda pendiente antes de agregarlo.")
            else:
                st.session_state["mn_pendientes_borrador"].append({
                    "descripcion": descripcion_nueva.strip(),
                    "responsable": (responsable_texto or "").strip(),
                    "fecha_limite": str(fecha_limite_nueva) if fecha_limite_nueva else None,
                })
                for k in ("mn_pend_descripcion", "mn_pend_responsable_nuevo"):
                    st.session_state.pop(k, None)
                st.rerun()

        if st.session_state["mn_pendientes_borrador"]:
            for idx, p in enumerate(st.session_state["mn_pendientes_borrador"]):
                c1, c2 = st.columns([6, 1])
                texto_p = f"🔴 {p['descripcion']} (👤 {p.get('responsable') or '—'}"
                texto_p += f", límite {p['fecha_limite']})" if p.get("fecha_limite") else ")"
                c1.markdown(texto_p)
                if c2.button("🗑️", key=f"mn_quitar_pend_{idx}"):
                    st.session_state["mn_pendientes_borrador"].pop(idx)
                    st.rerun()
        else:
            st.caption("Todavía no has agregado ningún pendiente.")

        st.divider()
        if st.button("💾 Guardar minuta", key="mn_guardar_minuta", use_container_width=True):
            checklist_final = [
                {"tema": tema, "tratado": bool(marcado), "extra": False}
                for tema, marcado in temas_marcados.items()
            ]
            if agregar_extra:
                for linea in temas_extra_texto.splitlines():
                    if linea.strip():
                        checklist_final.append({"tema": linea.strip(), "tratado": True, "extra": True})

            nueva_minuta_id = db.create_minuta_tienda(
                user["id"], user["nombre"], tienda_nueva, fecha_reunion,
                checklist_final, st.session_state["mn_pendientes_borrador"],
                notas_generales=notas_generales,
            )
            _avisar_nueva_minuta_por_correo(nueva_minuta_id)
            st.session_state["mn_pendientes_borrador"] = []
            for idx in range(len(temas_predeterminados)):
                st.session_state.pop(f"mn_tema_pred_{idx}", None)
            st.session_state.pop("mn_tema_extra_toggle", None)
            st.session_state.pop("mn_temas_extra_texto", None)
            st.session_state.pop("mn_notas_generales", None)
            st.success("Minuta guardada.")
            st.rerun()
