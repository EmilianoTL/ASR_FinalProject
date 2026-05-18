import os

from flask import Flask,jsonify
from flask_cors import CORS 
from dotenv import load_dotenv


from database.models import db
from database.seed import ejecutar_poblado_inicial
from sqlalchemy import text 
from routes.usuarios import usuarios_bp
from routes.routers import routers_bp
from routes.topologia import topologia_bp

load_dotenv()

app = Flask(__name__)
CORS(app)

nombre_db = os.getenv('DB_NAME', 'red_asr.db')
puerto_app = int(os.getenv('FLASK_PUERTO', 5000))
modo_debug = os.getenv('FLASK_DEBUG') == 'True'

basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database', nombre_db)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all() 
    print(f"[DB] Base de datos '{nombre_db}' inicializada.")

app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
app.register_blueprint(routers_bp, url_prefix='/routers')
app.register_blueprint(topologia_bp, url_prefix='/topologia')

@app.route('/')
def index():
    return jsonify({
        "proyecto": "Gestion de Red ASR",
        "version": "1.0.0",
        "status": "Online"
    })


@app.route('/health', methods=['GET'])
def health_check():
    try:
        # Hacemos una consulta súper ligera a la base de datos (un "ping")
        db.session.execute(text('SELECT 1'))
        return jsonify({
            "api_status": "Online",
            "database_status": "Alive y conectada",
            "motor": "SQLite"
        }), 200
    except Exception as e:
        # Si la base de datos falla o no existe, atrapamos el error
        return jsonify({
            "api_status": "Online",
            "database_status": "Desconectada o con errores",
            "error_detalle": str(e)
        }), 500

if __name__ == '__main__':
    with app.app_context():
        ejecutar_poblado_inicial()
    app.run(host='0.0.0.0', port=puerto_app, debug=modo_debug)