import base64
from datetime import date

import streamlit as st

import auth
import database as db
from config import DOCUMENTOS_ARCHIVO_MAX_BYTES, DOCUMENTOS_ARCHIVO_MAX_BYTES_STORAGE, DOCUMENTOS_CATEGORIAS
from utils import sidebar_user_box

user = auth.current_user()
sidebar_user_box()
puede_subir = user["rol"] == "admin"

_usa_storage = db.storage_disponible()
_documentos_max_bytes = DOCUMENTOS_ARCHIVO_MAX_BYTES_STORAGE if _usa_storage else DOCUMENTOS_ARCHIVO_MAX_BYTES

CATEGORIA_EMOJI = {
    "Legal": "⚖️", "Políticas": "📋", "Presentaciones": "📊", "Otros": "🗂️",
}

st.title("📄 Documentos")
st.caption(
    "Biblioteca de documentos en PDF (legal, políticas, presentaciones) organizados por categoría, "
    "disponibles para consultar y descargar."
    + ("" if puede_subir else " Tu acceso es solo de consulta: puedes ver y descargar, pero no subir ni eliminar.")
)


def _subir_pdf(archivo_subido):
    """Sube el PDF a Firebase Storage si está disponible; si no, cae al
    guardado anterior (base64 dentro del documento). Lanza ValueError si el
    archivo pesa más de lo permitido."""
    if archivo_subido is None:
        raise ValueError("Debes seleccionar un archivo PDF.")
    datos = archivo_subido.getvalue()
    if len(datos) > _documentos_max_bytes:
        if _usa_storage:
            raise ValueError(
                f"El archivo pesa {len(datos) / 1_000_000:.1f} MB; el máximo permitido es "
                f"{_documentos_max_bytes / 1_000_000:.0f} MB."
            )
        raise ValueError(
            f"El archivo pesa {len(datos) / 1000:.0f} KB; el máximo permitido es "
            f"{_documentos_max_bytes / 1000:.0f} KB."
        )
    if _usa_storage:
        return db.subir_archivo_storage("documentos", archivo_subido)
    return {
        "nombre": archivo_subido.name, "tipo": archivo_subido.type or "application/pdf",
        "b64": base64.b64encode(datos).decode("ascii"),
    }


if puede_subir:
    with st.expander("➕ Subir documento nuevo"):
        with st.form("documentos_nuevo", clear_on_submit=True):
            titulo_n = st.text_input("Título del documento")
            categoria_n = st.selectbox("Categoría", DOCUMENTOS_CATEGORIAS)
            descripcion_n = st.text_area("Descripción (opcional)")
            archivo_n = st.file_uploader("Archivo PDF", type=["pdf"])
            if _usa_storage:
                st.caption(f"Tamaño máximo por archivo: {_documentos_max_bytes // 1_000_000} MB.")
            else:
                st.caption(f"Tamaño máximo por archivo: {_documentos_max_bytes // 1000} KB.")
            if st.form_submit_button("Subir documento", use_container_width=True):
                if not titulo_n.strip():
                    st.error("El título del documento es obligatorio.")
                elif archivo_n is None:
                    st.error("Debes seleccionar un archivo PDF.")
                else:
                    try:
                        archivo_info = _subir_pdf(archivo_n)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        db.create_documento(
                            titulo_n.strip(), categoria_n, descripcion_n.strip() or None,
                            archivo_info, creado_por_id=user["id"],
                        )
                        st.success(f"Documento '{titulo_n.strip()}' agregado a «{categoria_n}».")
                        st.rerun()

st.divider()

tabs = st.tabs([f"{CATEGORIA_EMOJI.get(cat, '')} {cat}" for cat in DOCUMENTOS_CATEGORIAS])
for tab, categoria in zip(tabs, DOCUMENTOS_CATEGORIAS):
    with tab:
        documentos = db.list_documentos(categoria=categoria)
        if not documentos:
            st.info(f"Todavía no hay documentos en «{categoria}».")
            continue
        for d in documentos:
            with st.container(border=True):
                st.markdown(f"**{d.get('titulo') or 'Sin título'}**")
                if d.get("descripcion"):
                    st.caption(d["descripcion"])
                st.caption(f"🕒 Subido: {(d.get('creado_en') or '')[:10]}")

                if puede_subir:
                    col_descarga, col_borrar = st.columns([3, 1])
                else:
                    col_descarga, col_borrar = st.container(), None

                if d.get("storage_path"):
                    url_archivo = db.url_descarga_archivo_storage(
                        d["storage_path"], nombre_descarga=d.get("nombre"),
                    )
                    with col_descarga:
                        if url_archivo:
                            st.link_button(
                                f"📎 Descargar «{d.get('nombre') or 'documento'}»", url_archivo,
                                use_container_width=True, key=f"doc_dl_{d['id']}",
                            )
                        else:
                            st.caption("📎 No se pudo generar el enlace de descarga.")
                elif d.get("b64"):
                    with col_descarga:
                        st.download_button(
                            f"📎 Descargar «{d.get('nombre') or 'documento'}»",
                            data=base64.b64decode(d["b64"]), file_name=d.get("nombre") or "documento.pdf",
                            mime=d.get("tipo") or "application/pdf",
                            use_container_width=True, key=f"doc_dl_{d['id']}",
                        )
                else:
                    with col_descarga:
                        st.caption("📎 Este documento no tiene un archivo asociado.")

                if puede_subir:
                    with col_borrar:
                        if st.button("🗑️ Eliminar", key=f"doc_borrar_{d['id']}", use_container_width=True):
                            db.delete_documento(d["id"])
                            st.success("Documento eliminado.")
                            st.rerun()
