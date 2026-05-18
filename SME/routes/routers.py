from flask import Blueprint, jsonify, current_app
from database.models import *
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
    """
    Regresa un JSON con todas las muestras guardadas en la BD hasta el momento.
    Cumple la regla del HTTP 404 si el router no existe en el catálogo.
    """
    # 1. Validar existencia del router (Regla general 2 del PDF)
    router = Router.query.filter_by(hostname=hostname).first()
    if not router:
        return jsonify({"error": True, "mensaje": "Router no encontrado en la topología."}), 404

    # 2. Consultar la tabla de métricas filtrando por router e interfaz
    muestras = MetricaOctetos.query.filter_by(
        router_hostname=hostname, 
        interfaz_api=interfaz
    ).order_by(MetricaOctetos.timestamp.asc()).all()

    # 3. Formatear los registros de SQLAlchemy a diccionarios JSON nativos
    lista_muestras = [
        {
            "id": m.id,
            "router": m.router_hostname,
            "interfaz": m.interfaz_api,
            "octetos_entrada": m.octetos_entrada,
            "timestamp": m.timestamp.isoformat()
        }
        for m in muestras
    ]

    return jsonify({
        "router": hostname,
        "interfaz": interfaz,
        "total_muestras_recolectadas": len(lista_muestras),
        "muestras": lista_muestras
    }), 200

@routers_bp.route('/<hostname>/interfaces/<interfaz>/octetos/<tiempo>', methods=['POST'])
def start_octetos(hostname, interfaz, tiempo):
    """
    Activa el monitoreo continuo en segundo plano.
    Utiliza el parámetro <tiempo> de la URL como el intervalo de sondeo entre muestras.
    """
    router = Router.query.filter_by(hostname=hostname).first()
    if not router:
        return jsonify({"error": True, "mensaje": "Router no encontrado en la topología."}), 404

    try:
        # Limpiar registros históricos de esta interfaz para asegurar una gráfica limpia
        MetricaOctetos.query.filter_by(
            router_hostname=hostname, 
            interfaz_api=interfaz
        ).delete(synchronize_session=False)
        db.session.commit()

        # Iniciamos el hilo pasando <tiempo> directamente como el intervalo de muestreo
        from network_utils.snmp_pysnmp import iniciar_monitoreo_hilo
        resultado = iniciar_monitoreo_hilo(
            current_app._get_current_object(), 
            hostname, 
            router.ip_admin, 
            interfaz, 
            int(tiempo)
        )
        
        return jsonify(resultado), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": True, "mensaje": f"Error en el servidor: {str(e)}"}), 500
    
@routers_bp.route('/<hostname>/interfaces/<interfaz>/octetos/<tiempo>', methods=['DELETE'])
def stop_octetos(hostname, interfaz, tiempo):
    """
    Detiene inmediatamente el hilo de monitoreo continuo para la interfaz.
    """
    router = Router.query.filter_by(hostname=hostname).first()
    if not router:
        return jsonify({"error": True, "mensaje": "Router no encontrado en la topología."}), 404

    from network_utils.snmp_pysnmp import detener_monitoreo_interfaz
    resultado = detener_monitoreo_interfaz(hostname, interfaz)
    
    # Si ocurre con éxito devolvemos 200, si no había hilo activo devolvemos un código de control
    status_code = 200 if not resultado["error"] else 400
    return jsonify(resultado), status_code


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