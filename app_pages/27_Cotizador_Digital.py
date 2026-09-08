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
    falta para la cantidad pedida, y el costo de cada pliego (impresión +
    laminado/foil/troquel si aplican) + una "ventaja" de merma de producción
    + envío.
  - "Papel bond / inkjet": formularios, manuales, hojas sueltas — el precio
    ya es por hoja al tamaño final, sin necesidad de calcular pliegos.

Los precios NO se leen de un Excel en vivo: están cargados como datos fijos
en pricing_data.py (a partir del Excel "LPM_DIGITAL_ABRIL2025" que compartió
Steven), para que la cotización funcione igual en Streamlit Cloud. Si el
priciario cambia, hay que actualizar ese archivo.

Al generar una cotización aquí, además de guardarse en este cotizador
también se crea automáticamente una fila en la pestaña "Cotizaciones" (con
el mismo monto y cliente), para no duplicar el trabajo de registro — ver
db.create_cotizacion_digital.
"""

import math
from datetime import date

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

    total = costo_impresion + costo_laminado + costo_foil + costo_troquel + ventaja + envio
    return {
        "piezas_por_pliego": piezas, "pliegos": pliegos, "precio_impresion_pliego": precio_impresion,
        "costo_impresion": costo_impresion, "costo_laminado": costo_laminado, "costo_foil": costo_foil,
        "costo_troquel": costo_troquel, "ventaja": ventaja, "envio": envio, "total": total,
        "precio_unitario": total / cantidad,
    }


def _calcular_papel_bond(bloque, idx_tamano, modo, cantidad, envio):
    if cantidad <= 0:
        return None
    precio_hoja = _precio_valido(bloque[modo][idx_tamano])
    if precio_hoja is None:
        return None
    subtotal = precio_hoja * cantidad
    envio = envio or 0.0
    total = subtotal + envio
    return {"precio_hoja": precio_hoja, "subtotal": subtotal, "envio": envio, "total": total,
            "precio_unitario": total / cantidad}


tab_nueva, tab_lista = st.tabs(["🧮 Nueva cotización", "📋 Cotizaciones guardadas"])

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
        if not prospectos:
            st.warning("Este vendedor no tiene prospectos registrados. Crea uno primero en 'Prospección (CRM)'.")
            st.stop()

        opciones_p = {p["nombre_cliente"]: p["id"] for p in prospectos}
        prospecto_sel = st.selectbox("Prospecto/cliente", list(opciones_p.keys()), key="cd_prospecto")
        prospecto_id = opciones_p[prospecto_sel]

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
                        f"**Total: {money(resultado['total'])} · Precio unitario: {money(resultado['precio_unitario'])}**"
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

            resultado = _calcular_papel_bond(bloque, idx_tamano, modo, cantidad, envio)
            if resultado is None:
                st.error("Esta combinación de tamaño/impresión no tiene precio cargado en el catálogo.")
            else:
                st.info(
                    f"Precio por hoja: {money(resultado['precio_hoja'])} · Subtotal: {money(resultado['subtotal'])} · "
                    f"Envío: {money(resultado['envio'])}  \n"
                    f"**Total: {money(resultado['total'])} · Precio unitario: {money(resultado['precio_unitario'])}**"
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

        if st.button(
            "💾 Generar cotización", type="primary", use_container_width=True,
            disabled=resultado is None or not nombre_producto.strip(),
        ):
            r = db.create_cotizacion_digital(
                prospecto_id=prospecto_id, vendedor_id=vendedor_id,
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
        vendedores_map = {v["id"]: v["nombre"] for v in db.list_usuarios()}
        df = pd.DataFrame([{
            "Número": f"CD-{c.get('numero', 0):04d}", "Fecha": (c.get("creado_en") or "")[:10],
            "Cliente": db.get_prospecto(c.get("prospecto_id"))["nombre_cliente"] if c.get("prospecto_id") and db.get_prospecto(c.get("prospecto_id")) else "—",
            "Producto": c.get("nombre_producto") or "—", "Tipo": c.get("tipo_trabajo") or "—",
            "Total": money((c.get("resultado") or {}).get("total")),
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
                    f"**Total: {money(resultado_cot.get('total'))} · Precio unitario: "
                    f"{money(resultado_cot.get('precio_unitario'))}**"
                )

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
