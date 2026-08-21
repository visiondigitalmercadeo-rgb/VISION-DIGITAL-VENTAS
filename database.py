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
    global
