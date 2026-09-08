"""Cotizador Digital: convierte el catálogo de precios de Visión Digital (LPM
Digital) en un formulario que el vendedor llena para generar una cotización
—inspirado en la ficha de pedido "B01" que se llenaba a mano— y calcula el
precio automáticamente, con un PDF de la cotización listo para descargar y
enviar al cliente.

Dos tipos de trabajo, porque el catálogo original tiene dos formas de cobrar
muy distintas:
  - "Impresión en pliego": tarjetas, stickers, adhesivos, empaques, etc. Se
    imprime un pliego completo del material elegido y se corta a la medida
    final del producto — el cálculo es cuántas piezas caben por pliego (en
    las dos orientaciones, como se haría a mano), cuántos pliegos hacen
    falta para la cantidad pedida, y el COSTO de cada pliego (impresión +
    laminado/foil/troquel si aplican) + una "ventaja" de merma de producción
    + envío.
  - "Papel bond / inkjet": formularios, manuales, hojas sueltas — el precio
    ya es por hoja al tamaño final, sin necesidad de calcular pliegos.

Margen de utilidad: el catálogo LPM (columnas "VENTA... C/IVA") se trata como
la base de COSTO del cotizador, no como el precio final al cliente. Sobre ese
costo se aplica un % de margen de utilidad, configurable por tarifa desde la
pestaña "⚙️ Márgenes" (solo admin) sin tocar código — ver
db.get_margenes_cotizador_digital / set_margenes_cotizador_digital y el valor
de fábrica en pricing_data.MARGENES_INICIAL. "Papel bond / inkjet" no tiene
tarifas LPM, así que usa el margen de la tarifa "normal".

Los precios NO se leen de un Excel en vivo: están cargados como datos fijos
en pricing_data.py (a partir del Excel "LPM_DIGITAL_ABRIL2025" que compartió
Steven), para que la cotización funcione igual en Streamlit Cloud. Si el
priciario cambia, hay que actualizar ese archivo.

Al generar una cotización aquí, además de guardarse en este cotizador
también se crea automáticamente una fila en la pestaña "Cotizaciones" (con
el mismo monto de VENTA y cliente), para no duplicar el trabajo de registro
— ver db.create_cotizacion_digital. El desglose de costo/margen/utilidad es
información interna: NO aparece en el PDF que se descarga para el cliente
(ver utils.cotizador_digital_pdf_bytes), solo el precio de venta final.
"""

import math

import pandas as pd
import streamlit as st

import auth
import database as db
from pricing_data import (
    MARGEN_CORTE_PULGADAS,
    PAPEL_BOND_INKJET,
    TARIFA_LABEL,
    TARIFAS_DIGITAL,
    VENTAJA_FACTOR,
    MATERIALES_DIGITAL,
)
from utils import cotizador_digital_pdf_bytes, download_excel_button, money, sidebar_user_box

user = auth.current_user()
sidebar_user_box()

st.title("🖨️ Cotizador Digital")
st.caption(
    "Convierte el catálogo de precios de Visión Digital en una cotización lista para descargar en "
    "PDF. Al generarla, también queda registrada automáticamente en 'Cotizaciones'."
)

puede_gestionar = auth.can_edit()
margenes = db.get_margenes_cotizador_digital()

# Los dos códigos "BOND DIGITAL ... 80 GRS BASE 20" del catálogo ya están a
# precio POR HOJA (no por pliego, como el resto) — se excluyen de "Impresión
# en pliego" porque el cálculo de piezas-por-pliego no les aplica; para ese
# caso de uso ya existe "Papel bond / inkjet" con su propia tabla de precios.
MATERIALES_PLIEGO = [m for m in MATERIALES_DIGITAL if m["codigo"] not in ("010011", "010012")]

TIPOS_MODO_IMPRESION = {
    "tiro": "Tiro (un solo lado)",
    "tr": "Tiro y retiro (impreso por los dos lados)",
}
TIPOS_MODO_PAPEL_BOND = {
    "tiro_1_color": "Tiro — un color",
    "tiro_color": "Tiro — a color",
    "duplex_1_color": "Dúplex (2 lados) — un color",
    "duplex_color": "Dúplex (2 lados) — a color",
}


def _precio_valido(v):
    return v if isinstance(v, (int, float)) and v > 0 else None


def _piezas_por_pliego(pieza_w, pieza_h, sheet_w, sheet_h, margen):
    def caben(a, b):
        return math.floor(sheet_w / (a + margen)) * math.floor(sheet_h / (b + margen))
    return max(caben(pieza_w, pieza_h), caben(pieza_h, pieza_w))


def _con_margen(costo_total, margen_pct, cantidad):
    """A partir del costo total calculado y el % de margen de utilidad de la
    tarifa correspondiente, arma el precio de venta final — precio_venta =
    costo x (1 + %/100) — y el resto de campos de la utilidad/margen real
    que se muestran como KPI (nunca en el PDF del cliente)."""
    precio_venta = costo_total * (1 + margen_pct / 100)
    utilidad = precio_venta - costo_total
    margen_real_pct = (utilidad / precio_venta * 100) if precio_venta else 0.0
    return {
        "costo_total": costo_total, "margen_pct": margen_pct, "precio_venta": precio_venta,
        "utilidad": utilidad, "margen_real_pct": margen_real_pct,
        # "total" queda como el precio de VENTA (compatibilidad con la fila que se
        # crea en 'Cotizaciones' y con el PDF, que muestran precio al cliente).
        "total": precio_venta, "precio_unitario": precio_venta / cantidad if cantidad else 0.0,
    }


def _calcular_pliego(material, tarifa, modo, pieza_w, pieza_h, cantidad, laminado, foil, troquel, envio):
    if pieza_w <= 0 or pieza_h <= 0 or cantidad <= 0:
        return None
    precio_impresion = _precio_valido(material["precios"][tarifa].get(modo))
    if precio_impresion is None:
        return None
    piezas = _piezas_por_pliego(pieza_w, pieza_h, material["sheet_w"], material["sheet_h"], MARGEN_CORTE_PULGADAS)
    if piezas <= 0:
        return None
    pliegos = math.ceil(cantidad / piezas)

    costo_impresion = pliegos * precio_impresion
    precio_laminado = _precio_valido(material.get("laminado_tr") if modo == "tr" else material.get("laminado_tiro"))
    costo_laminado = pliegos * precio_laminado if (laminado and precio_laminado) else 0.0
    precio_foil = _precio_valido(material.get("foil"))
    costo_foil = pliegos * precio_foil if (foil and precio_foil) else 0.0
    precio_troquel = _precio_valido(material.get("troquelado"))
    costo_troquel = pliegos * precio_troquel if (troquel and precio_troquel) else 0.0
    ventaja = precio_impresion * VENTAJA_FACTOR
    envio = envio or 0.0

    costo_total = costo_impresion + costo_laminado + costo_foil + costo_troquel + ventaja + envio
    return {
        "piezas_por_pliego": piezas, "pliegos": pliegos, "precio_impresion_pliego": precio_impresion,
        "costo_impresion": costo_impresion, "costo_laminado": costo_laminado, "costo_foil": costo_foil,
        "costo_troquel": costo_troquel, "ventaja": ventaja, "envio": envio,
        **_con_margen(costo_total, margenes.get(tarifa, 0.0), cantidad),
    }


def _calcular_papel_bond(bloque, idx_tamano, modo, cantidad, envio):
    if cantidad <= 0:
        return None
    precio_hoja = _precio_valido(bloque[modo][idx_tamano])
    if precio_hoja is None:
        return None
    subtotal = precio_hoja * cantidad
    envio = envio or 0.0
    costo_total = subtotal + envio
    # No hay tarifas LPM para papel bond/inkjet — se usa el margen de "normal".
    return {
        "precio_hoja": precio_hoja, "subtotal": subtotal, "envio": envio,
        **_con_margen(costo_total, margenes.get("normal", 0.0), cantidad),
    }


if user["rol"] == "admin":
    tab_nueva, tab_lista, tab_margenes = st.tabs(
        ["🧮 Nueva cotización", "📋 Cotizaciones guardadas", "⚙️ Márgenes"]
    )
else:
    tab_nueva, tab_lista = st.tabs(["🧮 Nueva cotización", "📋 Cotizaciones guardadas"])
    tab_margenes = None

# ---------------------------------------------------------------------------
# Nueva cotización
# ---------------------------------------------------------------------------
with tab_nueva:
    if not puede_gestionar:
        st.info("Tu rol es de solo vista y no puede generar cotizaciones aquí.")
    else:
        if user["rol"] == "admin":
            vendedores = db.list_vendedores()
            opciones_v = {v["nombre"]: v["id"] for v in vendedores}
            if not opciones_v:
                st.warning("No hay vendedores registrados todavía.")
                st.stop()
            vendedor_nombre = st.selectbox("Vendedor", list(opciones_v.keys()), key="cd_vendedor")
            vendedor_id = opciones_v[vendedor_nombre]
        else:
            vendedor_id = user["id"]
            st.caption(f"Vendedor: **{user['nombre']}**")

        prospectos = db.list_prospectos(vendedor_id)
        opciones_p = {p["nombre_cliente"]: p["id"] for p in prospectos}
        ESCRIBIR_CLIENTE_NUEVO = "✍️ Escribir un cliente nuevo"
        opciones_cliente = [ESCRIBIR_CLIENTE_NUEVO] + list(opciones_p.keys())
        cliente_sel = st.selectbox("Cliente", opciones_cliente, key="cd_cliente_sel")

        if cliente_sel == ESCRIBIR_CLIENTE_NUEVO:
            nombre_cliente_nuevo = st.text_input(
                "Nombre del cliente", key="cd_cliente_nuevo", placeholder="Ej. Banco Industrial",
            )
            prospecto_id = None
            st.caption(
                "Si el nombre ya existe entre tus prospectos, se usa ese mismo; si no, se crea uno nuevo "
                "en 'Prospección (CRM)' al generar la cotización."
            )
        else:
            nombre_cliente_nuevo = None
            prospecto_id = opciones_p[cliente_sel]

        st.divider()
        tipo_trabajo = st.radio(
            "Tipo de trabajo",
            ["Impresión en pliego (tarjetas, stickers, empaques...)", "Papel bond / inkjet (formularios, manuales...)"],
            key="cd_tipo_trabajo",
        )

        nombre_producto = st.text_input(
            "Nombre del producto", key="cd_nombre_producto",
            placeholder="Ej. Tarjetas de presentación — Banco Industrial",
        )

        resultado = None
        detalle_pdf = {}

        if tipo_trabajo.startswith("Impresión en pliego"):
            c1, c2 = st.columns(2)
            opciones_material = {
                f"{m['nombre']} (pliego {m['sheet_w']:.0f}x{m['sheet_h']:.0f}\")": m for m in MATERIALES_PLIEGO
            }
            material_label = c1.selectbox("Material", list(opciones_material.keys()), key="cd_material")
            material = opciones_material[material_label]
            tarifa = c2.selectbox(
                "Tarifa", TARIFAS_DIGITAL, format_func=lambda t: TARIFA_LABEL[t], key="cd_tarifa",
            )

            modos_disponibles = [
                m for m in ("tiro", "tr") if _precio_valido(material["precios"][tarifa].get(m)) is not None
            ]
            if not modos_disponibles:
                st.error("Este material no tiene precio cargado para la tarifa elegida. Prueba con otra tarifa.")
            else:
                modo = st.selectbox(
                    "Impresión", modos_disponibles, format_func=lambda m: TIPOS_MODO_IMPRESION[m], key="cd_modo",
                )

                c3, c4, c5 = st.columns(3)
                pieza_w = c3.number_input("Tamaño — ancho (pulgadas)", min_value=0.1, value=3.5, step=0.1, key="cd_ancho")
                pieza_h = c4.number_input("Tamaño — alto (pulgadas)", min_value=0.1, value=2.0, step=0.1, key="cd_alto")
                cantidad = c5.number_input("Cantidad", min_value=1, value=500, step=1, key="cd_cantidad")

                puede_laminado = _precio_valido(material.get("laminado_tiro")) or _precio_valido(material.get("laminado_tr"))
                puede_foil = _precio_valido(material.get("foil")) is not None
                puede_troquel = _precio_valido(material.get("troquelado")) is not None

                c6, c7, c8 = st.columns(3)
                laminado = c6.checkbox("Laminado", value=False, disabled=not puede_laminado, key="cd_laminado")
                if not puede_laminado:
                    c6.caption("No disponible para este material.")
                foil = c7.checkbox("Foil", value=False, disabled=not puede_foil, key="cd_foil")
                if not puede_foil:
                    c7.caption("No disponible para este material.")
                troquel = c8.checkbox("Troquelado", value=False, disabled=not puede_troquel, key="cd_troquel")
                if not puede_troquel:
                    c8.caption("No disponible para este material.")

                envio = st.number_input("Costo de envío (Q, opcional)", min_value=0.0, value=0.0, step=10.0, key="cd_envio")
                st.caption(
                    f"Se calcula dejando {MARGEN_CORTE_PULGADAS}\" de margen de corte entre piezas, igual que en "
                    "producción."
                )

                resultado = _calcular_pliego(
                    material, tarifa, modo, pieza_w, pieza_h, cantidad, laminado, foil, troquel, envio,
                )
                if resultado is None:
                    st.error("La pieza no cabe en el pliego de este material con esas medidas — revisa el tamaño.")
                else:
                    if tarifa == "gerencial" and resultado["pliegos"] < 250:
                        st.warning(
                            f"La tarifa 'Gerencial' aplica desde 250 pliegos y este trabajo usa "
                            f"{resultado['pliegos']}. Considera cambiar a la tarifa 'Normal'."
                        )
                    st.info(
                        f"📐 {resultado['piezas_por_pliego']} piezas por pliego · **{resultado['pliegos']} pliegos** "
                        f"necesarios para {cantidad} piezas.  \n"
                        f"Impresión: {money(resultado['costo_impresion'])} · Laminado: {money(resultado['costo_laminado'])} · "
                        f"Foil: {money(resultado['costo_foil'])} · Troquelado: {money(resultado['costo_troquel'])} · "
                        f"Merma de producción: {money(resultado['ventaja'])} · Envío: {money(resultado['envio'])}  \n"
                        f"**Costo total: {money(resultado['costo_total'])}**"
                    )
                    st.success(
                        f"Margen ({TARIFA_LABEL[tarifa]}): **{resultado['margen_pct']:.0f}%** · "
                        f"Utilidad: {money(resultado['utilidad'])} (margen real {resultado['margen_real_pct']:.1f}%)  \n"
                        f"**Precio de venta: {money(resultado['total'])} · Precio unitario: {money(resultado['precio_unitario'])}**"
                    )
                    detalle_pdf = {
                        "tipo": "Impresión en pliego",
                        "material": material["nombre"],
                        "tarifa": TARIFA_LABEL[tarifa],
                        "impresion": TIPOS_MODO_IMPRESION[modo],
                        "tamano": f'{pieza_w}" x {pieza_h}"',
                        "cantidad": cantidad,
                        "procesos": ", ".join(
                            p for p, activo in [("Laminado", laminado), ("Foil", foil), ("Troquelado", troquel)] if activo
                        ) or "Ninguno",
                    }
        else:
            opciones_bloque = {b["titulo"]: b for b in PAPEL_BOND_INKJET}
            c1, c2 = st.columns(2)
            bloque_label = c1.selectbox("Gramaje", list(opciones_bloque.keys()), key="cd_pb_bloque")
            bloque = opciones_bloque[bloque_label]
            tamano_label = c2.selectbox("Tamaño de hoja", bloque["tamanos"], key="cd_pb_tamano")
            idx_tamano = bloque["tamanos"].index(tamano_label)

            c3, c4 = st.columns(2)
            modo = c3.selectbox(
                "Tipo de impresión", list(TIPOS_MODO_PAPEL_BOND.keys()),
                format_func=lambda m: TIPOS_MODO_PAPEL_BOND[m], key="cd_pb_modo",
            )
            cantidad = c4.number_input("Cantidad de hojas", min_value=1, value=100, step=1, key="cd_pb_cantidad")
            envio = st.number_input("Costo de envío (Q, opcional)", min_value=0.0, value=0.0, step=10.0, key="cd_pb_envio")
            st.caption(f"Se usa el margen de utilidad de la tarifa '{TARIFA_LABEL['normal']}' ({margenes.get('normal', 0):.0f}%).")

            resultado = _calcular_papel_bond(bloque, idx_tamano, modo, cantidad, envio)
            if resultado is None:
                st.error("Esta combinación de tamaño/impresión no tiene precio cargado en el catálogo.")
            else:
                st.info(
                    f"Precio por hoja: {money(resultado['precio_hoja'])} · Subtotal: {money(resultado['subtotal'])} · "
                    f"Envío: {money(resultado['envio'])}  \n"
                    f"**Costo total: {money(resultado['costo_total'])}**"
                )
                st.success(
                    f"Margen: **{resultado['margen_pct']:.0f}%** · Utilidad: {money(resultado['utilidad'])} "
                    f"(margen real {resultado['margen_real_pct']:.1f}%)  \n"
                    f"**Precio de venta: {money(resultado['total'])} · Precio unitario: {money(resultado['precio_unitario'])}**"
                )
                detalle_pdf = {
                    "tipo": "Papel bond / inkjet",
                    "material": f"{bloque['titulo']} — {tamano_label}",
                    "tarifa": "—",
                    "impresion": TIPOS_MODO_PAPEL_BOND[modo],
                    "tamano": tamano_label,
                    "cantidad": cantidad,
                    "procesos": "Ninguno",
                }

        notas = st.text_area(
            "Notas de producción (opcional)",
            key="cd_notas",
            placeholder="Ej. Distribución de datos variables, forma de empaque, instrucciones especiales...",
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
                        notas="Creado automáticamente desde Cotizador Digital.",
                        estado="Prospecto", productos=[],
                    )

            r = db.create_cotizacion_digital(
                prospecto_id=prospecto_id_final, vendedor_id=vendedor_id,
                nombre_producto=nombre_producto.strip(), tipo_trabajo=detalle_pdf.get("tipo"),
                detalle=detalle_pdf, resultado=resultado, notas=notas.strip() or None,
                creado_por=user["nombre"],
            )
            for k in list(st.session_state.keys()):
                if k.startswith("cd_"):
                    del st.session_state[k]
            st.success(
                f"Cotización CD-{r['numero']:04d} generada y agregada a 'Cotizaciones'. Ve a la pestaña "
                "'📋 Cotizaciones guardadas' para descargar el PDF."
            )
            st.rerun()

# ---------------------------------------------------------------------------
# Cotizaciones guardadas
# ---------------------------------------------------------------------------
with tab_lista:
    cotizaciones = db.list_cotizaciones_digital()
    if user["rol"] not in ("admin", "vista"):
        cotizaciones = [c for c in cotizaciones if c.get("vendedor_id") == user["id"]]

    if not cotizaciones:
        st.info("No hay cotizaciones del Cotizador Digital registradas todavía.")
    else:
        resultados = [c.get("resultado") or {} for c in cotizaciones]
        utilidad_total = sum(r.get("utilidad") or 0 for r in resultados)
        ventas_total = sum(r.get("total") or 0 for r in resultados)
        margen_prom = (utilidad_total / ventas_total * 100) if ventas_total else 0.0

        st.markdown("#### 📊 KPIs")
        k1, k2, k3 = st.columns(3)
        k1.metric("Cotizaciones generadas", len(cotizaciones))
        k2.metric("Utilidad total", money(utilidad_total))
        k3.metric("Margen real promedio", f"{margen_prom:.1f}%")

        vendedores_map = {v["id"]: v["nombre"] for v in db.list_usuarios()}
        df = pd.DataFrame([{
            "Número": f"CD-{c.get('numero', 0):04d}", "Fecha": (c.get("creado_en") or "")[:10],
            "Cliente": db.get_prospecto(c.get("prospecto_id"))["nombre_cliente"] if c.get("prospecto_id") and db.get_prospecto(c.get("prospecto_id")) else "—",
            "Producto": c.get("nombre_producto") or "—", "Tipo": c.get("tipo_trabajo") or "—",
            "Costo": money((c.get("resultado") or {}).get("costo_total")),
            "Precio de venta": money((c.get("resultado") or {}).get("total")),
            "Utilidad": money((c.get("resultado") or {}).get("utilidad")),
            "Margen %": f"{(c.get('resultado') or {}).get('margen_real_pct', 0):.1f}%",
            "Vendedor": vendedores_map.get(c.get("vendedor_id"), "—"),
        } for c in cotizaciones])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_excel_button(df, "cotizador_digital.xlsx", key="cd_descargar_excel")

        st.divider()
        st.markdown("#### 🔎 Ver detalle y descargar PDF")
        opciones_c = {f"CD-{c.get('numero', 0):04d} — {c.get('nombre_producto') or ''}": c["id"] for c in cotizaciones}
        elegido = st.selectbox("Selecciona una cotización", ["—"] + list(opciones_c.keys()), key="cd_seleccion")
        if elegido != "—":
            cid = opciones_c[elegido]
            cot = db.get_cotizacion_digital(cid)
            if cot:
                prospecto = db.get_prospecto(cot.get("prospecto_id"))
                resultado_cot = cot.get("resultado") or {}
                detalle_cot = cot.get("detalle") or {}
                st.markdown(f"**Cliente:** {prospecto['nombre_cliente'] if prospecto else '—'}")
                st.markdown(f"**Producto:** {cot.get('nombre_producto') or '—'}  ·  **Tipo:** {cot.get('tipo_trabajo') or '—'}")
                st.caption(
                    f"Material: {detalle_cot.get('material') or '—'} · Impresión: {detalle_cot.get('impresion') or '—'} · "
                    f"Tamaño: {detalle_cot.get('tamano') or '—'} · Cantidad: {detalle_cot.get('cantidad') or '—'} · "
                    f"Procesos: {detalle_cot.get('procesos') or '—'}"
                )
                if cot.get("notas"):
                    st.caption(f"📝 {cot['notas']}")
                st.markdown(
                    f"**Costo: {money(resultado_cot.get('costo_total'))} · Margen: {resultado_cot.get('margen_pct', 0):.0f}% "
                    f"· Utilidad: {money(resultado_cot.get('utilidad'))} (margen real {resultado_cot.get('margen_real_pct', 0):.1f}%)**"
                )
                st.markdown(
                    f"**Precio de venta: {money(resultado_cot.get('total'))} · Precio unitario: "
                    f"{money(resultado_cot.get('precio_unitario'))}**"
                )
                st.caption("El desglose de costo/margen/utilidad es información interna — no aparece en el PDF descargable.")

                pdf_bytes = cotizador_digital_pdf_bytes(cot, prospecto, vendedores_map.get(cot.get("vendedor_id"), "—"))
                st.download_button(
                    "📄 Descargar cotización (PDF)", data=pdf_bytes,
                    file_name=f"cotizacion_CD-{cot.get('numero', 0):04d}.pdf", mime="application/pdf",
                    use_container_width=True,
                )

                if puede_gestionar:
                    with st.expander("🗑️ Eliminar esta cotización"):
                        st.caption("Esto NO elimina la fila correspondiente en 'Cotizaciones' — hay que borrarla aparte ahí si hace falta.")
                        confirmar_borrar = st.checkbox("Confirmo que quiero eliminar esta cotización", key=f"cd_conf_del_{cid}")
                        if st.button("Eliminar cotización", key=f"cd_btn_del_{cid}", disabled=not confirmar_borrar):
                            db.delete_cotizacion_digital(cid)
                            st.success("Cotización eliminada.")
                            st.rerun()

# ---------------------------------------------------------------------------
# Márgenes (solo admin)
# ---------------------------------------------------------------------------
if tab_margenes is not None:
    with tab_margenes:
        st.caption(
            "Define el % de margen de utilidad que se aplica automáticamente sobre el costo calculado, "
            "según la tarifa del catálogo LPM elegida en cada cotización — precio de venta = costo x "
            "(1 + %/100). Los cambios solo afectan a las cotizaciones nuevas; las que ya se generaron no "
            "cambian."
        )
        with st.form("cd_form_margenes"):
            cols = st.columns(4)
            nuevos_margenes = {}
            for i, tarifa_key in enumerate(TARIFAS_DIGITAL):
                nuevos_margenes[tarifa_key] = cols[i].number_input(
                    TARIFA_LABEL[tarifa_key], min_value=0.0, max_value=1000.0,
                    value=float(margenes.get(tarifa_key, 0.0)), step=1.0, key=f"cd_margen_form_{tarifa_key}",
                )
            st.caption("'Papel bond / inkjet' (no tiene tarifas LPM) usa el mismo % que la tarifa 'Normal'.")
            if st.form_submit_button("💾 Guardar márgenes", use_container_width=True):
                db.set_margenes_cotizador_digital(nuevos_margenes)
                st.success("Márgenes actualizados.")
                st.rerun()
