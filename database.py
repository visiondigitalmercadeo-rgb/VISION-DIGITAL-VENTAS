"""Capa de datos — Firestore (Firebase), con un 'modo de práctica' automático
en memoria mientras todavía no tienes tus credenciales de Firebase.

Todo el resto de la aplicación (app_pages/*.py) llama únicamente a las
funciones de este archivo — nunca usa Firestore directamente — así que si
algún día cambias de proveedor de base de datos, solo hay que tocar aquí.

Cómo se eligen las credenciales, en este orden:
  1. `st.secrets["firebase"]`      → para cuando la plataforma esté publicada
                                      en Streamlit Community Cloud.
  2. `serviceAccountKey.json`      → archivo que descargas de Firebase y
     (en la carpeta del proyecto)   colocas junto a este archivo, para uso
                                      local en tu computadora.
  3. Si no se encuentra ninguna    → la app sigue funcionando con datos de
     de las dos anteriores           práctica en memoria (se pierden al
                                      cerrar el servidor), y en pantalla se
                                      avisa que Firebase no está conectado.
"""

import os
from datetime import date, datetime, timedelta

import bcrypt
import firebase_admin
from firebase_admin import credentials, firestore

import fake_firestore
from config import BASE_DIR, CHECKLIST_DEFAULT

SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

_client = None
MODO_PRACTICA = False  # se actualiza la primera vez que se pide el cliente


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Conexión a Firestore (o modo de práctica en memoria)
# ---------------------------------------------------------------------------
def _cargar_credenciales():
    try:
        import streamlit as st
        if "firebase" in st.secrets:
            return credentials.Certificate(dict(st.secrets["firebase"]))
    except Exception as e:
        import traceback
        print("ERROR AL CARGAR CREDENCIALES DE FIREBASE:", e)
        traceback.print_exc()

    if os.path.exists(SERVICE_ACCOUNT_PATH):
        return credentials.Certificate(SERVICE_ACCOUNT_PATH)

    return None


def get_client():
    """Devuelve el cliente de Firestore (real o de práctica), creándolo la
    primera vez que se necesita y reutilizándolo en el resto de la sesión."""
    global _client, MODO_PRACTICA
    if _client is not None:
        return _client

    cred = _cargar_credenciales()
    if cred is not None:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _client = firestore.client()
        MODO_PRACTICA = False
    else:
        _client = fake_firestore.FakeFirestoreClient()
        MODO_PRACTICA = True
    return _client


def firebase_conectado() -> bool:
    """True si la app está usando tu proyecto real de Firebase (no el modo
    de práctica). Se usa en app.py para mostrar el aviso correspondiente."""
    get_client()
    return not MODO_PRACTICA


def _doc_to_dict(snapshot):
    data = snapshot.to_dict()
    if data is None:
        return None
    return {**data, "id": snapshot.id}


# ---------------------------------------------------------------------------
# Inicialización y datos de ejemplo
# ---------------------------------------------------------------------------
def init_db(seed_demo: bool = True):
    client = get_client()
    usuarios = list(client.collection("usuarios").limit(1).stream())
    if not usuarios:
        _seed(client, seed_demo)


def _seed(client, seed_demo):
    now = str(date.today())

    users = [
        ("Administrador General", "admin", "admin123", "admin"),
        ("Visor Gerencia", "vista", "vista123", "vista"),
        ("Juan Pérez", "juan", "vendedor123", "vendedor"),
        ("María López", "maria", "vendedor123", "vendedor"),
        ("Carlos Ramírez", "carlos", "vendedor123", "vendedor"),
    ]
    ids = {}
    for nombre, username, pwd, rol in users:
        ref = client.collection("usuarios").document()
        ref.set({
            "nombre": nombre, "username": username, "password_hash": hash_password(pwd),
            "rol": rol, "activo": True, "fecha_creacion": now,
        })
        ids[username] = ref.id

    if not seed_demo:
        return

    juan, maria, carlos = ids["juan"], ids["maria"], ids["carlos"]
    today = date.today()

    prospectos = [
        ("Imprenta El Sol, S.A.", "1234567-8", juan, "Prospecto"),
        ("Distribuidora Central", "2233445-6", maria, "En negociación"),
        ("Editorial Horizonte", "9988776-5", carlos, "Cliente (Ganado)"),
        ("Empaques del Norte", "5544332-1", juan, "Perdido"),
        ("Publicidad Maya", "7766554-3", maria, "Prospecto"),
    ]
    prospecto_ids = []
    for nombre, nit, vendedor_id, estado in prospectos:
        ref = client.collection("prospectos").document()
        ref.set({
            "nombre_cliente": nombre, "nit": nit, "telefono": "5555-0000",
            "email": "contacto@ejemplo.com", "direccion": "Zona 10, Ciudad de Guatemala",
            "vendedor_id": vendedor_id, "fecha_registro": str(today - timedelta(days=10)),
            "fecha_seguimiento": str(today + timedelta(days=2)),
            "recordatorio": "Llamar para confirmar interés",
            "notas": "Prospecto de ejemplo (dato semilla)", "estado": estado,
        })
        prospecto_ids.append(ref.id)

    client.collection("cotizaciones").document().set({
        "prospecto_id": prospecto_ids[2], "vendedor_id": carlos,
        "fecha_contacto": str(today - timedelta(days=8)), "fecha_cotizacion": str(today - timedelta(days=5)),
        "numero_cotizacion": "COT-0001", "monto": 15400.0, "estado": "Aprobada", "notas": "Cotización de ejemplo",
    })
    client.collection("cotizaciones").document().set({
        "prospecto_id": prospecto_ids[1], "vendedor_id": maria,
        "fecha_contacto": str(today - timedelta(days=3)), "fecha_cotizacion": str(today - timedelta(days=1)),
        "numero_cotizacion": "COT-0002", "monto": 8200.0, "estado": "Enviada", "notas": "Cotización de ejemplo",
    })

    for vendedor_id, cliente, tipo, dias, estado in [
        (juan, "Imprenta El Sol, S.A.", "Cita", -2, "Realizada"),
        (juan, "Empaques del Norte", "Llamada", 1, "Programada"),
        (maria, "Distribuidora Central", "Visita", 0, "Programada"),
        (carlos, "Editorial Horizonte", "Cita", -5, "Realizada"),
    ]:
        client.collection("citas").document().set({
            "vendedor_id": vendedor_id, "prospecto_id": None, "cliente_nombre": cliente, "tipo": tipo,
            "fecha": str(today + timedelta(days=dias)), "hora": "10:00", "lugar": "Oficinas del cliente",
            "estado": estado, "notas": "Dato de ejemplo",
        })

    checklist = [{"item": i, "ok": False} for i in CHECKLIST_DEFAULT]
    client.collection("visitas_mercadeo").document().set({
        "vendedor_id": maria, "punto_venta": "Librería Central", "direccion": "6a avenida, Zona 1",
        "fecha": str(today), "checklist": checklist, "pendientes": "Revisar exhibición de vitrina",
        "estado": "Pendiente", "notas": "Dato de ejemplo",
    })

    client.collection("reclamos").document().set({
        "cliente": "Editorial Horizonte", "nit": "9988776-5", "numero_orden": "ORD-4521",
        "fecha_reclamo": str(today - timedelta(days=4)), "fecha_solucion": None,
        "estatus": "En proceso", "descripcion": "Diferencia de color en impresión offset", "vendedor_id": carlos,
    })

    for vendedor_id, planta, linea, monto in [
        (juan, "Offset", "Volantes", 3200.0),
        (juan, "Digital", "Tarjetas de presentación", 950.0),
        (maria, "Valloy", "Etiquetas", 1800.0),
        (carlos, "Colorado", "Empaques", 4200.0),
        (carlos, "Offset", "Revistas", 6100.0),
    ]:
        client.collection("ventas").document().set({
            "vendedor_id": vendedor_id, "fecha": str(today), "planta": planta,
            "linea_venta": linea, "monto": monto, "notas": "Dato de ejemplo",
        })


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
def get_user_by_username(username):
    client = get_client()
    for snap in client.collection("usuarios").where("username", "==", username).limit(1).stream():
        return _doc_to_dict(snap)
    return None


def list_usuarios(solo_activos=False):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("usuarios").stream()]
    if solo_activos:
        rows = [r for r in rows if r["activo"]]
    rows.sort(key=lambda r: (r["rol"], r["nombre"]))
    return rows


def list_vendedores(solo_activos=True):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("usuarios").where("rol", "==", "vendedor").stream()]
    if solo_activos:
        rows = [r for r in rows if r["activo"]]
    rows.sort(key=lambda r: r["nombre"])
    return rows


def create_usuario(nombre, username, password, rol):
    client = get_client()
    client.collection("usuarios").document().set({
        "nombre": nombre, "username": username, "password_hash": hash_password(password),
        "rol": rol, "activo": True, "fecha_creacion": str(date.today()),
    })


def set_usuario_activo(user_id, activo):
    get_client().collection("usuarios").document(user_id).update({"activo": bool(activo)})


def reset_password(user_id, new_password):
    get_client().collection("usuarios").document(user_id).update({"password_hash": hash_password(new_password)})


def update_usuario(user_id, **kwargs):
    """Actualiza datos del usuario (ej. nombre, username, rol). No usar para
    la contraseña: para eso usa reset_password()."""
    kwargs.pop("password", None)
    kwargs.pop("password_hash", None)
    if kwargs:
        get_client().collection("usuarios").document(user_id).update(kwargs)


def delete_usuario(user_id):
    """Elimina el usuario por completo. Los registros que ya haya creado
    (prospectos, citas, ventas, etc.) NO se borran — solo dejan de tener un
    vendedor asignado (se mostrarán con '—')."""
    get_client().collection("usuarios").document(user_id).delete()


def nombre_vendedor(vendedor_id, vendedores=None):
    if vendedor_id is None:
        return "—"
    if vendedores is None:
        vendedores = list_usuarios()
    for v in vendedores:
        if v["id"] == vendedor_id:
            return v["nombre"]
    return "—"


# ---------------------------------------------------------------------------
# Prospectos / CRM
# ---------------------------------------------------------------------------
def find_prospectos_by_nit(nit, exclude_id=None):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("prospectos").where("nit", "==", nit.strip()).stream()]
    if exclude_id:
        rows = [r for r in rows if r["id"] != exclude_id]
    return rows


def list_prospectos(vendedor_id=None):
    client = get_client()
    coll = client.collection("prospectos")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r["fecha_registro"] or "", reverse=True)
    return rows


def create_prospecto(nombre_cliente, nit, telefono, email, direccion, vendedor_id,
                      fecha_seguimiento, recordatorio, notas, estado):
    get_client().collection("prospectos").document().set({
        "nombre_cliente": nombre_cliente, "nit": nit.strip(), "telefono": telefono, "email": email,
        "direccion": direccion, "vendedor_id": vendedor_id, "fecha_registro": str(date.today()),
        "fecha_seguimiento": str(fecha_seguimiento) if fecha_seguimiento else None,
        "recordatorio": recordatorio, "notas": notas, "estado": estado,
    })


def update_prospecto(prospecto_id, **kwargs):
    if kwargs:
        get_client().collection("prospectos").document(prospecto_id).update(kwargs)


def get_prospecto(prospecto_id):
    snap = get_client().collection("prospectos").document(prospecto_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def delete_prospecto(prospecto_id):
    """Elimina el prospecto por completo. Citas, cotizaciones u otros registros
    que lo mencionen no se borran, solo dejan de estar vinculados a él."""
    get_client().collection("prospectos").document(prospecto_id).delete()


def prospectos_con_seguimiento_proximo(vendedor_id=None, dias=3):
    hoy = date.today()
    limite = hoy + timedelta(days=dias)
    rows = list_prospectos(vendedor_id)
    return [
        r for r in rows
        if r["fecha_seguimiento"] and hoy.isoformat() <= r["fecha_seguimiento"] <= limite.isoformat()
        and r["estado"] not in ("Cliente (Ganado)", "Perdido")
    ]


# ---------------------------------------------------------------------------
# Llamadas
# ---------------------------------------------------------------------------
def find_llamadas_by_nit(nit, exclude_id=None):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("llamadas").where("nit", "==", nit.strip()).stream()]
    if exclude_id:
        rows = [r for r in rows if r["id"] != exclude_id]
    return rows


def list_llamadas(vendedor_id=None):
    client = get_client()
    coll = client.collection("llamadas")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r["fecha_registro"] or "", reverse=True)
    return rows


def create_llamada(nombre_cliente, nit, telefono, email, direccion, vendedor_id,
                    fecha_seguimiento, recordatorio, notas, estado, tipo_llamada):
    get_client().collection("llamadas").document().set({
        "nombre_cliente": nombre_cliente, "nit": nit.strip(), "telefono": telefono, "email": email,
        "direccion": direccion, "vendedor_id": vendedor_id, "fecha_registro": str(date.today()),
        "fecha_seguimiento": str(fecha_seguimiento) if fecha_seguimiento else None,
        "recordatorio": recordatorio, "notas": notas, "estado": estado, "tipo_llamada": tipo_llamada,
    })


def update_llamada(llamada_id, **kwargs):
    if kwargs:
        get_client().collection("llamadas").document(llamada_id).update(kwargs)


def get_llamada(llamada_id):
    snap = get_client().collection("llamadas").document(llamada_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def delete_llamada(llamada_id):
    """Elimina la llamada por completo (no se puede deshacer)."""
    get_client().collection("llamadas").document(llamada_id).delete()


# ---------------------------------------------------------------------------
# Cotizaciones
# ---------------------------------------------------------------------------
def list_cotizaciones(vendedor_id=None):
    client = get_client()
    coll = client.collection("cotizaciones")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    for r in rows:
        p = get_prospecto(r["prospecto_id"]) if r.get("prospecto_id") else None
        r["nombre_cliente"] = p["nombre_cliente"] if p else None
        r["nit"] = p["nit"] if p else None
    rows.sort(key=lambda r: r["fecha_cotizacion"] or "", reverse=True)
    return rows


def create_cotizacion(prospecto_id, vendedor_id, fecha_contacto, fecha_cotizacion,
                       numero_cotizacion, monto, estado, notas):
    get_client().collection("cotizaciones").document().set({
        "prospecto_id": prospecto_id, "vendedor_id": vendedor_id,
        "fecha_contacto": str(fecha_contacto) if fecha_contacto else None,
        "fecha_cotizacion": str(fecha_cotizacion) if fecha_cotizacion else None,
        "numero_cotizacion": numero_cotizacion, "monto": monto, "estado": estado, "notas": notas,
    })


def update_cotizacion(cotizacion_id, **kwargs):
    if kwargs:
        get_client().collection("cotizaciones").document(cotizacion_id).update(kwargs)


def delete_cotizacion(cotizacion_id):
    get_client().collection("cotizaciones").document(cotizacion_id).delete()


# ---------------------------------------------------------------------------
# Citas
# ---------------------------------------------------------------------------
def list_citas(vendedor_id=None, desde=None, hasta=None):
    client = get_client()
    coll = client.collection("citas")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    if desde:
        rows = [r for r in rows if r["fecha"] >= str(desde)]
    if hasta:
        rows = [r for r in rows if r["fecha"] <= str(hasta)]
    rows.sort(key=lambda r: (r["fecha"], r["hora"] or ""))
    return rows


def create_cita(vendedor_id, prospecto_id, cliente_nombre, tipo, fecha, hora, lugar, estado, notas):
    get_client().collection("citas").document().set({
        "vendedor_id": vendedor_id, "prospecto_id": prospecto_id, "cliente_nombre": cliente_nombre,
        "tipo": tipo, "fecha": str(fecha), "hora": str(hora) if hora else None,
        "lugar": lugar, "estado": estado, "notas": notas,
    })


def update_cita(cita_id, **kwargs):
    if kwargs:
        get_client().collection("citas").document(cita_id).update(kwargs)


def delete_cita(cita_id):
    get_client().collection("citas").document(cita_id).delete()


# ---------------------------------------------------------------------------
# Visitas de mercadeo
# ---------------------------------------------------------------------------
def list_visitas_mercadeo(vendedor_id=None):
    client = get_client()
    coll = client.collection("visitas_mercadeo")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    for r in rows:
        r["checklist_items"] = r.get("checklist") or []
    rows.sort(key=lambda r: r["fecha"] or "", reverse=True)
    return rows


def create_visita_mercadeo(vendedor_id, punto_venta, direccion, fecha, checklist_items, pendientes, estado, notas):
    get_client().collection("visitas_mercadeo").document().set({
        "vendedor_id": vendedor_id, "punto_venta": punto_venta, "direccion": direccion,
        "fecha": str(fecha), "checklist": checklist_items, "pendientes": pendientes,
        "estado": estado, "notas": notas,
    })


def update_visita_mercadeo(visita_id, **kwargs):
    if "checklist_items" in kwargs:
        kwargs["checklist"] = kwargs.pop("checklist_items")
    if kwargs:
        get_client().collection("visitas_mercadeo").document(visita_id).update(kwargs)


def delete_visita_mercadeo(visita_id):
    get_client().collection("visitas_mercadeo").document(visita_id).delete()


# ---------------------------------------------------------------------------
# Pendientes de mercadeo
# ---------------------------------------------------------------------------
def list_pendientes_mercadeo(vendedor_id=None):
    client = get_client()
    coll = client.collection("pendientes_mercadeo")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r["fecha_reportada"] or "", reverse=True)
    return rows


def create_pendiente_mercadeo(vendedor_id, tienda, fecha_reportada, pendiente, estado):
    get_client().collection("pendientes_mercadeo").document().set({
        "vendedor_id": vendedor_id, "tienda": tienda,
        "fecha_reportada": str(fecha_reportada) if fecha_reportada else None,
        "pendiente": pendiente, "fecha_finalizacion": None, "estado": estado,
    })


def update_pendiente_mercadeo(pendiente_id, **kwargs):
    if kwargs:
        get_client().collection("pendientes_mercadeo").document(pendiente_id).update(kwargs)


def delete_pendiente_mercadeo(pendiente_id):
    get_client().collection("pendientes_mercadeo").document(pendiente_id).delete()


# ---------------------------------------------------------------------------
# Reclamos
# ---------------------------------------------------------------------------
def list_reclamos(vendedor_id=None):
    client = get_client()
    coll = client.collection("reclamos")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r["fecha_reclamo"] or "", reverse=True)
    return rows


def create_reclamo(cliente, nit, numero_orden, fecha_reclamo, estatus, descripcion, vendedor_id):
    get_client().collection("reclamos").document().set({
        "cliente": cliente, "nit": nit, "numero_orden": numero_orden,
        "fecha_reclamo": str(fecha_reclamo), "fecha_solucion": None,
        "estatus": estatus, "descripcion": descripcion, "vendedor_id": vendedor_id,
        "comentarios_jefe_planta": None, "fecha_cierre": None,
    })


def update_reclamo(reclamo_id, **kwargs):
    if kwargs:
        get_client().collection("reclamos").document(reclamo_id).update(kwargs)


def delete_reclamo(reclamo_id):
    get_client().collection("reclamos").document(reclamo_id).delete()


# ---------------------------------------------------------------------------
# Ventas
# ---------------------------------------------------------------------------
def list_ventas(vendedor_id=None, desde=None, hasta=None):
    client = get_client()
    coll = client.collection("ventas")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    if desde:
        rows = [r for r in rows if r["fecha"] >= str(desde)]
    if hasta:
        rows = [r for r in rows if r["fecha"] <= str(hasta)]
    rows.sort(key=lambda r: r["fecha"], reverse=True)
    return rows


def create_venta(vendedor_id, fecha, planta, linea_venta, monto, notas, cliente=None, numero_ordenes=0):
    get_client().collection("ventas").document().set({
        "vendedor_id": vendedor_id, "fecha": str(fecha), "planta": planta,
        "linea_venta": linea_venta, "monto": monto, "notas": notas,
        "cliente": cliente, "numero_ordenes": numero_ordenes,
    })


def update_venta(venta_id, **kwargs):
    if kwargs:
        get_client().collection("ventas").document(venta_id).update(kwargs)


def delete_venta(venta_id):
    get_client().collection("ventas").document(venta_id).delete()


# ---------------------------------------------------------------------------
# Diseño Gráfico (tablero estilo Trello)
# ---------------------------------------------------------------------------
def list_disenos(vendedor_id=None):
    """Retorna las solicitudes de diseño, más nuevas primero."""
    client = get_client()
    coll = client.collection("disenos")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r.get("creado_en") or "", reverse=True)
    return rows


def get_diseno(diseno_id):
    snap = get_client().collection("disenos").document(diseno_id).get()
    return _doc_to_dict(snap) if snap.exists else None
  
def create_diseno(
    vendedor_id, cliente, producto, material, acabado, medida, fecha_necesaria, estado,
    archivo_nombre=None, archivo_tipo=None, archivo_b64=None, cambios_necesarios=None,
):
    get_client().collection("disenos").document().set({
        "vendedor_id": vendedor_id, "cliente": cliente, "producto": producto,
        "material": material, "acabado": acabado, "medida": medida,
        "fecha_necesaria": str(fecha_necesaria) if fecha_necesaria else None,
        "estado": estado, "creado_en": datetime.now().isoformat(timespec="seconds"),
        "archivo_nombre": archivo_nombre, "archivo_tipo": archivo_tipo, "archivo_b64": archivo_b64,
        "cambios_necesarios": cambios_necesarios,
  
    })


def update_diseno(diseno_id, **kwargs):
    if kwargs:
        get_client().collection("disenos").document(diseno_id).update(kwargs)


def delete_diseno(diseno_id):
    get_client().collection("disenos").document(diseno_id).delete()
