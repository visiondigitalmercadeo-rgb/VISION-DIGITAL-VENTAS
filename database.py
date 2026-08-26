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

import math
import os
from datetime import date, datetime, timedelta, timezone

import bcrypt
import firebase_admin
from firebase_admin import credentials, firestore

import fake_firestore
from config import (
    BASE_DIR, CHECKLIST_DEFAULT, LITO_MAQUINAS_INICIAL, LITO_PAPELES_INICIAL, LOGISTICA_VENDEDORES_INICIAL,
)

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
        # NOTA: se apunta explícitamente a la base de datos "vision-digital-ventas-2"
        # (en vez de la "(default)") porque la base "(default)" del proyecto quedó
        # con un problema de conexión desde el lado de Google tras activar el plan
        # Blaze (error "Invalid database id (default)"). Los datos originales ya
        # fueron migrados (exportados e importados) a esta base nueva, que funciona
        # con normalidad. Si en el futuro Firebase confirma que "(default)" volvió
        # a funcionar, se puede quitar el parámetro database_id para volver a usarla.
        _client = firestore.client(database_id="vision-digital-ventas-2")
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
    _seed_logistica_vendedores(client)
    _seed_lito_catalogos(client)


def _seed_logistica_vendedores(client):
    """Carga la lista inicial de LOGISTICA_VENDEDORES_INICIAL (config.py) en
    la colección 'logistica_vendedores' la primera vez que arranca la app —
    independiente de si ya hay usuarios, para que este agregado funcione
    aunque la plataforma ya esté en uso."""
    existentes = list(client.collection("logistica_vendedores").limit(1).stream())
    if existentes:
        return
    for nombre in LOGISTICA_VENDEDORES_INICIAL:
        client.collection("logistica_vendedores").document().set({
            "nombre": nombre, "activo": True,
            "creado_en": datetime.now().isoformat(timespec="seconds"),
        })


def _seed_lito_catalogos(client):
    """Carga máquinas y papel DE EJEMPLO (LITO_MAQUINAS_INICIAL / LITO_PAPELES_INICIAL
    en config.py) la primera vez que arranca la app, para que el cotizador de
    Litografía no empiece vacío. Son solo ejemplos — hay que corregir precios
    y medidas reales desde la pestaña de Litografía."""
    existentes_m = list(client.collection("lito_maquinas").limit(1).stream())
    if not existentes_m:
        for m in LITO_MAQUINAS_INICIAL:
            client.collection("lito_maquinas").document().set({
                **m, "activo": True,
                "creado_en": datetime.now().isoformat(timespec="seconds"),
            })
    existentes_p = list(client.collection("lito_papeles").limit(1).stream())
    if not existentes_p:
        for p in LITO_PAPELES_INICIAL:
            client.collection("lito_papeles").document().set({
                **p, "activo": True,
                "creado_en": datetime.now().isoformat(timespec="seconds"),
            })


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


def list_logistica_vendedores(solo_activos=True):
    """Vendedores adicionales, sin usuario propio, que se pueden elegir como
    'vendedor que hizo la venta' en un pedido de Logística (ver
    LOGISTICA_VENDEDORES_INICIAL en config.py). Se combinan con
    list_vendedores() en la pestaña de Logística."""
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("logistica_vendedores").stream()]
    if solo_activos:
        rows = [r for r in rows if r.get("activo", True)]
    rows.sort(key=lambda r: r.get("nombre") or "")
    return rows


def create_logistica_vendedor(nombre):
    get_client().collection("logistica_vendedores").document().set({
        "nombre": nombre.strip(), "activo": True,
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def set_logistica_vendedor_activo(vendedor_id, activo):
    get_client().collection("logistica_vendedores").document(vendedor_id).update({"activo": bool(activo)})


def delete_logistica_vendedor(vendedor_id):
    get_client().collection("logistica_vendedores").document(vendedor_id).delete()


def list_repartidores(solo_activos=True):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("usuarios").where("rol", "==", "repartidor").stream()]
    if solo_activos:
        rows = [r for r in rows if r["activo"]]
    rows.sort(key=lambda r: r["nombre"])
    return rows


def create_usuario(nombre, username, password, rol, tienda=None):
    client = get_client()
    client.collection("usuarios").document().set({
        "nombre": nombre, "username": username, "password_hash": hash_password(password),
        "rol": rol, "activo": True, "fecha_creacion": str(date.today()), "tienda": tienda,
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
# Registros CF (Consumidor Final) — registros adicionales de facturación
# dentro de un mismo prospecto. Un prospecto puede tener una cantidad
# ilimitada de estos registros (por ejemplo, distintas razones sociales o
# ventas facturadas a "Consumidor Final" asociadas al mismo cliente).
# ---------------------------------------------------------------------------
def list_registros_cf(prospecto_id):
    client = get_client()
    rows = [
        _doc_to_dict(s) for s in client.collection("registros_cf")
        .where("prospecto_id", "==", prospecto_id).stream()
    ]
    rows.sort(key=lambda r: r.get("fecha_registro") or "", reverse=True)
    return rows


def create_registro_cf(prospecto_id, nombre_cliente, nit_cf, telefono, email, direccion):
    get_client().collection("registros_cf").document().set({
        "prospecto_id": prospecto_id, "nombre_cliente": nombre_cliente, "nit_cf": nit_cf.strip(),
        "telefono": telefono, "email": email, "direccion": direccion,
        "fecha_registro": str(date.today()),
    })


def delete_registro_cf(registro_id):
    """Elimina un registro CF por completo (no se puede deshacer)."""
    get_client().collection("registros_cf").document(registro_id).delete()


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
# Venta mensual por planta (monto acumulado del mes, por vendedor — lo
# digita manualmente el administrador, no se calcula de las ventas diarias)
# ---------------------------------------------------------------------------
def get_ventas_mensuales_planta(anio_mes):
    """Retorna {vendedor_id: {"vendedor_id", "anio_mes", "montos": {planta: monto}, ...}}
    para el mes indicado (formato 'YYYY-MM')."""
    client = get_client()
    rows = [
        _doc_to_dict(s)
        for s in client.collection("ventas_mensuales_planta").where("anio_mes", "==", anio_mes).stream()
    ]
    return {r["vendedor_id"]: r for r in rows}


def upsert_venta_mensual_planta(vendedor_id, anio_mes, montos):
    """montos: dict {planta: monto}, ej. {"Offset": 1000, "Digital": 500, "Valloy": 0, "Colorado": 200}.
    Si ya existe un registro para ese vendedor y mes, lo reemplaza; si no, lo crea."""
    client = get_client()
    existentes = list(
        client.collection("ventas_mensuales_planta")
        .where("vendedor_id", "==", vendedor_id)
        .where("anio_mes", "==", anio_mes)
        .stream()
    )
    data = {
        "vendedor_id": vendedor_id, "anio_mes": anio_mes, "montos": montos,
        "actualizado_en": datetime.now().isoformat(timespec="seconds"),
    }
    if existentes:
        client.collection("ventas_mensuales_planta").document(existentes[0].id).set(data)
    else:
        client.collection("ventas_mensuales_planta").document().set(data)


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
    archivos=None, cambios_necesarios=None,
):
    """archivos: lista de hasta 3 dicts {"nombre", "tipo", "b64"}."""
    get_client().collection("disenos").document().set({
        "vendedor_id": vendedor_id, "cliente": cliente, "producto": producto,
        "material": material, "acabado": acabado, "medida": medida,
        "fecha_necesaria": str(fecha_necesaria) if fecha_necesaria else None,
        "estado": estado, "creado_en": datetime.now().isoformat(timespec="seconds"),
        "archivos": archivos or [],
        "cambios_necesarios": cambios_necesarios, "detenido_emergencia": False,
    })


def update_diseno(diseno_id, **kwargs):
    if kwargs:
        get_client().collection("disenos").document(diseno_id).update(kwargs)


def delete_diseno(diseno_id):
    get_client().collection("disenos").document(diseno_id).delete()


# ---------------------------------------------------------------------------
# Diseño Gráfico — Álvaro (tablero independiente, mismo sistema que el de
# Nicolás pero con su propia colección, para que las solicitudes no se mezclen)
# ---------------------------------------------------------------------------
def list_disenos_alvaro(vendedor_id=None):
    """Retorna las solicitudes de diseño de Álvaro, más nuevas primero."""
    client = get_client()
    coll = client.collection("disenos_alvaro")
    query = coll.where("vendedor_id", "==", vendedor_id) if vendedor_id else coll
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r.get("creado_en") or "", reverse=True)
    return rows


def get_diseno_alvaro(diseno_id):
    snap = get_client().collection("disenos_alvaro").document(diseno_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_diseno_alvaro(
    vendedor_id, cliente, producto, material, acabado, medida, fecha_necesaria, estado,
    archivos=None, cambios_necesarios=None,
):
    """archivos: lista de hasta 3 dicts {"nombre", "tipo", "b64"}."""
    get_client().collection("disenos_alvaro").document().set({
        "vendedor_id": vendedor_id, "cliente": cliente, "producto": producto,
        "material": material, "acabado": acabado, "medida": medida,
        "fecha_necesaria": str(fecha_necesaria) if fecha_necesaria else None,
        "estado": estado, "creado_en": datetime.now().isoformat(timespec="seconds"),
        "archivos": archivos or [],
        "cambios_necesarios": cambios_necesarios, "detenido_emergencia": False,
    })


def update_diseno_alvaro(diseno_id, **kwargs):
    if kwargs:
        get_client().collection("disenos_alvaro").document(diseno_id).update(kwargs)


def delete_diseno_alvaro(diseno_id):
    get_client().collection("disenos_alvaro").document(diseno_id).delete()


# ---------------------------------------------------------------------------
# Logística (pedidos AM/PM de la ruta de reparto)
# ---------------------------------------------------------------------------
def list_pedidos(fecha=None, franja=None, repartidor_id=None, vendedor_id=None):
    client = get_client()
    query = client.collection("pedidos")
    if fecha:
        query = query.where("fecha", "==", str(fecha))
    if franja:
        query = query.where("franja", "==", franja)
    if repartidor_id:
        query = query.where("repartidor_id", "==", repartidor_id)
    if vendedor_id:
        query = query.where("vendedor_id", "==", vendedor_id)
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r.get("creado_en") or "", reverse=True)
    return rows


def get_pedido(pedido_id):
    snap = get_client().collection("pedidos").document(pedido_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def _siguiente_numero_envio():
    """Numeración corrida (no reinicia por día), empezando en 1 — el 'ENVÍO
    No.' que aparece impreso en el PDF de cada pedido, igual que la libreta
    física de envíos que se usaba en papel."""
    rows = [_doc_to_dict(s) for s in get_client().collection("pedidos").stream()]
    numeros = [r.get("numero_envio") for r in rows if isinstance(r.get("numero_envio"), int)]
    return (max(numeros, default=0)) + 1


def create_pedido(
    fecha, franja, cliente, direccion, zona, producto, numero_orden,
    vendedor_id, repartidor_id, notas=None, tipo_ruta=None, atencion_a=None, productos=None,
):
    get_client().collection("pedidos").document().set({
        "fecha": str(fecha), "franja": franja, "cliente": cliente, "direccion": direccion,
        "zona": zona, "producto": producto, "numero_orden": numero_orden,
        "vendedor_id": vendedor_id, "repartidor_id": repartidor_id,
        "estado": "Pendiente", "notas": notas, "tipo_ruta": tipo_ruta,
        "atencion_a": atencion_a, "productos": productos or [],
        "numero_envio": _siguiente_numero_envio(),
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_pedido(pedido_id, **kwargs):
    if kwargs:
        get_client().collection("pedidos").document(pedido_id).update(kwargs)


def delete_pedido(pedido_id):
    get_client().collection("pedidos").document(pedido_id).delete()


# ---------------------------------------------------------------------------
# Rutas extra de Logística: Compras, Trámites y Papelería — versión sencilla
# de "pedido" (sin cliente/zona/franja/productos), usada para mandados del
# repartidor que no son un envío de mercadería. Las 3 comparten la misma
# colección ("rutas_extra"), diferenciadas por el campo "tipo".
# ---------------------------------------------------------------------------
def list_rutas_extra(tipo=None, repartidor_id=None):
    client = get_client()
    query = client.collection("rutas_extra")
    if tipo:
        query = query.where("tipo", "==", tipo)
    if repartidor_id:
        query = query.where("repartidor_id", "==", repartidor_id)
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r.get("fecha") or "", reverse=True)
    return rows


def get_ruta_extra(ruta_id):
    snap = get_client().collection("rutas_extra").document(ruta_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_ruta_extra(tipo, fecha, empresa, descripcion, repartidor_id):
    get_client().collection("rutas_extra").document().set({
        "tipo": tipo, "fecha": str(fecha), "empresa": empresa, "descripcion": descripcion,
        "repartidor_id": repartidor_id, "estado": "Pendiente",
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_ruta_extra(ruta_id, **kwargs):
    if kwargs:
        get_client().collection("rutas_extra").document(ruta_id).update(kwargs)


def delete_ruta_extra(ruta_id):
    get_client().collection("rutas_extra").document(ruta_id).delete()


# ---------------------------------------------------------------------------
# Capacitación — personal por tienda
# ---------------------------------------------------------------------------
def list_personal_tiendas(tienda=None, solo_activos=True):
    client = get_client()
    query = client.collection("personal_tiendas")
    if tienda:
        query = query.where("tienda", "==", tienda)
    rows = [_doc_to_dict(s) for s in query.stream()]
    if solo_activos:
        rows = [r for r in rows if r.get("activo", True)]
    rows.sort(key=lambda r: (r.get("tienda") or "", r.get("nombre") or ""))
    return rows


def get_personal_tienda(persona_id):
    snap = get_client().collection("personal_tiendas").document(persona_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_personal_tienda(nombre, tienda, puesto=None):
    get_client().collection("personal_tiendas").document().set({
        "nombre": nombre, "tienda": tienda, "puesto": puesto, "activo": True,
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_personal_tienda(persona_id, **kwargs):
    if kwargs:
        get_client().collection("personal_tiendas").document(persona_id).update(kwargs)


def set_personal_tienda_activo(persona_id, activo):
    get_client().collection("personal_tiendas").document(persona_id).update({"activo": bool(activo)})


def delete_personal_tienda(persona_id):
    """Elimina a la persona del listado. Las calificaciones que ya tenga
    registradas no se borran, solo dejan de estar vinculadas a un nombre visible."""
    get_client().collection("personal_tiendas").document(persona_id).delete()


def nombre_personal_tienda(persona_id, personal=None):
    if not persona_id:
        return "—"
    if personal is None:
        personal = list_personal_tiendas(solo_activos=False)
    for p in personal:
        if p["id"] == persona_id:
            return p["nombre"]
    return "—"


# ---------------------------------------------------------------------------
# Capacitación — módulos y submódulos
# ---------------------------------------------------------------------------
def list_modulos():
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("capacitacion_modulos").stream()]
    rows.sort(key=lambda r: r.get("nombre") or "")
    return rows


def get_modulo(modulo_id):
    snap = get_client().collection("capacitacion_modulos").document(modulo_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_modulo(nombre, descripcion=None):
    get_client().collection("capacitacion_modulos").document().set({
        "nombre": nombre, "descripcion": descripcion,
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_modulo(modulo_id, **kwargs):
    if kwargs:
        get_client().collection("capacitacion_modulos").document(modulo_id).update(kwargs)


def delete_modulo(modulo_id):
    """Elimina el módulo junto con todos sus submódulos y las calificaciones
    (generales y por submódulo) ligadas a él — para no dejar nada huérfano."""
    client = get_client()
    for sub in list_submodulos(modulo_id):
        delete_submodulo(sub["id"])
    for c in list_calificaciones(modulo_id=modulo_id):
        client.collection("capacitacion_calificaciones").document(c["id"]).delete()
    client.collection("capacitacion_modulos").document(modulo_id).delete()


def list_submodulos(modulo_id=None):
    client = get_client()
    query = client.collection("capacitacion_submodulos")
    if modulo_id:
        query = query.where("modulo_id", "==", modulo_id)
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r.get("nombre") or "")
    return rows


def get_submodulo(submodulo_id):
    snap = get_client().collection("capacitacion_submodulos").document(submodulo_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_submodulo(modulo_id, nombre, descripcion=None, archivos=None):
    get_client().collection("capacitacion_submodulos").document().set({
        "modulo_id": modulo_id, "nombre": nombre, "descripcion": descripcion,
        "archivos": archivos or [], "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_submodulo(submodulo_id, **kwargs):
    if kwargs:
        get_client().collection("capacitacion_submodulos").document(submodulo_id).update(kwargs)


def delete_submodulo(submodulo_id):
    client = get_client()
    for c in list_calificaciones(submodulo_id=submodulo_id):
        client.collection("capacitacion_calificaciones").document(c["id"]).delete()
    client.collection("capacitacion_submodulos").document(submodulo_id).delete()


# ---------------------------------------------------------------------------
# Capacitación — calificaciones (una por persona + módulo, o por persona +
# submódulo; siempre reemplaza el valor anterior, no suma).
# ---------------------------------------------------------------------------
def list_calificaciones(modulo_id=None, submodulo_id=None, persona_id=None):
    client = get_client()
    query = client.collection("capacitacion_calificaciones")
    if modulo_id:
        query = query.where("modulo_id", "==", modulo_id)
    if persona_id:
        query = query.where("persona_id", "==", persona_id)
    rows = [_doc_to_dict(s) for s in query.stream()]
    if submodulo_id is not None:
        rows = [r for r in rows if r.get("submodulo_id") == submodulo_id]
    return rows


def get_calificacion(persona_id, modulo_id, submodulo_id=None):
    coincidencias = [
        c for c in list_calificaciones(modulo_id=modulo_id, persona_id=persona_id)
        if c.get("submodulo_id") == submodulo_id
    ]
    return coincidencias[0] if coincidencias else None


def upsert_calificacion(persona_id, modulo_id, submodulo_id, calificacion, notas=None):
    """submodulo_id=None significa que es la calificación general del módulo.
    Si ya existe una calificación para esta persona + módulo (+ submódulo),
    la reemplaza; si no, la crea."""
    existente = get_calificacion(persona_id, modulo_id, submodulo_id)
    data = {
        "persona_id": persona_id, "modulo_id": modulo_id, "submodulo_id": submodulo_id,
        "calificacion": calificacion, "notas": notas,
        "actualizado_en": datetime.now().isoformat(timespec="seconds"),
    }
    client = get_client()
    if existente:
        client.collection("capacitacion_calificaciones").document(existente["id"]).set(data)
    else:
        client.collection("capacitacion_calificaciones").document().set(data)


# ---------------------------------------------------------------------------
# Sistema de Tickets — Tiendas (fila de clientes nuevos, con check-in público
# por QR desde el celular del cliente — no requiere haber iniciado sesión).
# Se mide el tiempo en cada etapa guardando la hora exacta en la que el
# ticket entra a ella: hora_ingreso (check-in), hora_inicio_atencion,
# hora_inicio_elaboracion y hora_facturado.
# ---------------------------------------------------------------------------
_TICKET_TS_POR_ESTADO = {
    "En atención": "hora_inicio_atencion",
    "En elaboración": "hora_inicio_elaboracion",
    "Facturado": "hora_facturado",
    "Abandono": "hora_abandono",
}

# Guatemala usa siempre UTC-6 (no tiene horario de verano), así que un
# desplazamiento fijo es suficiente y no depende de que el servidor donde
# corre Streamlit Cloud tenga instalada la base de datos de zonas horarias.
GUATEMALA_TZ = timezone(timedelta(hours=-6))


def ahora_guatemala():
    """Hora actual en horario de Guatemala, como datetime 'naive' (sin
    información de zona horaria en el valor) para que se guarde y se compare
    siempre igual, sin importar en qué servidor/zona horaria esté corriendo
    la app. Se usa para todo lo relacionado al Sistema de Tickets — Tiendas."""
    return datetime.now(GUATEMALA_TZ).replace(tzinfo=None)


def hoy_guatemala():
    return ahora_guatemala().date()


def _siguiente_numero_ticket(tienda):
    """Numeración diaria por tienda: reinicia en 1 cada día (día de Guatemala)."""
    hoy = str(hoy_guatemala())
    tickets_hoy = [
        t for t in list_tickets_tienda(tienda=tienda) if t.get("fecha") == hoy
    ]
    return (max([t.get("numero_ticket") or 0 for t in tickets_hoy], default=0)) + 1


def create_ticket_tienda(tienda, nombre, telefono, servicio):
    """Crea un ticket nuevo. Esta es la función que usa el formulario público
    de check-in (por QR) — se llama SIN que el cliente haya iniciado sesión.
    'servicio' es una lista (el cliente puede elegir varios productos/servicios
    del catálogo TICKET_SERVICIOS); por compatibilidad también acepta texto
    suelto y lo convierte en una lista de un solo elemento.
    Devuelve el id y el número de ticket asignado, para mostrárselo al cliente."""
    if isinstance(servicio, list):
        servicio_lista = [s for s in servicio if s]
    else:
        servicio_lista = [servicio.strip()] if servicio and servicio.strip() else []
    numero = _siguiente_numero_ticket(tienda)
    doc_ref = get_client().collection("tickets_tienda").document()
    # El ticket entra directo a "En atención" (columna "En espera" del
    # tablero) — ya no existe la etapa intermedia "Esperando"/"Ingresado",
    # así que hora_inicio_atencion queda igual a hora_ingreso.
    ahora = ahora_guatemala().isoformat(timespec="seconds")
    doc_ref.set({
        "tienda": tienda, "fecha": str(hoy_guatemala()), "numero_ticket": numero,
        "nombre": nombre.strip(), "telefono": telefono.strip(), "servicio": servicio_lista,
        "estado": "En atención",
        "hora_ingreso": ahora,
        "hora_inicio_atencion": ahora, "hora_inicio_elaboracion": None, "hora_facturado": None,
        "hora_abandono": None, "motivo_abandono": None, "asesor_id": None,
    })
    return {"id": doc_ref.id, "numero_ticket": numero}


def list_tickets_tienda(tienda=None, fecha=None, activos_solo=False):
    """Tickets 'vivos' (no incluye los que se hayan eliminado — para esos ver
    list_tickets_eliminados)."""
    client = get_client()
    query = client.collection("tickets_tienda")
    if tienda:
        query = query.where("tienda", "==", tienda)
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows = [r for r in rows if not r.get("eliminado")]
    if fecha:
        rows = [r for r in rows if r.get("fecha") == fecha]
    if activos_solo:
        rows = [r for r in rows if r.get("estado") not in ("Facturado", "Abandono")]
    rows.sort(key=lambda r: r.get("hora_ingreso") or "", reverse=True)
    return rows


def list_tickets_eliminados(tienda=None):
    """Todos los tickets que se han eliminado (con motivo, quién y cuándo),
    para el listado de auditoría al final de la pestaña de Tickets — Tiendas."""
    client = get_client()
    query = client.collection("tickets_tienda")
    if tienda:
        query = query.where("tienda", "==", tienda)
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows = [r for r in rows if r.get("eliminado")]
    rows.sort(key=lambda r: r.get("eliminado_en") or "", reverse=True)
    return rows


def get_ticket_tienda(ticket_id):
    snap = get_client().collection("tickets_tienda").document(ticket_id).get()
    return _doc_to_dict(snap) if snap.exists else None


_SIN_CAMBIO_ASESOR = object()


def avanzar_ticket_tienda(ticket_id, nuevo_estado, asesor_id=_SIN_CAMBIO_ASESOR):
    """Cambia el estado del ticket y, si corresponde, registra la hora exacta
    en la que entró a esa etapa (para poder medir cuánto tiempo pasó en cada
    una: espera, elaboración, etc.). Si se pasa 'asesor_id' (por ejemplo al
    pasar a 'En elaboración'), también queda asignada esa persona (un id de
    "personal_tiendas") al ticket; si no se pasa, la persona ya asignada no
    se toca."""
    cambios = {"estado": nuevo_estado}
    campo_ts = _TICKET_TS_POR_ESTADO.get(nuevo_estado)
    if campo_ts:
        cambios[campo_ts] = ahora_guatemala().isoformat(timespec="seconds")
    if asesor_id is not _SIN_CAMBIO_ASESOR:
        cambios["asesor_id"] = asesor_id
    get_client().collection("tickets_tienda").document(ticket_id).update(cambios)


def abandonar_ticket_tienda(ticket_id, motivo=None):
    """Marca el ticket como 'Abandono' (el cliente no completó su proceso, por
    la razón que sea) y guarda el motivo junto con la hora exacta."""
    get_client().collection("tickets_tienda").document(ticket_id).update({
        "estado": "Abandono",
        "hora_abandono": ahora_guatemala().isoformat(timespec="seconds"),
        "motivo_abandono": (motivo or "").strip() or None,
    })


def eliminar_ticket_tienda(ticket_id, motivo, eliminado_por=None):
    """'Elimina' un ticket del tablero (deja de aparecer ahí y en el
    historial), pero NO lo borra de la base de datos: lo marca como
    eliminado y guarda el motivo, quién lo eliminó y cuándo, para que quede
    un registro de auditoría (ver list_tickets_eliminados)."""
    get_client().collection("tickets_tienda").document(ticket_id).update({
        "eliminado": True,
        "motivo_eliminacion": (motivo or "").strip() or None,
        "eliminado_por": eliminado_por,
        "eliminado_en": ahora_guatemala().isoformat(timespec="seconds"),
    })


def update_ticket_tienda(ticket_id, **kwargs):
    if kwargs:
        get_client().collection("tickets_tienda").document(ticket_id).update(kwargs)


_TICKET_KPI_DEFAULT = {"meta_espera": None, "meta_atencion": None, "meta_elaboracion": None}


def get_ticket_kpis(tienda):
    """Tiempos meta (en minutos) configurados para una tienda, para cada
    etapa del Sistema de Tickets — Tiendas: 'meta_atencion' (En espera, antes
    de pasar a elaboración) y 'meta_elaboracion' (En elaboración, antes de
    facturar). 'meta_espera' ya no se usa (existía para la etapa
    "Ingresado", que se eliminó) — se deja en el registro solo por
    compatibilidad con datos antiguos. Si todavía no se ha configurado nada
    para esa tienda, los valores vienen en None (sin meta) y no se pinta
    nada en rojo."""
    snap = get_client().collection("tickets_kpis_metas").document(tienda).get()
    if not snap.exists:
        return dict(_TICKET_KPI_DEFAULT)
    data = _doc_to_dict(snap)
    return {
        "meta_espera": data.get("meta_espera"),
        "meta_atencion": data.get("meta_atencion"),
        "meta_elaboracion": data.get("meta_elaboracion"),
    }


def set_ticket_kpis(tienda, meta_espera, meta_atencion, meta_elaboracion):
    """Guarda (o corrige) los tiempos meta de una tienda. Cada valor es en
    minutos, o None para dejar esa etapa sin meta."""
    get_client().collection("tickets_kpis_metas").document(tienda).set({
        "tienda": tienda, "meta_espera": meta_espera,
        "meta_atencion": meta_atencion, "meta_elaboracion": meta_elaboracion,
    })


def delete_ticket_tienda(ticket_id):
    """Elimina un ticket de la base de datos por completo y sin dejar
    rastro (no se puede deshacer). No se usa desde la pestaña de Tickets —
    ahí se usa eliminar_ticket_tienda(), que sí deja un registro de
    auditoría; esta función queda disponible para una limpieza manual de
    datos si algún día hace falta."""
    get_client().collection("tickets_tienda").document(ticket_id).delete()


# ---------------------------------------------------------------------------
# Mantenimiento de Maquinaria (por planta): cada máquina/impresora es un
# registro en "maquinas"; sus mantenimientos (preventivos y correctivos) son
# registros en "mantenimientos_maquinas", ligados por "maquina_id".
# ---------------------------------------------------------------------------
def list_maquinas(planta=None, solo_activas=False):
    client = get_client()
    query = client.collection("maquinas")
    if planta:
        query = query.where("planta", "==", planta)
    rows = [_doc_to_dict(s) for s in query.stream()]
    if solo_activas:
        rows = [r for r in rows if r.get("activa", True)]
    rows.sort(key=lambda r: r.get("nombre") or "")
    return rows


def get_maquina(maquina_id):
    snap = get_client().collection("maquinas").document(maquina_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_maquina(nombre, tipo_maquina, planta, numero_serie=None, notas=None, codigo_alterno_gasto=None):
    doc_ref = get_client().collection("maquinas").document()
    doc_ref.set({
        "nombre": nombre.strip(), "tipo_maquina": (tipo_maquina or "").strip() or None,
        "planta": planta, "numero_serie": (numero_serie or "").strip() or None,
        "codigo_alterno_gasto": (codigo_alterno_gasto or "").strip() or None,
        "notas": (notas or "").strip() or None, "activa": True,
        "creado_en": ahora_guatemala().isoformat(timespec="seconds"),
    })
    return doc_ref.id


def update_maquina(maquina_id, **kwargs):
    if kwargs:
        get_client().collection("maquinas").document(maquina_id).update(kwargs)


def delete_maquina(maquina_id):
    """Elimina la máquina junto con todo su historial de mantenimientos
    (preventivos y correctivos), para no dejar registros huérfanos."""
    client = get_client()
    for m in list_mantenimientos_maquina(maquina_id):
        client.collection("mantenimientos_maquinas").document(m["id"]).delete()
    client.collection("maquinas").document(maquina_id).delete()


def list_mantenimientos_maquina(maquina_id, tipo=None):
    """Historial de mantenimientos de una máquina (preventivos y
    correctivos juntos, o solo uno de los dos tipos si se especifica
    'tipo'), más recientes primero."""
    client = get_client()
    rows = [
        _doc_to_dict(s)
        for s in client.collection("mantenimientos_maquinas").where("maquina_id", "==", maquina_id).stream()
    ]
    if tipo:
        rows = [r for r in rows if r.get("tipo") == tipo]
    rows.sort(key=lambda r: r.get("fecha") or "", reverse=True)
    return rows


def get_mantenimiento(mantenimiento_id):
    snap = get_client().collection("mantenimientos_maquinas").document(mantenimiento_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def list_mantenimientos_todos():
    """Todos los mantenimientos (preventivos y correctivos) de todas las
    máquinas, sin filtrar por una sola — para los KPIs y alertas generales
    de la pantalla principal de Mantenimiento de Maquinaria."""
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("mantenimientos_maquinas").stream()]
    rows.sort(key=lambda r: r.get("fecha") or "", reverse=True)
    return rows


def create_mantenimiento(maquina_id, tipo, **campos):
    """Crea un registro de mantenimiento ('Preventivo' o 'Correctivo') para
    una máquina. 'campos' admite: fecha, proveedor, costo, repuesto_cambiado,
    tiempo_garantia, numero_factura, notas, factura_nombre/tipo/b64,
    foto_repuesto_nombre/tipo/b64, realizado (solo aplica a 'Preventivo' —
    si ya se llevó a cabo el mantenimiento programado)."""
    doc_ref = get_client().collection("mantenimientos_maquinas").document()
    data = {
        "maquina_id": maquina_id, "tipo": tipo,
        "creado_en": ahora_guatemala().isoformat(timespec="seconds"),
    }
    data.update(campos)
    doc_ref.set(data)
    return doc_ref.id


def update_mantenimiento(mantenimiento_id, **kwargs):
    if kwargs:
        get_client().collection("mantenimientos_maquinas").document(mantenimiento_id).update(kwargs)


def delete_mantenimiento(mantenimiento_id):
    get_client().collection("mantenimientos_maquinas").document(mantenimiento_id).delete()


# ---------------------------------------------------------------------------
# Litografía: catálogo de máquinas y papel (con precios), y cotizaciones
# técnicas — la ficha de especificación de un trabajo (formato, tintas,
# páginas, papel, máquina) con cálculo automático de pliegos, planchas,
# pasadas de máquina y costo total. Inspirado en sistemas como Logic Print.
# ---------------------------------------------------------------------------
def list_lito_maquinas(solo_activos=True):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("lito_maquinas").stream()]
    if solo_activos:
        rows = [r for r in rows if r.get("activo", True)]
    rows.sort(key=lambda r: r.get("nombre") or "")
    return rows


def get_lito_maquina(maquina_id):
    if not maquina_id:
        return None
    snap = get_client().collection("lito_maquinas").document(maquina_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_lito_maquina(nombre, ancho_max, alto_max, costo_millar_pasadas, costo_plancha):
    get_client().collection("lito_maquinas").document().set({
        "nombre": nombre.strip(), "ancho_max": float(ancho_max), "alto_max": float(alto_max),
        "costo_millar_pasadas": float(costo_millar_pasadas), "costo_plancha": float(costo_plancha),
        "activo": True, "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_lito_maquina(maquina_id, **kwargs):
    if kwargs:
        get_client().collection("lito_maquinas").document(maquina_id).update(kwargs)


def delete_lito_maquina(maquina_id):
    get_client().collection("lito_maquinas").document(maquina_id).delete()


def list_lito_papeles(solo_activos=True):
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("lito_papeles").stream()]
    if solo_activos:
        rows = [r for r in rows if r.get("activo", True)]
    rows.sort(key=lambda r: r.get("tipo") or "")
    return rows


def get_lito_papel(papel_id):
    if not papel_id:
        return None
    snap = get_client().collection("lito_papeles").document(papel_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_lito_papel(tipo, fabricante, gramaje, ancho, alto, costo_pliego):
    get_client().collection("lito_papeles").document().set({
        "tipo": tipo.strip(), "fabricante": fabricante.strip(), "gramaje": float(gramaje),
        "ancho": float(ancho), "alto": float(alto), "costo_pliego": float(costo_pliego),
        "activo": True, "creado_en": datetime.now().isoformat(timespec="seconds"),
    })


def update_lito_papel(papel_id, **kwargs):
    if kwargs:
        get_client().collection("lito_papeles").document(papel_id).update(kwargs)


def delete_lito_papel(papel_id):
    get_client().collection("lito_papeles").document(papel_id).delete()


def _siguiente_numero_lito():
    """Numeración corrida (no reinicia por día) para las cotizaciones
    técnicas de Litografía — ej. LIT-0001, LIT-0002, ..."""
    rows = [_doc_to_dict(s) for s in get_client().collection("lito_cotizaciones").stream()]
    numeros = [r.get("numero") for r in rows if isinstance(r.get("numero"), int)]
    return (max(numeros, default=0)) + 1


def list_lito_cotizaciones():
    client = get_client()
    rows = [_doc_to_dict(s) for s in client.collection("lito_cotizaciones").stream()]
    rows.sort(key=lambda r: r.get("numero") or 0, reverse=True)
    return rows


def get_lito_cotizacion(cotizacion_id):
    if not cotizacion_id:
        return None
    snap = get_client().collection("lito_cotizaciones").document(cotizacion_id).get()
    return _doc_to_dict(snap) if snap.exists else None


def create_lito_cotizacion(**campos):
    """Crea una cotización técnica de Litografía. 'campos' admite: cliente,
    nit, descripcion, cantidad, merma_pct, margen_pct, componentes (lista de
    dicts, uno por cada parte del trabajo — ej. Cubierta e Interior — con sus
    especificaciones y los resultados ya calculados), acabados (lista de
    {descripcion, costo}), costo_total, precio_sugerido, estado, notas,
    creado_por."""
    numero = _siguiente_numero_lito()
    doc_ref = get_client().collection("lito_cotizaciones").document()
    data = {
        "numero": numero,
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    }
    data.update(campos)
    doc_ref.set(data)
    return {"id": doc_ref.id, "numero": numero}


def update_lito_cotizacion(cotizacion_id, **kwargs):
    if kwargs:
        get_client().collection("lito_cotizaciones").document(cotizacion_id).update(kwargs)


def delete_lito_cotizacion(cotizacion_id):
    get_client().collection("lito_cotizaciones").document(cotizacion_id).delete()
