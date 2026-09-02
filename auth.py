import base64
from datetime import datetime, timedelta

import streamlit as st
from streamlit_cookies_controller import CookieController

import database as db
from config import EMPRESA_LEMA, EMPRESA_NOMBRE, LOGO_PATH

# Nombre de la cookie donde se guarda el token de "recuérdame" — para que,
# una vez que alguien inicia sesión, la plataforma no lo vuelva a sacar hasta
# que él mismo cierre sesión (ni siquiera si la app se reinicia por un nuevo
# despliegue, o cierra y vuelve a abrir el navegador).
_COOKIE_SESION = "vd_sesion"


def _cookies():
    """Controlador de cookies del navegador — una sola instancia por sesión
    de Streamlit (se cachea sola en session_state, ver CookieController)."""
    return CookieController()


def _sincronizar_usuario_sesion(user):
    st.session_state["user"] = {
        "id": user["id"],
        "nombre": user["nombre"],
        "username": user["username"],
        "rol": user["rol"],
        "tienda": user.get("tienda"),
        "paginas_extra": user.get("paginas_extra") or [],
    }


def _logo_centrado(path, width):
    """st.image() alinea la imagen a la izquierda de su columna aunque el
    texto de al lado esté centrado — para el logo del login se ve mejor
    centrarlo de verdad, incrustándolo como <img> dentro de un <div>
    centrado."""
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='data:image/png;base64,{b64}' width='{width}' /></div>",
            unsafe_allow_html=True,
        )
    except Exception:
        st.image(path, width=width)


def do_login(username: str, password: str) -> bool:
    user = db.get_user_by_username(username.strip().lower())
    if not user or not user["activo"]:
        return False
    if not db.check_password(password, user["password_hash"]):
        return False
    _sincronizar_usuario_sesion(user)
    # Guarda un token de "recuérdame" en una cookie del navegador, para que
    # esta sesión sobreviva un refresh, cerrar y abrir el navegador, o que la
    # plataforma se reinicie por un nuevo despliegue — hasta que la persona
    # cierre sesión ella misma. Si la cookie falla por cualquier motivo (ej.
    # el navegador la bloquea), el inicio de sesión normal sigue funcionando
    # igual, solo que sin "recordar" para la próxima vez.
    try:
        token = db.crear_sesion_recordada(user["id"])
        _cookies().set(
            _COOKIE_SESION, token, expires=datetime.now() + timedelta(days=db.SESION_RECORDAR_DIAS),
        )
    except Exception:
        pass
    return True


def do_logout():
    try:
        controller = _cookies()
        token = controller.get(_COOKIE_SESION)
        if token:
            db.eliminar_sesion_recordada(token)
        controller.remove(_COOKIE_SESION)
    except Exception:
        pass
    st.session_state.pop("user", None)


def current_user():
    return st.session_state.get("user")


def require_login():
    """Muestra el formulario de login si no hay sesión activa. Debe llamarse
    al inicio de app.py. Devuelve True si hay un usuario autenticado.

    Antes de pedir usuario/contraseña, revisa si ya hay una cookie de
    "recuérdame" válida en el navegador (de un inicio de sesión anterior) —
    si la hay, entra directo sin pedir nada, para que la sesión de admin (o
    cualquier usuario) no se cierre sola nunca, salvo que la persona cierre
    sesión a propósito."""
    controller = None
    try:
        controller = _cookies()
    except Exception:
        controller = None

    if current_user():
        return True

    if controller is not None:
        try:
            token = controller.get(_COOKIE_SESION)
        except Exception:
            token = None
        if token:
            user = db.usuario_desde_token_sesion(token)
            if user:
                _sincronizar_usuario_sesion(user)
                return True

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        _logo_centrado(LOGO_PATH, 320)
        st.markdown(
            f"<h3 style='text-align:center;margin-top:0.5rem;'>{EMPRESA_NOMBRE} · Plataforma Comercial</h3>"
            f"<p style='text-align:center;color:#52514e;'>{EMPRESA_LEMA} · "
            "Citas · CRM · Cotizaciones · Reclamos · Ventas · KPIs</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True)
            if submitted:
                if do_login(username, password):
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos, o el usuario está inactivo.")
        with st.expander("Usuarios de demostración"):
            st.markdown(
                "- **admin** / admin123 — Administrador\n"
                "- **vista** / vista123 — Solo vista\n"
                "- **juan** / vendedor123 — Vendedor\n"
                "- **maria** / vendedor123 — Vendedor\n"
                "- **carlos** / vendedor123 — Vendedor"
            )
    return False


def is_admin():
    u = current_user()
    return u is not None and u["rol"] == "admin"


def is_vendedor():
    u = current_user()
    return u is not None and u["rol"] == "vendedor"


def is_vista():
    u = current_user()
    return u is not None and u["rol"] == "vista"


def is_mercadeo():
    u = current_user()
    return u is not None and u["rol"] == "mercadeo"


def is_jefe_planta():
    u = current_user()
    return u is not None and u["rol"] == "jefe_planta"


def is_disenador():
    u = current_user()
    return u is not None and u["rol"] == "disenador"


def is_disenador_alvaro():
    u = current_user()
    return u is not None and u["rol"] == "disenador_alvaro"


def is_jefe_logistica():
    u = current_user()
    return u is not None and u["rol"] == "jefe_logistica"


def is_repartidor():
    u = current_user()
    return u is not None and u["rol"] == "repartidor"


def is_jefe_capacitacion():
    u = current_user()
    return u is not None and u["rol"] == "jefe_capacitacion"


def is_asistente_capacitacion():
    u = current_user()
    return u is not None and u["rol"] == "asistente_capacitacion"


def puede_editar_capacitacion():
    """Admin, jefe de capacitación y asistente de capacitación tienen el mismo
    nivel de permiso dentro de la pestaña de Capacitación (crear/editar
    módulos, submódulos, personal y calificaciones)."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "jefe_capacitacion", "asistente_capacitacion")


def is_anfitriona():
    u = current_user()
    return u is not None and u["rol"] == "anfitriona"


def is_jefe_tienda():
    u = current_user()
    return u is not None and u["rol"] == "jefe_tienda"


def is_asesor_ventas():
    u = current_user()
    return u is not None and u["rol"] == "asesor_ventas"


def is_cajero():
    u = current_user()
    return u is not None and u["rol"] == "cajero"


def is_subjefe_tienda():
    u = current_user()
    return u is not None and u["rol"] == "subjefe_tienda"


def puede_gestionar_tickets_tienda():
    """Admin y todos los roles de tienda con usuario (anfitriona, jefe de
    tienda, sub jefe de tienda, asesor de ventas, cajero) tienen el mismo
    nivel de permiso dentro del Sistema de Tickets — Tiendas (ver y avanzar
    los tickets de la fila, incluyendo marcarlos como Facturado), igual que
    se hizo con capacitación. El resto del personal de tienda (acabados,
    express) no tiene usuario propio — solo aparece como nombre asignado a
    su tienda para poder elegir quién elabora un pedido."""
    u = current_user()
    return u is not None and u["rol"] in (
        "admin", "anfitriona", "jefe_tienda", "subjefe_tienda", "asesor_ventas", "cajero",
    )


def puede_gestionar_mantenimiento():
    """Admin y jefe de planta pueden registrar máquinas y mantenimientos; el
    resto de roles que llegan a esta pestaña (vendedor, vista) solo pueden
    consultar el historial."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "jefe_planta")


def puede_configurar_kpis_tienda():
    """Admin y mercadeo son los únicos que pueden establecer los tiempos meta
    (KPIs) del Sistema de Tickets — Tiendas; el resto de roles de tienda
    (asesor, cajero, jefe de tienda) solo pueden verlos."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "mercadeo")


def current_user_tienda():
    """Tienda asignada al usuario en sesión (solo aplica a los roles de
    tienda: anfitriona, jefe_tienda, asesor_ventas). None para admin u otros
    roles, que ven todas las tiendas."""
    u = current_user()
    return u.get("tienda") if u else None


def can_edit():
    """Admin, vendedor y mercadeo pueden crear/editar (el rol 'mercadeo' solo
    tiene acceso a la pestaña de Visitas de mercadeo, restringido en app.py);
    el rol 'vista' es solo lectura. El rol 'jefe_planta' tiene un permiso
    aparte, más limitado, definido directamente en la página de Reclamos."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "vendedor", "mercadeo")


def is_cotizadora():
    u = current_user()
    return u is not None and u["rol"] == "cotizadora"


def puede_gestionar_litografia():
    """Quién puede crear, editar y eliminar cotizaciones técnicas en el
    cotizador de Litografía — admin y vendedor, que son quienes cotizan
    trabajos con clientes, y 'cotizadora', el rol dedicado exclusivamente a
    este cotizador. El rol 'vista' solo puede consultar."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "vendedor", "cotizadora")


def puede_administrar_catalogos_litografia():
    """Quién puede agregar, editar o desactivar máquinas y tipos de papel del
    catálogo de Litografía — ahí viven los precios y capacidades técnicas que
    usa el cálculo de costo, así que se restringe más que la creación de
    cotizaciones: admin y 'cotizadora' (que tiene control total del
    cotizador, pero solo de esa pestaña)."""
    u = current_user()
    return u is not None and u["rol"] in ("admin", "cotizadora")


def is_jefe_mantenimiento():
    u = current_user()
    return u is not None and u["rol"] == "jefe_mantenimiento"


def puede_crear_mant_tiendas():
    """Quién puede crear (abrir) solicitudes en el tablero de Mantenimiento
    de Tiendas — admin, jefe de tienda, sub jefe de tienda y mercadeo tienen
    acceso total a esta pestaña (crear, editar, mover y eliminar cualquier
    solicitud); son quienes detectan y reportan qué hay que arreglar en su
    sucursal (mismo concepto que 'vendedor' en el tablero de Diseño
    Gráfico). 'jefe_mantenimiento' también puede abrir solicitudes él mismo,
    además de darles seguimiento moviéndolas por el tablero."""
    u = current_user()
    return u is not None and u["rol"] in (
        "admin", "jefe_tienda", "subjefe_tienda", "mercadeo", "jefe_mantenimiento",
    )


def puede_mover_mant_tiendas():
    """Quién mueve las solicitudes por el tablero de Mantenimiento de
    Tiendas — admin, jefe de tienda, sub jefe de tienda y mercadeo tienen
    acceso total (igual que puede_crear_mant_tiendas); 'jefe_mantenimiento'
    es el rol dedicado exclusivamente a darles seguimiento (mismo concepto
    que 'disenador' en el tablero de Diseño Gráfico)."""
    u = current_user()
    return u is not None and u["rol"] in (
        "admin", "jefe_mantenimiento", "jefe_tienda", "subjefe_tienda", "mercadeo",
    )


def puede_subir_cotizacion_mant_tiendas():
    """Quién puede subir los archivos PDF de cotización dentro de una
    solicitud de Mantenimiento de Tiendas que está en la columna 'En
    cotización' — el jefe de planta, que es quien cotiza los trabajos con
    los proveedores, además de todos los roles que ya tienen acceso total
    al tablero (ver puede_crear_mant_tiendas)."""
    u = current_user()
    return u is not None and u["rol"] in (
        "admin", "jefe_tienda", "subjefe_tienda", "mercadeo", "jefe_mantenimiento", "jefe_planta",
    )


def puede_editar_drive():
    """Quién puede editar los números de la pestaña Drive ('Datos generales'
    y 'Krispy 2') — solo el administrador. Mercadeo, jefe de tienda y sub
    jefe de tienda también entran a esta pestaña, pero solo para consultar
    (tabla y gráfica), igual que 'vista' en el resto de la plataforma."""
    u = current_user()
    return u is not None and u["rol"] == "admin"


def puede_editar_nps():
    """Quién puede editar la parametrización (texto de las preguntas y
    opciones de la de opción múltiple) de la encuesta NPS: solo el
    administrador — mismo criterio que puede_editar_drive. Mercadeo, jefe de
    tienda y sub jefe de tienda también entran a esta pestaña (mismo grupo
    que ya entra a Drive), pero solo para consultar los KPIs y descargar los
    códigos QR, sin poder cambiar las preguntas."""
    u = current_user()
    return u is not None and u["rol"] == "admin"


def is_cliente_phara():
    u = current_user()
    return u is not None and u["rol"] == "cliente_phara"


def puede_editar_phara():
    """Quién puede crear pedidos, editarlos y moverlos por el tablero de la
    pestaña Phara — todos los que llegan a esta pestaña (admin, o quien
    tenga acceso extra otorgado desde Administración de usuarios), EXCEPTO
    el rol 'cliente_phara' (el cliente externo), que solo puede consultar el
    cronograma y el tablero, sin poder cambiar nada."""
    u = current_user()
    return u is not None and u["rol"] != "cliente_phara"


def puede_editar_colorado():
    """Quién puede crear órdenes de producción, moverlas por el tablero y
    eliminarlas en la pestaña Colorado: TODOS los que tienen acceso a esta
    pestaña — ya sea porque su rol la incluye por defecto (admin, vendedor,
    vista, jefe_tienda y subjefe_tienda) o porque se les dio acceso extra a
    'colorado' desde Administración de usuarios. A diferencia de Phara, aquí
    no hay ningún rol de solo consulta."""
    u = current_user()
    if u is None:
        return False
    if u["rol"] in ("admin", "vendedor", "vista", "jefe_tienda", "subjefe_tienda"):
        return True
    return "colorado" in (u.get("paginas_extra") or [])


def puede_editar_galaxy():
    """Igual que puede_editar_colorado, pero para la pestaña Galaxy (misma
    plataforma, línea de producción independiente)."""
    u = current_user()
    if u is None:
        return False
    if u["rol"] in ("admin", "vendedor", "vista", "jefe_tienda", "subjefe_tienda"):
        return True
    return "galaxy" in (u.get("paginas_extra") or [])


def puede_autorizar_cotizacion_mant_tiendas():
    """Solo el administrador puede autorizar la cotización de una solicitud
    de Mantenimiento de Tiendas — mientras no se autoriza, la tarjeta
    muestra el semáforo de cotización en rojo; una vez autorizada, en
    verde."""
    u = current_user()
    return u is not None and u["rol"] == "admin"
