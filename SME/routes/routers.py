from flask import Blueprint, jsonify, current_app
from database.models import Router
from network_utils.snmp_pysnmp import iniciar_monitoreo_hilo

routers_bp = Blueprint('routers', __name__)

# --- INFORMACIÓN GENERAL ---
@routers_bp.route('', methods=['GET'])
def get_all_routers():
    return jsonify({"mensaje": "Información general de todos los routers de la topología"}), 200

@routers_bp.route('/<hostname>/', methods=['GET'])
def get_router(hostname):
    return jsonify({"mensaje": f"Información general del router {hostname}"}), 200

@routers_bp.route('/<hostname>/interfaces', methods=['GET'])
def get_interfaces(hostname):
    return jsonify({"mensaje": f"Información de la interfaz del router {hostname}"}), 200


# --- CRUD USUARIOS POR ENRUTADOR ---
@routers_bp.route('/<hostname>/usuarios/', methods=['GET'])
def get_local_users(hostname):
    return jsonify({"mensaje": f"Usuarios existentes en el router {hostname}"}), 200

@routers_bp.route('/<hostname>/usuarios/', methods=['POST'])
def create_local_user(hostname):
    return jsonify({"mensaje": f"Agrega un nuevo usuario al router {hostname}"}), 201

@routers_bp.route('/<hostname>/usuarios/', methods=['PUT'])
def update_local_user(hostname):
    return jsonify({"mensaje": f"Actualiza un usuario al router {hostname}"}), 200

@routers_bp.route('/<hostname>/usuarios/', methods=['DELETE'])
def delete_local_user(hostname):
    return jsonify({"mensaje": f"Elimina usuario del router {hostname}"}), 200


# --- MONITOREO DE INTERFAZ (OCTETOS) ---
@routers_bp.route('/<hostname>/interfaces/<interfaz>/octetos/<tiempo>', methods=['GET'])
def get_octetos(hostname, interfaz, tiempo):
    return jsonify({"mensaje": f"Muestras de monitoreo en {interfaz}"}), 200

@routers_bp.route('/<hostname>/interfaces/<interfaz>/octetos/<tiempo>', methods=['POST'])
def start_octetos(hostname, interfaz, tiempo):
    # 1. Cumplir regla del PDF: Buscar el router. Si no existe, devolver 404.
    router = Router.query.filter_by(hostname=hostname).first()
    
    if not router:
        return jsonify({"error": True, "mensaje": "Router no encontrado en la topología"}), 404

    # 2. Iniciar el hilo de monitoreo pasando el contexto de la app actual
    resultado = iniciar_monitoreo_hilo(
        current_app._get_current_object(), 
        hostname, 
        router.ip_admin, 
        interfaz, 
        int(tiempo)
    )
    
    return jsonify(resultado), 200

@routers_bp.route('/<hostname>/interfaces/<interfaz>/octetos/<tiempo>', methods=['DELETE'])
def stop_octetos(hostname, interfaz, tiempo):
    return jsonify({"mensaje": f"Para el proceso de monitoreo en {interfaz}"}), 200


# --- GESTIÓN DE TRAPS (LINKUP/LINKDOWN) ---
@routers_bp.route('/<hostname>/interfaces/<interfaz>/estado', methods=['GET'])
def get_traps_estado(hostname, interfaz):
    return jsonify({"mensaje": f"Estado de la interfaz {interfaz}"}), 200

@routers_bp.route('/<hostname>/interfaces/<interfaz>/estado', methods=['POST'])
def start_traps(hostname, interfaz):
    return jsonify({"mensaje": f"Activa captura de trampas en {interfaz}"}), 200

@routers_bp.route('/<hostname>/interfaces/<interfaz>/estado', methods=['DELETE'])
def stop_traps(hostname, interfaz):
    return jsonify({"mensaje": f"Para la captura de trampas en {interfaz}"}), 200


# --- GRÁFICA DE MONITOREO ---
@routers_bp.route('/<hostname>/interfaces/<interfaz>/grafica', methods=['GET'])
def get_grafica_monitoreo(hostname, interfaz):
    return jsonify({"mensaje": f"Regresa gráfica JPG de monitoreos en {interfaz}"}), 200