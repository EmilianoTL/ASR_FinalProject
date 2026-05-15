from flask import Blueprint, jsonify

topologia_bp = Blueprint('topologia', __name__)

@topologia_bp.route('', methods=['GET'])
def get_topology():
    return jsonify({"mensaje": "Routers existentes y ligas a sus vecinos"}), 200

@topologia_bp.route('', methods=['POST'])
def start_topology_daemon():
    return jsonify({"mensaje": "Activa demonio que explora red cada 5 minutos"}), 200

@topologia_bp.route('', methods=['PUT'])
def update_topology_daemon():
    return jsonify({"mensaje": "Cambia el intervalo de tiempo del demonio"}), 200

@topologia_bp.route('', methods=['DELETE'])
def stop_topology_daemon():
    return jsonify({"mensaje": "Detiene el demonio que explora la topología"}), 200

@topologia_bp.route('/grafica', methods=['GET'])
def get_topology_graph():
    return jsonify({"mensaje": "Regresa formato gráfico de la topología"}), 200