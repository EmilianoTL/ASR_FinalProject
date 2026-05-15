from flask import Blueprint, jsonify

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('', methods=['GET'])
def get_global_users():
    return jsonify({"mensaje": "Regresa todos los usuarios existentes en los routers"}), 200

@usuarios_bp.route('', methods=['POST'])
def create_global_user():
    return jsonify({"mensaje": "Agrega un nuevo usuario a todos los routers"}), 201

@usuarios_bp.route('', methods=['PUT'])
def update_global_user():
    return jsonify({"mensaje": "Actualiza un usuario en todos los routers"}), 200

@usuarios_bp.route('', methods=['DELETE'])
def delete_global_user():
    return jsonify({"mensaje": "Elimina usuario común a todos los routers"}), 200