"""Litografía — cotizador técnico: la ficha de especificación de un trabajo
de impresión (formato, tintas, páginas, papel, máquina) con cálculo
automático de pliegos, planchas, pasadas de máquina y costo total, inspirado
en sistemas como Logic Print. Pestaña independiente (no se conecta con
'Cotizaciones', que es el seguimiento comercial de fecha/monto/estado).

Cómo se calcula cada componente del trabajo (por ejemplo la cubierta y el
interior de una revista, por separado):
  1. Se ve cuántas páginas del formato final caben en el pliego de papel
     elegido (probando las dos orientaciones, como se haría a mano).
  2. Esas páginas caben en las 2 caras del pliego → páginas por pliego.
  3. Con el total de páginas del componente se calcula cuántos "diseños"
     de pliego distintos hacen falta (ej. una revista de 48 páginas interiores
     a 16 páginas por pliego = 3 diseños distintos).
  4. Pliegos = diseños × cantidad de ejemplares (+ % de merma/desperdicio).
  5. Pasadas de máquina = pliegos × 2 (una pasada por cada cara).
  6. Planchas = diseños × (tintas de frente + tintas de dorso).
  7. Costo = pliegos × costo del papel  +  planchas × costo de plancha
           + (pasadas / 1000) × costo por millar de pasadas de la máquina.
"""

import math

import pandas as pd
import streamlit as st

import auth
import database as db
from config import ESTADOS_LITO_COTIZACION, LITO_TINTAS_PRESETS
from utils import download_excel_button, money, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🖨️ Litografía — Cotizador técnico")
st.caption(
    "Ficha técnica de un trabajo de impresión (formato, tintas, páginas, papel, máquina) con "
    "cálculo automático de pliegos, planchas, pasadas de máquina y costo — inspirado en Logic Print."
)

puede_gestionar = auth.puede_gestionar_litografia()
puede_admin_catalogos = auth.puede_administrar_catalogos_litografia()


def _calcular_componente(formato_ancho, formato_alto, paginas, tintas_frente, tintas_dorso,
                          papel, maquina, cantidad, merma_pct):
    """Calcula pliegos/planchas/pasadas/costo para UN componente del trabajo.
    Prueba el papel en las dos orientaciones y se queda con la que rinde más
    páginas. Devuelve None si el formato no cabe en el pliego elegido."""
    if not papel or not maquina or formato_ancho <= 0 or formato_alto <= 0:
        return None
    pliego_ancho, pliego_alto = float(papel["ancho"]), float(papel["alto"])

    def n_up(pw, ph, fw, fh):
        return math.floor(pw / fw) * math.floor(ph / fh)

    por_lado = max(
        n_up(pliego_ancho, pliego_alto, formato_ancho, formato_alto),
        n_up(pliego_ancho, pliego_alto, formato_alto, formato_ancho),
    )
    if por_lado <= 0:
        return None

    paginas_por_pliego = por_lado * 2  # las 2 caras del pliego
    num_disenios = math.ceil(paginas / paginas_por_pliego) if paginas > 0 else 1
    pliegos = math.ceil(cantidad * num_disenios * (1 + (merma_pct or 0) / 100))
    pasadas = pliegos * 2
    planchas = num_disenios * (tintas_frente + tintas_dorso)

    costo_papel = pliegos * float(papel.get("costo_pliego") or 0)
    costo_planchas = planchas * float(maquina.get("costo_plancha") or 0)
    costo_maquina = (pasadas / 1000) * float(maquina.get("costo_millar_pasadas") or 0)
    costo_total = costo_papel + costo_planchas + costo_maquina

    return {
        "paginas_por_pliego": paginas_por_pliego, "num_disenios": num_disenios,
        "pliegos": pliegos, "pasadas": pasadas, "planchas": planchas,
        "costo_papel": costo_papel, "costo_planchas": costo_planchas,
        "costo_maquina": costo_maquina, "costo_total": costo_total,
    }


def _label_papel(p):
    return (
        f"{p['tipo']} — {p.get('fabricante') or '—'} — {p.get('gramaje', 0):.0f}g — "
        f"{p.get('ancho', 0):.0f}x{p.get('alto', 0):.0f}cm — {money(p.get('costo_pliego'))}/pliego"
    )


def _label_maquina(m):
    return (
        f"{m['nombre']} (máx {m.get('ancho_max', 0):.0f}x{m.get('alto_max', 0):.0f}cm)"
    )


tab_nueva, tab_lista, tab_maquinas, tab_papel = st.tabs(
    ["🧮 Nueva cotización", "📋 Cotizaciones guardadas", "🖨️ Máquinas", "📄 Papel"]
)

# ---------------------------------------------------------------------------
# Nueva cotización
# ---------------------------------------------------------------------------
with tab_nueva:
    if not puede_gestionar:
        st.info("Tu rol solo puede consultar cotizaciones guardadas — no puede crear nuevas.")
    maquinas = db.list_lito_maquinas(solo_activos=True)
    papeles = db.list_lito_papeles(solo_activos=True)

    if not maquinas or not papeles:
        st.warning(
            "Todavía no hay máquinas o tipos de papel activos en el catálogo. Agrégalos primero "
            "en las pestañas **🖨️ Máquinas** y **📄 Papel**."
        )
    elif puede_gestionar:
        st.session_state.setdefault("lito_n_componentes", 1)
        st.session_state.setdefault("lito_n_acabados", 0)

        st.markdown("#### Datos del trabajo")
        c1, c2, c3 = st.columns(3)
        cliente = c1.text_input("Cliente", key="lito_cliente")
        nit = c2.text_input("NIT (opcional)", key="lito_nit")
        descripcion = c3.text_input("Descripción del trabajo", key="lito_descripcion",
                                     placeholder="Ej. Revista de 52 páginas")
        c4, c5, c6 = st.columns(3)
        cantidad = c4.number_input("Cantidad de ejemplares", min_value=1, value=1000, step=1, key="lito_cantidad")
        merma_pct = c5.number_input("% de merma/desperdicio", min_value=0.0, value=1.0, step=0.5, key="lito_merma")
        margen_pct = c6.number_input("% de margen de utilidad", min_value=0.0, value=30.0, step=5.0, key="lito_margen")

        st.divider()
        st.markdown("#### Componentes del trabajo")
        st.caption(
            "Un trabajo puede tener una o varias partes con papel/tintas distintos — por ejemplo, "
            "la cubierta y el interior de una revista o libro. Agrega uno por cada parte."
        )

        bc1, bc2, _ = st.columns([1, 1, 3])
        if bc1.button("➕ Agregar componente", use_container_width=True):
            st.session_state["lito_n_componentes"] += 1
            st.rerun()
        if st.session_state["lito_n_componentes"] > 1:
            if bc2.button("➖ Quitar último", use_container_width=True):
                st.session_state["lito_n_componentes"] -= 1
                st.rerun()

        opciones_papel = {_label_papel(p): p["id"] for p in papeles}
        opciones_maquina = {_label_maquina(m): m["id"] for m in maquinas}
        nombres_default = ["Cubierta", "Interior"]

        componentes_calc = []
        for i in range(st.session_state["lito_n_componentes"]):
            with st.container(border=True):
                default_nombre = nombres_default[i] if i < len(nombres_default) else f"Componente {i + 1}"
                nc1, nc2 = st.columns([2, 1])
                nombre_comp = nc1.text_input("Nombre del componente", value=default_nombre, key=f"lito_comp_nombre_{i}")

                fc1, fc2, fc3 = st.columns(3)
                formato_ancho = fc1.number_input("Formato ancho (cm)", min_value=0.1, value=21.0, step=0.1, key=f"lito_comp_fa_{i}")
                formato_alto = fc2.number_input("Formato alto (cm)", min_value=0.1, value=29.7, step=0.1, key=f"lito_comp_fh_{i}")
                paginas = fc3.number_input("Páginas", min_value=1, value=4, step=1, key=f"lito_comp_pag_{i}")

                tc1, tc2 = st.columns(2)
                preset_key = tc1.selectbox("Tintas (frente+dorso)", list(LITO_TINTAS_PRESETS.keys()), key=f"lito_comp_tintas_preset_{i}")
                preset_val = LITO_TINTAS_PRESETS[preset_key]
                if preset_val is None:
                    pc1, pc2 = tc2.columns(2)
                    tintas_frente = pc1.number_input("Frente", min_value=0, max_value=8, value=4, step=1, key=f"lito_comp_tf_{i}")
                    tintas_dorso = pc2.number_input("Dorso", min_value=0, max_value=8, value=0, step=1, key=f"lito_comp_td_{i}")
                else:
                    tintas_frente, tintas_dorso = preset_val
                    tc2.caption(f"Frente: {tintas_frente} tinta(s) · Dorso: {tintas_dorso} tinta(s)")

                pc1, pc2 = st.columns(2)
                papel_label = pc1.selectbox("Papel", list(opciones_papel.keys()), key=f"lito_comp_papel_{i}")
                maquina_label = pc2.selectbox("Máquina", list(opciones_maquina.keys()), key=f"lito_comp_maquina_{i}")
                papel_sel = db.get_lito_papel(opciones_papel[papel_label])
                maquina_sel = db.get_lito_maquina(opciones_maquina[maquina_label])

                calc = _calcular_componente(
                    formato_ancho, formato_alto, paginas, tintas_frente, tintas_dorso,
                    papel_sel, maquina_sel, cantidad, merma_pct,
                )
                if calc is None:
                    st.error(
                        "El formato de página no cabe en este pliego de papel — elige un papel más "
                        "grande o revisa las medidas."
                    )
                else:
                    st.info(
                        f"📄 {calc['paginas_por_pliego']} páginas por pliego · {calc['num_disenios']} diseño(s) · "
                        f"**{calc['pliegos']} pliegos** · {calc['pasadas']} pasadas · **{calc['planchas']} planchas**  \n"
                        f"Costo — papel: {money(calc['costo_papel'])} · planchas: {money(calc['costo_planchas'])} · "
                        f"máquina: {money(calc['costo_maquina'])} · **Subtotal: {money(calc['costo_total'])}**"
                    )

                componentes_calc.append({
                    "nombre": nombre_comp, "formato_ancho": formato_ancho, "formato_alto": formato_alto,
                    "paginas": paginas, "tintas_frente": tintas_frente, "tintas_dorso": tintas_dorso,
                    "papel_id": papel_sel["id"] if papel_sel else None,
                    "papel_desc": _label_papel(papel_sel) if papel_sel else "—",
                    "maquina_id": maquina_sel["id"] if maquina_sel else None,
                    "maquina_desc": _label_maquina(maquina_sel) if maquina_sel else "—",
                    "calc": calc,
                })

        st.divider()
        st.markdown("#### Acabados adicionales (opcional)")
        st.caption("Costos extra que no son papel/planchas/máquina — ej. encuadernado, laminado, corte.")
        ac1, ac2, _ = st.columns([1, 1, 3])
        if ac1.button("➕ Agregar acabado", use_container_width=True):
            st.session_state["lito_n_acabados"] += 1
            st.rerun()
        if st.session_state["lito_n_acabados"] > 0:
            if ac2.button("➖ Quitar último acabado", use_container_width=True):
                st.session_state["lito_n_acabados"] -= 1
                st.rerun()

        acabados = []
        for j in range(st.session_state["lito_n_acabados"]):
            fa1, fa2 = st.columns([3, 1])
            desc_acabado = fa1.text_input("Descripción", key=f"lito_acabado_desc_{j}", placeholder="Ej. Encuadernado")
            costo_acabado = fa2.number_input("Costo (Q)", min_value=0.0, value=0.0, step=10.0, key=f"lito_acabado_costo_{j}")
            acabados.append({"descripcion": desc_acabado, "costo": costo_acabado})

        st.divider()
        costo_componentes = sum(c["calc"]["costo_total"] for c in componentes_calc if c["calc"])
        costo_acabados = sum(a["costo"] for a in acabados)
        costo_total_trabajo = costo_componentes + costo_acabados
        precio_sugerido = costo_total_trabajo * (1 + margen_pct / 100)
        utilidad = precio_sugerido - costo_total_trabajo

        st.markdown("#### 💵 Resumen")
        r1, r2, r3 = st.columns(3)
        r1.metric("Costo total", money(costo_total_trabajo))
        r2.metric("Precio sugerido", money(precio_sugerido))
        r3.metric("Utilidad", money(utilidad))

        notas = st.text_area("Notas (opcional)", key="lito_notas")
        estado_sel = st.selectbox("Estado", ESTADOS_LITO_COTIZACION, key="lito_estado")

        todos_calculados = all(c["calc"] for c in componentes_calc)
        if not todos_calculados:
            st.caption("⚠️ Corrige los componentes marcados en rojo antes de guardar.")

        if st.button(
            "💾 Guardar cotización", type="primary", use_container_width=True,
            disabled=not (cliente.strip() and todos_calculados),
        ):
            r = db.create_lito_cotizacion(
                cliente=cliente.strip(), nit=nit.strip() or None, descripcion=descripcion.strip() or None,
                cantidad=int(cantidad), merma_pct=merma_pct, margen_pct=margen_pct,
                componentes=componentes_calc, acabados=acabados,
                costo_total=costo_total_trabajo, precio_sugerido=precio_sugerido,
                estado=estado_sel, notas=notas.strip() or None, creado_por=user["nombre"],
            )
            for k in list(st.session_state.keys()):
                if k.startswith("lito_"):
                    del st.session_state[k]
            st.success(f"Cotización LIT-{r['numero']:04d} guardada.")
            st.rerun()

# ---------------------------------------------------------------------------
# Cotizaciones guardadas
# ---------------------------------------------------------------------------
with tab_lista:
    cotizaciones = db.list_lito_cotizaciones()
    filtro_estado = st.multiselect("Filtrar por estado", ESTADOS_LITO_COTIZACION, default=[], key="lito_filtro_estado")
    if filtro_estado:
        cotizaciones = [c for c in cotizaciones if c.get("estado") in filtro_estado]

    if not cotizaciones:
        st.info("No hay cotizaciones técnicas registradas todavía con este filtro.")
    else:
        df = pd.DataFrame([{
            "Número": f"LIT-{c.get('numero', 0):04d}", "Fecha": (c.get("creado_en") or "")[:10],
            "Cliente": c.get("cliente") or "—", "Descripción": c.get("descripcion") or "—",
            "Cantidad": c.get("cantidad") or 0, "Estado": c.get("estado") or "—",
            "Costo total": money(c.get("costo_total")), "Precio sugerido": money(c.get("precio_sugerido")),
            "Creado por": c.get("creado_por") or "—",
        } for c in cotizaciones])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_excel_button(df, "cotizaciones_litografia.xlsx", key="lito_descargar_excel")

        st.divider()
        st.markdown("#### 🔎 Ver detalle, actualizar estado o eliminar")
        opciones_c = {f"LIT-{c.get('numero', 0):04d} — {c.get('cliente') or ''}": c["id"] for c in cotizaciones}
        elegido = st.selectbox("Selecciona una cotización", ["—"] + list(opciones_c.keys()), key="lito_seleccion")
        if elegido != "—":
            cid = opciones_c[elegido]
            cot = db.get_lito_cotizacion(cid)
            if cot:
                st.markdown(f"**Cliente:** {cot.get('cliente') or '—'}  ·  **NIT:** {cot.get('nit') or '—'}")
                st.markdown(f"**Descripción:** {cot.get('descripcion') or '—'}  ·  **Cantidad:** {cot.get('cantidad') or 0}")
                if cot.get("notas"):
                    st.caption(f"📝 {cot['notas']}")

                for comp in cot.get("componentes") or []:
                    calc = comp.get("calc") or {}
                    st.markdown(f"###### {comp.get('nombre') or 'Componente'}")
                    st.caption(
                        f"Formato: {comp.get('formato_ancho')}x{comp.get('formato_alto')}cm · "
                        f"{comp.get('paginas')} páginas · Tintas {comp.get('tintas_frente')}+{comp.get('tintas_dorso')}"
                    )
                    st.caption(f"Papel: {comp.get('papel_desc') or '—'}")
                    st.caption(f"Máquina: {comp.get('maquina_desc') or '—'}")
                    if calc:
                        st.caption(
                            f"{calc.get('pliegos')} pliegos · {calc.get('pasadas')} pasadas · "
                            f"{calc.get('planchas')} planchas · Subtotal: {money(calc.get('costo_total'))}"
                        )
                for ac in cot.get("acabados") or []:
                    if ac.get("descripcion"):
                        st.caption(f"➕ {ac['descripcion']}: {money(ac.get('costo'))}")

                st.markdown(f"**Costo total: {money(cot.get('costo_total'))} · Precio sugerido: {money(cot.get('precio_sugerido'))}**")

                if puede_gestionar:
                    with st.form(f"lito_editar_{cid}"):
                        ge1, ge2 = st.columns(2)
                        estado_ed = ge1.selectbox(
                            "Estado", ESTADOS_LITO_COTIZACION,
                            index=ESTADOS_LITO_COTIZACION.index(cot["estado"]) if cot.get("estado") in ESTADOS_LITO_COTIZACION else 0,
                        )
                        margen_ed = ge2.number_input("% de margen de utilidad", min_value=0.0, value=float(cot.get("margen_pct") or 0), step=5.0)
                        notas_ed = st.text_area("Notas", value=cot.get("notas") or "")
                        st.caption(
                            "Para cambiar papel, máquina, tintas o formato de un componente, lo más simple "
                            "es crear una cotización nueva — esto solo actualiza estado, margen y notas."
                        )
                        if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
                            costo_total = float(cot.get("costo_total") or 0)
                            precio_sugerido_ed = costo_total * (1 + margen_ed / 100)
                            db.update_lito_cotizacion(
                                cid, estado=estado_ed, margen_pct=margen_ed, notas=notas_ed.strip() or None,
                                precio_sugerido=precio_sugerido_ed,
                            )
                            st.success("Cotización actualizada.")
                            st.rerun()

                    with st.expander("🗑️ Eliminar esta cotización"):
                        confirmar_borrar = st.checkbox("Confirmo que quiero eliminar esta cotización", key=f"lito_conf_del_{cid}")
                        if st.button("Eliminar cotización", key=f"lito_btn_del_{cid}", disabled=not confirmar_borrar):
                            db.delete_lito_cotizacion(cid)
                            st.success("Cotización eliminada.")
                            st.rerun()

# ---------------------------------------------------------------------------
# Catálogo de máquinas
# ---------------------------------------------------------------------------
with tab_maquinas:
    st.caption(
        "Máquinas de impresión disponibles, con el tamaño máximo de pliego que aceptan y sus "
        "costos — usados por el cotizador para calcular pliegos, planchas y costo de máquina."
    )
    maquinas_todas = db.list_lito_maquinas(solo_activos=False)
    if maquinas_todas:
        df_m = pd.DataFrame([{
            "Nombre": m["nombre"], "Tamaño máx.": f"{m.get('ancho_max', 0):.0f}x{m.get('alto_max', 0):.0f}cm",
            "Costo por millar de pasadas": money(m.get("costo_millar_pasadas")),
            "Costo por plancha": money(m.get("costo_plancha")),
            "Activa": "Sí" if m.get("activo", True) else "No",
        } for m in maquinas_todas])
        st.dataframe(df_m, use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay máquinas registradas.")

    if puede_admin_catalogos:
        with st.expander("➕ Agregar máquina"):
            with st.form("lito_nueva_maquina", clear_on_submit=True):
                nm1, nm2 = st.columns(2)
                nombre_m = nm1.text_input("Nombre")
                nm_a1, nm_a2 = nm2.columns(2)
                ancho_max_m = nm_a1.number_input("Ancho máx. (cm)", min_value=0.1, value=65.0, step=1.0)
                alto_max_m = nm_a2.number_input("Alto máx. (cm)", min_value=0.1, value=90.0, step=1.0)
                nm3, nm4 = st.columns(2)
                costo_millar_m = nm3.number_input("Costo por millar de pasadas (Q)", min_value=0.0, value=300.0, step=10.0)
                costo_plancha_m = nm4.number_input("Costo por plancha (Q)", min_value=0.0, value=40.0, step=5.0)
                if st.form_submit_button("Guardar máquina", use_container_width=True):
                    if not nombre_m.strip():
                        st.error("El nombre es obligatorio.")
                    else:
                        db.create_lito_maquina(nombre_m, ancho_max_m, alto_max_m, costo_millar_m, costo_plancha_m)
                        st.success("Máquina agregada.")
                        st.rerun()

        if maquinas_todas:
            st.markdown("#### ✏️ Editar o desactivar una máquina")
            opciones_m = {m["nombre"]: m["id"] for m in maquinas_todas}
            elegido_m = st.selectbox("Selecciona una máquina", ["—"] + list(opciones_m.keys()), key="lito_mq_sel")
            if elegido_m != "—":
                mid = opciones_m[elegido_m]
                mq = db.get_lito_maquina(mid)
                with st.form(f"lito_editar_maquina_{mid}"):
                    em1, em2 = st.columns(2)
                    nombre_ed = em1.text_input("Nombre", value=mq.get("nombre") or "")
                    activo_ed = em2.checkbox("Activa", value=mq.get("activo", True))
                    ea1, ea2 = st.columns(2)
                    ancho_ed = ea1.number_input("Ancho máx. (cm)", min_value=0.1, value=float(mq.get("ancho_max") or 1))
                    alto_ed = ea2.number_input("Alto máx. (cm)", min_value=0.1, value=float(mq.get("alto_max") or 1))
                    ec1, ec2 = st.columns(2)
                    costo_millar_ed = ec1.number_input("Costo por millar de pasadas (Q)", min_value=0.0, value=float(mq.get("costo_millar_pasadas") or 0))
                    costo_plancha_ed = ec2.number_input("Costo por plancha (Q)", min_value=0.0, value=float(mq.get("costo_plancha") or 0))
                    if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
                        db.update_lito_maquina(
                            mid, nombre=nombre_ed.strip(), activo=activo_ed,
                            ancho_max=ancho_ed, alto_max=alto_ed,
                            costo_millar_pasadas=costo_millar_ed, costo_plancha=costo_plancha_ed,
                        )
                        st.success("Máquina actualizada.")
                        st.rerun()

# ---------------------------------------------------------------------------
# Catálogo de papel
# ---------------------------------------------------------------------------
with tab_papel:
    st.caption(
        "Tipos de papel disponibles, con las medidas del pliego, el gramaje y el costo por "
        "pliego — usados por el cotizador para calcular cuántas páginas caben y el costo de papel."
    )
    papeles_todos = db.list_lito_papeles(solo_activos=False)
    if papeles_todos:
        df_p = pd.DataFrame([{
            "Tipo": p["tipo"], "Fabricante": p.get("fabricante") or "—",
            "Gramaje": f"{p.get('gramaje', 0):.0f} g/m²",
            "Medidas del pliego": f"{p.get('ancho', 0):.0f}x{p.get('alto', 0):.0f}cm",
            "Costo por pliego": money(p.get("costo_pliego")),
            "Activo": "Sí" if p.get("activo", True) else "No",
        } for p in papeles_todos])
        st.dataframe(df_p, use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay tipos de papel registrados.")

    if puede_admin_catalogos:
        with st.expander("➕ Agregar tipo de papel"):
            with st.form("lito_nuevo_papel", clear_on_submit=True):
                np1, np2 = st.columns(2)
                tipo_p = np1.text_input("Tipo", placeholder="Ej. Couché brillante")
                fabricante_p = np2.text_input("Fabricante", placeholder="Ej. Stora Enso")
                np3, np4, np5 = st.columns(3)
                gramaje_p = np3.number_input("Gramaje (g/m²)", min_value=1.0, value=80.0, step=5.0)
                ancho_p = np4.number_input("Ancho del pliego (cm)", min_value=0.1, value=65.0, step=1.0)
                alto_p = np5.number_input("Alto del pliego (cm)", min_value=0.1, value=90.0, step=1.0)
                costo_p = st.number_input("Costo por pliego (Q)", min_value=0.0, value=1.5, step=0.1)
                if st.form_submit_button("Guardar papel", use_container_width=True):
                    if not tipo_p.strip():
                        st.error("El tipo de papel es obligatorio.")
                    else:
                        db.create_lito_papel(tipo_p, fabricante_p, gramaje_p, ancho_p, alto_p, costo_p)
                        st.success("Papel agregado.")
                        st.rerun()

        if papeles_todos:
            st.markdown("#### ✏️ Editar o desactivar un tipo de papel")
            opciones_p = {f"{p['tipo']} — {p.get('fabricante') or ''}": p["id"] for p in papeles_todos}
            elegido_p = st.selectbox("Selecciona un papel", ["—"] + list(opciones_p.keys()), key="lito_pp_sel")
            if elegido_p != "—":
                pid = opciones_p[elegido_p]
                pp = db.get_lito_papel(pid)
                with st.form(f"lito_editar_papel_{pid}"):
                    ep1, ep2 = st.columns(2)
                    tipo_ed = ep1.text_input("Tipo", value=pp.get("tipo") or "")
                    fabricante_ed = ep2.text_input("Fabricante", value=pp.get("fabricante") or "")
                    ep3, ep4, ep5 = st.columns(3)
                    gramaje_ed = ep3.number_input("Gramaje (g/m²)", min_value=1.0, value=float(pp.get("gramaje") or 1))
                    ancho_ed = ep4.number_input("Ancho del pliego (cm)", min_value=0.1, value=float(pp.get("ancho") or 1))
                    alto_ed = ep5.number_input("Alto del pliego (cm)", min_value=0.1, value=float(pp.get("alto") or 1))
                    ep6, ep7 = st.columns(2)
                    costo_ed = ep6.number_input("Costo por pliego (Q)", min_value=0.0, value=float(pp.get("costo_pliego") or 0))
                    activo_ed = ep7.checkbox("Activo", value=pp.get("activo", True))
                    if st.form_submit_button("💾 Guardar cambios", use_container_width=True):
                        db.update_lito_papel(
                            pid, tipo=tipo_ed.strip(), fabricante=fabricante_ed.strip(),
                            gramaje=gramaje_ed, ancho=ancho_ed, alto=alto_ed,
                            costo_pliego=costo_ed, activo=activo_ed,
                        )
                        st.success("Papel actualizado.")
                        st.rerun()
