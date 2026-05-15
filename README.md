# ⚙️ Backend API - Gestión de Red (SME)

Esta carpeta contiene el código fuente del **Backend (API REST)** para el proyecto final de Administración de Servicios en Red (ASR). Está desarrollada en **Python + Flask** y diseñada bajo una arquitectura modular para gestionar dinámicamente una topología de routers Cisco configurados en GNS3.

La API permite interactuar con los dispositivos de red mediante **SSH (Netmiko)** y **SNMP (PySNMP)** para realizar tareas de inventario, configuración y telemetría.

---

## 📂 Estructura del Directorio

El proyecto sigue el patrón de diseño de **Flask Blueprints** para mantener la escalabilidad y el orden:

```text
📁 SME/
├── app.py                 # Orquestador principal de la API y conexión a la BD
├── requirements.txt       # Dependencias oficiales y versiones (LTS)
├── .gitignore             # Archivos excluidos del control de versiones
│
├── 📁 database/           # Capa de datos
│   └── models.py          # Modelos formales (ORM) usando Flask-SQLAlchemy
│
├── 📁 routes/             # Controladores y Endpoints (Blueprints)
│   ├── routers.py         # Gestión de equipos, interfaces y telemetría (SNMP)
│   ├── topologia.py       # Detección dinámica de vecinos y generación de grafos
│   └── usuarios.py        # CRUD global de usuarios en la red
│
└── 📁 network_utils/      # Scripts de interacción directa con Cisco
    ├── ssh_netmiko.py     # Utilidades para conexiones SSH y comandos IOS
    └── snmp_pysnmp.py     # Utilidades para monitoreo y traps SNMP
```

---

## 🚀 Características Principales

1. **Topología Dinámica:** Detección de vecinos y graficación automática.
2. **Gestión de Usuarios (CRUD):** Altas, bajas y modificaciones de credenciales tanto globales como por router específico utilizando conexiones seguras SSH.
3. **Telemetría y Monitoreo SNMP:** Captura de muestreos de octetos de entrada/salida y gestión de traps (LinkUp/LinkDown) por interfaz.
4. **Arquitectura Segura:** Uso de variables de entorno para protección de credenciales y un ORM (SQLAlchemy) para prevenir inyecciones SQL.

---

## 🛠️ Instalación y Configuración

Para ejecutar esta API localmente, asegúrate de tener instalado **Python 3.10 o superior**.

### 1. Crear y activar el entorno virtual

Es indispensable ejecutar la aplicación dentro de un entorno aislado. Ubicado en la consola dentro de la carpeta `SME/`, ejecuta:

**En Windows (Git Bash o CMD):**

```bash
python -m venv venv
source venv/Scripts/activate  # (Git Bash)
# venv\Scripts\activate       # (CMD / PowerShell)
```

**En Linux / Mac:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependencias

Con el entorno `(venv)` activado, instala las librerías oficiales del proyecto:

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crea un archivo llamado `.env` en la raíz de la carpeta `SME/` (junto a `app.py`). Este archivo es ignorado por Git por seguridad. Añade el siguiente contenido base y modifícalo con tus credenciales:

```env
# Servidor Flask
FLASK_APP=app.py
FLASK_DEBUG=True
FLASK_PUERTO=5000

# Base de Datos
DB_NAME=red_asr.db

# Credenciales de Red (Routers)
ROUTER_USER=admin
ROUTER_PASS=admin
```

---

## 🏃‍♂️ Ejecución del Servidor

Una vez configurado todo, inicia el orquestador principal:

```bash
python app.py
```

Deberías ver en consola que la base de datos se inicializa y el servidor arranca en `http://0.0.0.0:5000`.

### Verificación de Estado (Health Check)

Para comprobar que la API y la base de datos están corriendo correctamente, abre tu navegador o Postman y haz una petición GET a:
👉 **`http://127.0.0.1:5000/health`**

---

## 📡 Documentación de Endpoints

La API respeta de manera estricta los requerimientos REST solicitados en la rúbrica del proyecto. A continuación se detallan los endpoints disponibles:

### 1. Gestión Global de Usuarios (`/usuarios`)

Operaciones que afectan a toda la infraestructura de red de forma simultánea.

| Método | Endpoint | Descripción de la Función |
| --- | --- | --- |
| **GET** | `/usuarios/` | Recupera un JSON con todos los usuarios existentes en la red, detallando nombre, permisos y en qué routers están presentes. |
| **POST** | `/usuarios/` | Crea un nuevo usuario en **todos** los routers de la topología. Devuelve los datos del usuario creado. |
| **PUT** | `/usuarios/` | Actualiza las credenciales o permisos de un usuario existente en **toda** la red. |
| **DELETE** | `/usuarios/` | Elimina un usuario común de **todos** los dispositivos de red. |

### 2. Inventario de Routers e Interfaces (`/routers`)

Agrupa las consultas de estado e interfaces, así como la gestión local de usuarios por dispositivo.

| Método | Endpoint | Descripción de la Función |
| --- | --- | --- |
| **GET** | `/routers/` | Muestra información general de la topología: Nombres, IPs de administración, roles y SO. |
| **GET** | `/routers/<host>/` | Obtiene el detalle técnico de un router específico mediante su nombre de host. |
| **GET** | `/routers/<host>/interfaces` | Lista las interfaces activas del router con su IP, máscara y estado actual. |
| **GET** | `/routers/<host>/usuarios/` | Lista únicamente los usuarios que tienen acceso al router especificado. |
| **POST** | `/routers/<host>/usuarios/` | Da de alta a un usuario únicamente en el equipo definido. |
| **PUT** | `/routers/<host>/usuarios/` | Actualiza los datos de un usuario únicamente en el equipo definido. |
| **DELETE** | `/routers/<host>/usuarios/` | Elimina a un usuario únicamente del equipo definido. |

### 3. Telemetría y Monitoreo SNMP (`/routers/<host>/interfaces/<intf>/...`)

Endpoints dedicados al análisis de tráfico (octetos) y eventos de red (traps). El formato de la interfaz debe ser abreviado (ej. `f1_0`).

| Método | Endpoint | Descripción de la Función |
| --- | --- | --- |
| **POST** | `.../octetos/<tiempo>` | **Activa** el proceso de monitoreo de octetos de entrada en la interfaz por el tiempo indicado en segundos. |
| **GET** | `.../octetos/<tiempo>` | Recupera todas las muestras de tráfico recolectadas hasta el momento en formato JSON. |
| **DELETE** | `.../octetos/<tiempo>` | **Detiene** inmediatamente el proceso de monitoreo de octetos. |
| **POST** | `.../estado` | **Activa** la captura de trampas SNMP (LinkUp/LinkDown) para la interfaz seleccionada. |
| **GET** | `.../estado` | Devuelve el estado actual de captura de trampas de la interfaz. |
| **DELETE** | `.../estado` | **Desactiva** la captura de trampas SNMP para la interfaz. |
| **GET** | `.../grafica` | Genera y descarga un archivo (JPG/PNG) con la gráfica de tráfico y estado de la interfaz. |

### 4. Detección Dinámica de Topología (`/topologia`)

Módulo encargado del "demonio" que explora la red automáticamente y genera la representación visual.

| Método | Endpoint | Descripción de la Función |
| --- | --- | --- |
| **GET** | `/topologia/` | Devuelve la lista de routers detectados y sus conexiones (vecinos) actuales. |
| **POST** | `/topologia/` | **Arranca el demonio** que explora la red periódicamente buscando cambios. |
| **PUT** | `/topologia/` | Permite modificar el intervalo de tiempo (frecuencia) con el que el demonio explora la red. |
| **DELETE** | `/topologia/` | **Apaga** el proceso de exploración automática de la topología. |
| **GET** | `/topologia/grafica` | Devuelve un archivo gráfico con la representación visual de la red completa. |

---
