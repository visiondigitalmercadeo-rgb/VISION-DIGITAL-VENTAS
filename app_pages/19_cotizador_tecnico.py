"""Cotizador Técnico: ficha de cotización de un trabajo de impresión (offset o
similar) con cálculo automático de pliegos, planchas, pasadas de máquina y
costo total — a partir del catálogo de máquinas y papel que carga el propio
Steven (empieza VACÍO a propósito, sin datos de ejemplo).

Inspirado en cómo un MIS de impresión (ej. Optimus) resuelve la estimación de
un trabajo: reglas de cálculo a partir de la configuración de máquina,
formato de hoja, papel y procesos de acabado — pero construido a la medida
de Visión Digital, no es código de ningún proveedor externo.

Cálculo (simplificado, documentado aquí para que se pueda auditar):
  - piezas_por_pliego: cuántas piezas del tamaño final caben en el pliego de
    papel elegido (se prueban las dos orientaciones, como se haría a mano).
  - pliegos_necesarios = ceil(cantidad x (1 + merma%) / piezas_por_pliego).
  - costo_papel = pliegos_necesarios x costo_pliego del papel elegido.
  - planchas_necesarias = tintas_frente + tintas_dorso (una plancha por
    color por lado) x costo_plancha de la máquina elegida.
  - pasadas_maquina = pliegos_necesarios x (tintas_frente + tintas_dorso);
    costo_pasadas = (pasadas_maquina / 1000) x costo_millar_pasadas.
  - costo_total = costo_papel + costo_planchas + costo_pasadas + acabados.
  - precio_venta = costo_total x (1 + margen% / 100) — mismo criterio de
    margen (markup sobre costo) que el Cotizador Digital.

El catálogo de máquinas y papel (con los costos reales) se carga desde la
pestaña "⚙️ Catálogo" — a mano o en bloque con la plantilla de Excel
(ver utils.plantilla_catalogo_tecnico_bytes / db.bulk_upsert_tecnico_maquinas
/ bulk_upsert_tecnico_papeles).
"""

import math

import pandas as pd
import streamlit as st

import auth
import database as db
from config import TECNICO_TINTAS_PRESETS
from utils import download_excel_button, money, plantilla_catalogo_tecnico_bytes, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🖨️ Cotizador Técnico")
st.caption(
    "Cotiza un trabajo de impresión con cálculo automático de pliegos, planchas y costo, a partir "
    "de tu catálogo de máquinas y papel."
)

puede_gestionar = auth.puede_gestionar_tecnico()
puede_admin_catalogo = auth.puede_administrar_catalogo_tecnico()

MARGEN_DEFECTO = 35.0
ESCRIBIR_CLIENTE_NUEVO = "✍️ Escribir un cliente nuevo"


def _piezas_por_pliego(pieza_w, pieza_h, pliego_w, pliego_h):
    def caben(a, b):
        if a <= 0 or b <= 0:
            return 0
        return math.floor(pliego_w / a) * math.floor(pliego_h / b)
    return max(caben(pieza_w, pieza_h), caben(pieza_h, pieza_w))


def _con_margen(costo_total, margen_pct, cantidad):
    precio_venta = costo_total * (1 + margen_pct / 100)
    utilidad = precio_venta - costo_total
    margen_real_pct = (utilidad / precio_venta * 100) if precio_venta else 0.0
    return {
        "costo_total": costo_total, "margen_pct": margen_pct, "precio_venta": precio_venta,
        "utilidad": utilidad, "margen_real_pct": margen_real_pct,
        "precio_unitario": precio_venta / cantidad if cantidad else 0.0,
    }


def _calcular(maquina, papel, pieza_w, pieza_h, cantidad, tintas_frente, tintas_dorso, merma_pct,
              costo_acabados, margen_pct):
    piezas = _piezas_por_pliego(pieza_w, pieza_h, papel["ancho"], papel["alto"])
    if piezas <= 0:
        return None
    pliegos = math.ceil(cantidad * (1 + merma_pct / 100) / piezas)
    costo_papel = pliegos * papel["costo_pliego"]
    planchas = tintas_frente + tintas_dorso
    costo_planchas = planchas * maquina["costo_plancha"]
    pasadas = pliegos * planchas
    costo_pasadas = (pasadas / 1000) * maquina["costo_millar_pasadas"]
    costo_total = costo_papel + costo_planchas + costo_pasadas + (costo_acabados or 0.0)
    return {
        "piezas_por_pliego": piezas, "pliegos": pliegos, "planchas": planchas, "pasadas": pasadas,
        "costo_papel": costo_papel, "costo_planchas": costo_planchas, "costo_pasadas": costo_pasadas,
        "costo_acabados": costo_acabados or 0.0,
        **_con_margen(costo_total, margen_pct, cantidad),
    }


if puede_admin_catalogo:
    tab_nueva, tab_lista, tab_catalogo = st.tabs(["🧾 Nueva cotización", "📋 Cotizaciones guardadas", "⚙️ Catálogo"])
else:
    tab_nueva, tab_lista = st.tabs(["🧾 Nueva cotización", "📋 Cotizaciones guardadas"])
    tab_catalogo = None

# ---------------------------------------------------------------------------
# Nueva cotización
# ---------------------------------------------------------------------------
with tab_nueva:
    if not puede_gestionar:
        st.info("Tu rol es de solo vista y no puede generar cotizaciones aquí.")
    else:
        maquinas = db.list_tecnico_maquinas()
        papeles = db.list_tecnico_papeles()
        if not maquinas or not papeles:
            st.warning(
                "Todavía no has cargado tu catálogo de máquinas y/o papel — sin eso el sistema no "
                "puede calcular el costo. Ve a la pestaña '⚙️ Catálogo' para cargarlo (uno por uno o "
                "en bloque con la plantilla de Excel)."
                if puede_admin_catalogo else
                "Todavía no hay máquinas y/o papel cargados en el catálogo. Pídele a un administrador "
                "que los cargue en '⚙️ Catálogo'."
            )
            if puede_admin_catalogo:
                st.download_button(
                    "⬇️ Descargar plantilla de Excel para carga masiva",
                    data=plantilla_catalogo_tecnico_bytes(), file_name="Plantilla_Carga_Cotizador_Tecnico.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="tec_descargar_plantilla_aviso",
                )
        else:
            if user["rol"] == "admin":
                vendedores = db.list_vendedores()
                opciones_v = {v["nombre"]: v["id"] for v in vendedores}
                if not opciones_v:
                    st.warning("No hay vendedores registrados todavía.")
                    st.stop()
                vendedor_nombre = st.selectbox("Vendedor", list(opciones_v.keys()), key="tec_vendedor")
                vendedor_id = opciones_v[vendedor_nombre]
            else:
                vendedor_id = user["id"]
                st.caption(f"Vendedor: **{user['nombre']}**")

            prospectos = db.list_prospectos(vendedor_id)
            opciones_p = {p["nombre_cliente"]: p["id"] for p in prospectos}
            opciones_cliente = [ESCRIBIR_CLIENTE_NUEVO] + list(opciones_p.keys())
            cliente_sel = st.selectbox("Cliente", opciones_cliente, key="tec_cliente_sel")
            if cliente_sel == ESCRIBIR_CLIENTE_NUEVO:
                nombre_cliente_nuevo = st.text_input(
                    "Nombre del cliente", key="tec_cliente_nuevo", placeholder="Ej. Banco Industrial",
                )
                prospecto_id = None
            else:
                nombre_cliente_nuevo = None
                prospecto_id = opciones_p[cliente_sel]

            nombre_producto = st.text_input(
                "Nombre / descripción del trabajo", key="tec_nombre_producto",
                placeholder="Ej. Catálogo 32 páginas — Banco Industrial",
            )

            st.divider()
            c1, c2 = st.columns(2)
            opciones_maquina = {m["nombre"]: m for m in maquinas}
            maquina_sel = c1.selectbox("Máquina", list(opciones_maquina.keys()), key="tec_maquina")
            maquina = opciones_maquina[maquina_sel]
            opciones_papel = {
                f"{p['tipo']} — {p['fabricante']} ({p['gramaje']:.0f} g/m², {p['ancho']:.0f}x{p['alto']:.0f} cm)": p
                for p in papeles
            }
            papel_sel = c2.selectbox("Papel", list(opciones_papel.keys()), key="tec_papel")
            papel = opciones_papel[papel_sel]

            if papel["ancho"] > maquina["ancho_max"] or papel["alto"] > maquina["alto_max"]:
                st.error(
                    f"El pliego de este papel ({papel['ancho']:.0f}x{papel['alto']:.0f} cm) no cabe en "
                    f"la máquina elegida (máximo {maquina['ancho_max']:.0f}x{maquina['alto_max']:.0f} cm)."
                )

            c3, c4, c5 = st.columns(3)
            pieza_w = c3.number_input("Tamaño final — ancho (cm)", min_value=0.1, value=21.0, step=0.5, key="tec_ancho")
            pieza_h = c4.number_input("Tamaño final — alto (cm)", min_value=0.1, value=29.7, step=0.5, key="tec_alto")
            cantidad = c5.number_input("Cantidad", min_value=1, value=500, step=1, key="tec_cantidad")

            c6, c7 = st.columns(2)
            preset_tintas = c6.selectbox("Tintas", list(TECNICO_TINTAS_PRESETS.keys()), key="tec_tintas_preset")
            if TECNICO_TINTAS_PRESETS[preset_tintas] is None:
                cc1, cc2 = c7.columns(2)
                tintas_frente = cc1.number_input("Tintas frente", min_value=0, value=4, step=1, key="tec_tf")
                tintas_dorso = cc2.number_input("Tintas dorso", min_value=0, value=0, step=1, key="tec_td")
            else:
                tintas_frente, tintas_dorso = TECNICO_TINTAS_PRESETS[preset_tintas]
                c7.caption(f"Frente: {tintas_frente} tinta(s) · Dorso: {tintas_dorso} tinta(s)")

            c8, c9 = st.columns(2)
            merma_pct = c8.number_input("Merma de producción (%)", min_value=0.0, value=5.0, step=1.0, key="tec_merma")
            margen_pct = c9.number_input("Margen de utilidad (%)", min_value=0.0, value=MARGEN_DEFECTO, step=1.0, key="tec_margen")

            c10, c11 = st.columns(2)
            acabados_desc = c10.text_input(
                "Acabados (opcional)", key="tec_acabados_desc",
                placeholder="Ej. Laminado mate, troquelado, engrapado",
            )
            costo_acabados = c11.number_input("Costo de acabados (Q, opcional)", min_value=0.0, value=0.0, step=10.0, key="tec_acabados_costo")

            notas = st.text_area("Notas de producción (opcional)", key="tec_notas")

            resultado = None
            if papel["ancho"] <= maquina["ancho_max"] and papel["alto"] <= maquina["alto_max"]:
                resultado = _calcular(
                    maquina, papel, pieza_w, pieza_h, cantidad, tintas_frente, tintas_dorso,
                    merma_pct, costo_acabados, margen_pct,
                )
                if resultado is None:
                    st.error("La pieza no cabe en el pliego de este papel con esas medidas — revisa el tamaño.")
                else:
                    st.info(
                        f"📐 {resultado['piezas_por_pliego']} pieza(s) por pliego · **{resultado['pliegos']} pliegos** "
                        f"necesarios · {resultado['planchas']} plancha(s) · {resultado['pasadas']} pasada(s) de máquina.  \n"
                        f"Papel: {money(resultado['costo_papel'])} · Planchas: {money(resultado['costo_planchas'])} · "
                        f"Pasadas: {money(resultado['costo_pasadas'])} · Acabados: {money(resultado['costo_acabados'])}  \n"
                        f"**Costo total: {money(resultado['costo_total'])}**"
                    )
                    st.success(
                        f"Margen: **{resultado['margen_pct']:.0f}%** · Utilidad: {money(resultado['utilidad'])} "
                        f"(margen real {resultado['margen_real_pct']:.1f}%)  \n"
                        f"**Precio de venta: {money(resultado['precio_venta'])} · Precio unitario: "
                        f"{money(resultado['precio_unitario'])}**"
                    )

            falta_cliente = prospecto_id is None and not (nombre_cliente_nuevo or "").strip()
            if st.button(
                "💾 Generar cotización", type="primary", use_container_width=True,
                disabled=resultado is None or not nombre_producto.strip() or falta_cliente,
            ):
                prospecto_id_final = prospecto_id
                if prospecto_id_final is None:
                    nombre_final = nombre_cliente_nuevo.strip()
                    existente = next(
                        (p for p in prospectos if (p.get("nombre_cliente") or "").strip().lower() == nombre_final.lower()),
                        None,
                    )
                    if existente:
                        prospecto_id_final = existente["id"]
                    else:
                        prospecto_id_final = db.create_prospecto(
                            nombre_cliente=nombre_final, telefono="", email="", direccion="",
                            vendedor_id=vendedor_id, fecha_seguimiento=None, recordatorio="",
                            notas="Creado automáticamente desde Cotizador Técnico.",
                            estado="Prospecto", productos=[],
                        )

                r = db.create_tecnico_cotizacion(
                    prospecto_id=prospecto_id_final, vendedor_id=vendedor_id,
                    nombre_producto=nombre_producto.strip(),
                    maquina_id=maquina["id"], maquina_nombre=maquina["nombre"],
                    papel_id=papel["id"], papel_nombre=f"{papel['tipo']} — {papel['fabricante']}",
                    ancho_pieza=pieza_w, alto_pieza=pieza_h, cantidad=cantidad,
                    tintas_frente=tintas_frente, tintas_dorso=tintas_dorso, merma_pct=merma_pct,
                    acabados_descripcion=acabados_desc.strip() or None,
                    resultado=resultado, estado="Cotizado", notas=notas.strip() or None,
                    creado_por=user["nombre"],
                )
                for k in list(st.session_state.keys()):
                    if k.startswith("tec_"):
                        del st.session_state[k]
                st.success(f"Cotización TEC-{r['numero']:04d} generada correctamente.")
                st.rerun()

# ---------------------------------------------------------------------------
# Cotizaciones guardadas
# ---------------------------------------------------------------------------
with tab_lista:
    cotizaciones = db.list_tecnico_cotizaciones()
    if user["rol"] not in ("admin", "vista"):
        cotizaciones = [c for c in cotizaciones if c.get("vendedor_id") == user["id"]]

    if not cotizaciones:
        st.info("No hay cotizaciones del Cotizador Técnico registradas todavía.")
    else:
        resultados = [c.get("resultado") or {} for c in cotizaciones]
        utilidad_total = sum(r.get("utilidad") or 0 for r in resultados)
        ventas_total = sum(r.get("precio_venta") or 0 for r in resultados)
        margen_prom = (utilidad_total / ventas_total * 100) if ventas_total else 0.0

        st.markdown("#### 📊 KPIs")
        k1, k2, k3 = st.columns(3)
        k1.metric("Cotizaciones generadas", len(cotizaciones))
        k2.metric("Utilidad total", money(utilidad_total))
        k3.metric("Margen real promedio", f"{margen_prom:.1f}%")

        vendedores_map = {v["id"]: v["nombre"] for v in db.list_usuarios()}
        df = pd.DataFrame([{
            "Número": f"TEC-{c.get('numero', 0):04d}", "Fecha": (c.get("creado_en") or "")[:10],
            "Cliente": db.get_prospecto(c.get("prospecto_id"))["nombre_cliente"] if c.get("prospecto_id") and db.get_prospecto(c.get("prospecto_id")) else "—",
            "Trabajo": c.get("nombre_producto") or "—",
            "Máquina": c.get("maquina_nombre") or "—", "Papel": c.get("papel_nombre") or "—",
            "Cantidad": c.get("cantidad") or 0,
            "Costo": money((c.get("resultado") or {}).get("costo_total")),
            "Precio de venta": money((c.get("resultado") or {}).get("precio_venta")),
            "Utilidad": money((c.get("resultado") or {}).get("utilidad")),
            "Margen %": f"{(c.get('resultado') or {}).get('margen_real_pct', 0):.1f}%",
            "Vendedor": vendedores_map.get(c.get("vendedor_id"), "—"),
        } for c in cotizaciones])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_excel_button(df, "cotizador_tecnico.xlsx", key="tec_descargar_excel")

        st.divider()
        st.markdown("#### 🔎 Ver detalle")
        opciones_c = {f"TEC-{c.get('numero', 0):04d} — {c.get('nombre_producto') or ''}": c["id"] for c in cotizaciones}
        elegido = st.selectbox("Selecciona una cotización", ["—"] + list(opciones_c.keys()), key="tec_seleccion")
        if elegido != "—":
            cid = opciones_c[elegido]
            cot = db.get_tecnico_cotizacion(cid)
            if cot:
                prospecto = db.get_prospecto(cot.get("prospecto_id"))
                resultado_cot = cot.get("resultado") or {}
                st.markdown(f"**Cliente:** {prospecto['nombre_cliente'] if prospecto else '—'}")
                st.markdown(f"**Trabajo:** {cot.get('nombre_producto') or '—'}")
                st.caption(
                    f"Máquina: {cot.get('maquina_nombre') or '—'} · Papel: {cot.get('papel_nombre') or '—'} · "
                    f"Tamaño: {cot.get('ancho_pieza')}x{cot.get('alto_pieza')} cm · Cantidad: {cot.get('cantidad') or '—'} · "
                    f"Tintas: {cot.get('tintas_frente', 0)}+{cot.get('tintas_dorso', 0)}"
                )
                if cot.get("acabados_descripcion"):
                    st.caption(f"Acabados: {cot['acabados_descripcion']}")
                if cot.get("notas"):
                    st.caption(f"📝 {cot['notas']}")
                st.markdown(
                    f"**Costo: {money(resultado_cot.get('costo_total'))} · Margen: {resultado_cot.get('margen_pct', 0):.0f}% "
                    f"· Utilidad: {money(resultado_cot.get('utilidad'))} (margen real {resultado_cot.get('margen_real_pct', 0):.1f}%)**"
                )
                st.markdown(
                    f"**Precio de venta: {money(resultado_cot.get('precio_venta'))} · Precio unitario: "
                    f"{money(resultado_cot.get('precio_unitario'))}**"
                )

                if puede_gestionar:
                    with st.expander("🗑️ Eliminar esta cotización"):
                        confirmar_borrar = st.checkbox("Confirmo que quiero eliminar esta cotización", key=f"tec_conf_del_{cid}")
                        if st.button("Eliminar cotización", key=f"tec_btn_del_{cid}", disabled=not confirmar_borrar):
                            db.delete_tecnico_cotizacion(cid)
                            st.success("Cotización eliminada.")
                            st.rerun()

# ---------------------------------------------------------------------------
# Catálogo (solo admin)
# ---------------------------------------------------------------------------
if tab_catalogo is not None:
    with tab_catalogo:
        st.caption(
            "Aquí cargas los costos reales que usa el cálculo automático. Puedes agregar uno por uno, "
            "o cargar todo de una vez con la plantilla de Excel."
        )
        st.download_button(
            "⬇️ Descargar plantilla de Excel para carga masiva",
            data=plantilla_catalogo_tecnico_bytes(), file_name="Plantilla_Carga_Cotizador_Tecnico.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="tec_descargar_plantilla",
        )

        with st.expander("📤 Carga masiva desde Excel (usa la plantilla de arriba)"):
            archivo = st.file_uploader(
                "Sube tu Excel con las hojas 'Máquinas' y 'Papel'", type=["xlsx"], key="tec_upload_catalogo",
            )
            if archivo is not None and st.button("Cargar catálogo", key="tec_btn_cargar_catalogo"):
                try:
                    creadas_m = actualizadas_m = creados_p = actualizados_p = 0
                    try:
                        df_maq = pd.read_excel(archivo, sheet_name="Máquinas")
                        filas_maq = [{
                            "nombre": row.get("Nombre de la máquina"),
                            "ancho_max": row.get("Ancho máximo del pliego (cm)"),
                            "alto_max": row.get("Alto máximo del pliego (cm)"),
                            "costo_millar_pasadas": row.get("Costo por millar de pasadas (Q)"),
                            "costo_plancha": row.get("Costo por plancha (Q)"),
                        } for _, row in df_maq.iterrows() if pd.notna(row.get("Nombre de la máquina"))]
                        creadas_m, actualizadas_m = db.bulk_upsert_tecnico_maquinas(filas_maq)
                    except ValueError:
                        st.warning("No se encontró la hoja 'Máquinas' en el archivo — se omitió esa parte.")

                    try:
                        df_pap = pd.read_excel(archivo, sheet_name="Papel")
                        filas_pap = [{
                            "tipo": row.get("Tipo de papel"), "fabricante": row.get("Fabricante"),
                            "gramaje": row.get("Gramaje (g/m²)"), "ancho": row.get("Ancho del pliego (cm)"),
                            "alto": row.get("Alto del pliego (cm)"), "costo_pliego": row.get("Costo por pliego (Q)"),
                        } for _, row in df_pap.iterrows() if pd.notna(row.get("Tipo de papel"))]
                        creados_p, actualizados_p = db.bulk_upsert_tecnico_papeles(filas_pap)
                    except ValueError:
                        st.warning("No se encontró la hoja 'Papel' en el archivo — se omitió esa parte.")

                    st.success(
                        f"Máquinas: {creadas_m} nueva(s), {actualizadas_m} actualizada(s). "
                        f"Papel: {creados_p} nuevo(s), {actualizados_p} actualizado(s)."
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo leer el archivo — revisa que sea el formato de la plantilla. Detalle: {e}")

        st.divider()
        col_maq, col_pap = st.columns(2)

        with col_maq:
            st.markdown("#### 🖨️ Máquinas")
            maquinas_cat = db.list_tecnico_maquinas(solo_activos=False)
            if maquinas_cat:
                df_maq_cat = pd.DataFrame([{
                    "Nombre": m["nombre"], "Ancho máx (cm)": m["ancho_max"], "Alto máx (cm)": m["alto_max"],
                    "Costo/millar pasadas (Q)": m["costo_millar_pasadas"], "Costo plancha (Q)": m["costo_plancha"],
                    "Activa": "Sí" if m.get("activo", True) else "No",
                } for m in maquinas_cat])
                st.dataframe(df_maq_cat, use_container_width=True, hide_index=True)
            else:
                st.caption("Todavía no hay máquinas cargadas.")

            with st.expander("➕ Agregar máquina manualmente"):
                with st.form("tec_form_nueva_maquina", clear_on_submit=True):
                    nombre_m = st.text_input("Nombre de la máquina")
                    cc1, cc2 = st.columns(2)
                    ancho_max = cc1.number_input("Ancho máximo del pliego (cm)", min_value=0.1, value=65.0, step=1.0)
                    alto_max = cc2.number_input("Alto máximo del pliego (cm)", min_value=0.1, value=90.0, step=1.0)
                    cc3, cc4 = st.columns(2)
                    costo_pasadas_m = cc3.number_input("Costo por millar de pasadas (Q)", min_value=0.0, value=0.0, step=10.0)
                    costo_plancha_m = cc4.number_input("Costo por plancha (Q)", min_value=0.0, value=0.0, step=1.0)
                    if st.form_submit_button("Agregar máquina", use_container_width=True):
                        if not nombre_m.strip():
                            st.error("Ponle un nombre a la máquina.")
                        else:
                            db.create_tecnico_maquina(nombre_m, ancho_max, alto_max, costo_pasadas_m, costo_plancha_m)
                            st.success("Máquina agregada.")
                            st.rerun()

            if maquinas_cat:
                with st.expander("🚫 Activar / desactivar una máquina"):
                    opciones_m = {m["nombre"]: m for m in maquinas_cat}
                    elegido_m = st.selectbox("Máquina", list(opciones_m.keys()), key="tec_maquina_toggle")
                    m_sel = opciones_m[elegido_m]
                    nuevo_activo_m = st.toggle("Activa (visible al cotizar)", value=bool(m_sel.get("activo", True)), key="tec_maquina_toggle_val")
                    if nuevo_activo_m != bool(m_sel.get("activo", True)):
                        db.update_tecnico_maquina(m_sel["id"], activo=nuevo_activo_m)
                        st.success("Actualizado.")
                        st.rerun()

        with col_pap:
            st.markdown("#### 📄 Papel")
            papeles_cat = db.list_tecnico_papeles(solo_activos=False)
            if papeles_cat:
                df_pap_cat = pd.DataFrame([{
                    "Tipo": p["tipo"], "Fabricante": p["fabricante"], "Gramaje (g/m²)": p["gramaje"],
                    "Ancho (cm)": p["ancho"], "Alto (cm)": p["alto"], "Costo/pliego (Q)": p["costo_pliego"],
                    "Activo": "Sí" if p.get("activo", True) else "No",
                } for p in papeles_cat])
                st.dataframe(df_pap_cat, use_container_width=True, hide_index=True)
            else:
                st.caption("Todavía no hay papel cargado.")

            with st.expander("➕ Agregar papel manualmente"):
                with st.form("tec_form_nuevo_papel", clear_on_submit=True):
                    tipo_p = st.text_input("Tipo de papel", placeholder="Ej. Couché brillante")
                    fabricante_p = st.text_input("Fabricante", placeholder="Ej. Genérico")
                    cc5, cc6 = st.columns(2)
                    gramaje_p = cc5.number_input("Gramaje (g/m²)", min_value=1.0, value=115.0, step=1.0)
                    cc7, cc8 = st.columns(2)
                    ancho_p = cc7.number_input("Ancho del pliego (cm)", min_value=0.1, value=65.0, step=1.0)
                    alto_p = cc8.number_input("Alto del pliego (cm)", min_value=0.1, value=90.0, step=1.0)
                    costo_pliego_p = cc6.number_input("Costo por pliego (Q)", min_value=0.0, value=0.0, step=0.10)
                    if st.form_submit_button("Agregar papel", use_container_width=True):
                        if not tipo_p.strip():
                            st.error("Ponle un tipo de papel.")
                        else:
                            db.create_tecnico_papel(tipo_p, fabricante_p, gramaje_p, ancho_p, alto_p, costo_pliego_p)
                            st.success("Papel agregado.")
                            st.rerun()

            if papeles_cat:
                with st.expander("🚫 Activar / desactivar un papel"):
                    opciones_p_cat = {f"{p['tipo']} — {p['fabricante']} ({p['gramaje']:.0f} g/m²)": p for p in papeles_cat}
                    elegido_p = st.selectbox("Papel", list(opciones_p_cat.keys()), key="tec_papel_toggle")
                    p_sel = opciones_p_cat[elegido_p]
                    nuevo_activo_p = st.toggle("Activo (visible al cotizar)", value=bool(p_sel.get("activo", True)), key="tec_papel_toggle_val")
                    if nuevo_activo_p != bool(p_sel.get("activo", True)):
                        db.update_tecnico_papel(p_sel["id"], activo=nuevo_activo_p)
                        st.success("Actualizado.")
                        st.rerun()
