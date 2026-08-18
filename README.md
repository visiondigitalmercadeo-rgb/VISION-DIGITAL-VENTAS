# Plataforma Comercial — Visión Digital

Prototipo funcional en **Python (Streamlit)** conectado a **Firebase / Firestore**
como base de datos en la nube. Mientras no tengas tus credenciales de Firebase
configuradas, la app funciona sola en un **modo de práctica** (datos temporales
en memoria) para que puedas explorarla sin bloquearte.

## Qué incluye

1. **Calendario de citas y visitas de vendedores** — vista de calendario visual (mes/semana/lista) + lista editable.
2. **Calendario de visitas de mercadeo a puntos de venta**, con checklist por visita y vista Gantt.
3. **CRM de prospección**: nombre del cliente, datos, NIT, con:
   - recordatorio para el vendedor,
   - fecha de seguimiento,
   - **alerta automática si el NIT ya existe** en la base de datos.
4. **Fecha de contacto, cotización enviada y estado de la cotización** (módulo Cotizaciones, ligado a cada prospecto).
5. **Reclamos**: cliente, número de orden, fecha de reclamo, fecha de solución, estatus.
6. **Prospectos generales**: listado de todos los prospectos de todo el equipo — solo visibilidad.
7. **Venta del día por vendedor**: por planta (Offset, Digital, Valloy, Colorado) y por línea de venta, con venta general y acumulada.

### KPIs

1. Número de citas, visitas y llamadas — total, por vendedor y en general.
2. Clientes cerrados — total y por vendedor por mes.
3. Visitas de mercadeo — acumulado del checklist y pendientes por resolver.
4. Venta del día y acumulado (por planta y por vendedor).

### Usuarios y roles

- **Administrador**: acceso total, gestiona usuarios (crear vendedores/solo-vista, activar/desactivar, restablecer contraseñas).
- **Vendedor**: llena y ve únicamente su propia información (citas, prospectos, cotizaciones, reclamos, ventas). Puede ver "Prospectos generales" de solo lectura.
- **Solo vista**: acceso de lectura a todos los módulos y KPIs, sin poder crear ni editar.

## Cómo ejecutarlo

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Se abre en `http://localhost:8501`. Usuarios de demostración (cámbialos desde
"Administración de usuarios" antes de usar la plataforma con tu equipo real):

| Usuario | Contraseña   | Rol            |
|---------|--------------|----------------|
| admin   | admin123     | Administrador  |
| vista   | vista123     | Solo vista     |
| juan    | vendedor123  | Vendedor       |
| maria   | vendedor123  | Vendedor       |
| carlos  | vendedor123  | Vendedor       |

## Conectar tu proyecto de Firebase (paso a paso)

Mientras no completes esto, verás un aviso amarillo en la app: estás en
**modo de práctica** (los datos se pierden al cerrar el servidor). Sigue estos
pasos para conectarla a tu base de datos real en la nube:

**1. Crea el proyecto en Firebase.**
Entra a [console.firebase.google.com](https://console.firebase.google.com) con
tu cuenta de Google → **"Crear un proyecto"** → ponle un nombre (por ejemplo
`vision-digital-ventas`) → puedes desactivar Google Analytics si te lo pregunta,
no lo necesitas → **Crear proyecto**.

**2. Activa Firestore.**
Dentro del proyecto, en el menú izquierdo busca **"Firestore Database"** (bajo
"Compilación" / "Build") → **"Crear base de datos"** → elige una ubicación
(cualquiera cercana está bien, por ejemplo `us-central`) → inicia en **modo de
producción** → **Habilitar**.

**3. Descarga tus credenciales.**
Haz clic en el ícono de engranaje ⚙️ junto a "Descripción general del proyecto"
→ **"Configuración del proyecto"** → pestaña **"Cuentas de servicio"** →
botón **"Generar nueva clave privada"** → confirma. Se descarga un archivo
`.json` (algo como `vision-digital-ventas-firebase-adminsdk-xxxxx.json`).

**4. Colócalo en la carpeta de la plataforma.**
Renombra ese archivo descargado a exactamente:
```
serviceAccountKey.json
```
y muévelo a la misma carpeta donde está `app.py` (junto a `requirements.txt`,
`database.py`, etc.).

**5. Reinicia la plataforma.**
Detén el servidor si está corriendo (`Ctrl + C` en la Terminal) y vuelve a
correr `python3 -m streamlit run app.py`. El aviso amarillo de "modo de
práctica" debe desaparecer — a partir de ahí, todo lo que se registre en la
plataforma se guarda de verdad en tu proyecto de Firebase.

⚠️ **Ese archivo `serviceAccountKey.json` es como una contraseña maestra de tu
base de datos: nunca lo compartas ni lo subas a GitHub.** Ya está excluido
automáticamente en `.gitignore` para evitar subirlo por error si más adelante
publicas el código.

## Estructura del proyecto

```
app.py                     # Punto de entrada: login + navegación por rol
auth.py                    # Login, sesión y permisos
config.py                  # Catálogos (plantas, estados, colores, marca) — editar aquí para ajustar listas
database.py                 # Toda la lógica de datos (Firestore + modo de práctica)
fake_firestore.py           # Base de datos en memoria usada solo en modo de práctica
utils.py                    # Funciones compartidas (formato de moneda, filtros, gráficas)
assets/logo.png              # Logo de Visión Digital
serviceAccountKey.json       # (lo agregas tú) credenciales de Firebase — no se comparte
app_pages/                   # Cada módulo de la plataforma
  1_Inicio.py
  2_Prospectos_CRM.py
  3_Citas_Vendedores.py
  4_Visitas_Mercadeo.py
  5_Cotizaciones.py
  6_Reclamos.py
  7_Ventas_Diarias.py
  8_Prospectos_Generales.py
  9_KPIs.py
  10_Administracion.py
```

## Próximos pasos sugeridos

- Completar la conexión a Firebase (sección de arriba).
- Cambiar las contraseñas de demostración y crear los usuarios reales de tu equipo.
- Ajustar los catálogos en `config.py` (líneas de venta por planta, checklist de mercadeo, estados) a tu operación real.
- Publicarla en internet con un link propio (por ejemplo `https://vision-digital-ventas.streamlit.app`) para que todo el equipo la use desde su navegador, sin depender de tu computadora encendida.
