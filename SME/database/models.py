from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# 1. TABLA INTERMEDIA (Asociación N:N)
# Relaciona Usuarios con Routers. Es necesaria porque un usuario puede estar 
# en varios routers y un router tiene muchos usuarios.
router_usuarios = db.Table('router_usuarios',
    db.Column('router_id', db.Integer, db.ForeignKey('routers.id', ondelete="CASCADE"), primary_key=True),
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id', ondelete="CASCADE"), primary_key=True)
)

class Router(db.Model):
    __tablename__ = 'routers'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(50), unique=True, nullable=False)
    ip_admin = db.Column(db.String(15), nullable=False, unique=True)
    ip_loopback = db.Column(db.String(15))
    rol = db.Column(db.String(20)) # frontera, núcleo, hoja
    empresa = db.Column(db.String(50), default="Cisco")
    sistema_operativo = db.Column(db.String(50), default="IOS 7200")
    
    # --- RELACIONES ---
    # Relación 1:N con Interfaces (Un router tiene muchas interfaces)
    # backref='propietario' permite hacer: interfaz.propietario para saber de qué router es.
    interfaces = db.relationship('Interface',foreign_keys='Interface.router_id', backref='propietario', lazy=True, cascade="all, delete-orphan")
    
    # Relación N:N con Usuarios usando la tabla intermedia definida arriba.
    usuarios_instalados = db.relationship('Usuario', secondary=router_usuarios, backref='routers_donde_vive')

class Interface(db.Model):
    __tablename__ = 'interfaces'
    id = db.Column(db.Integer, primary_key=True)
    nombre_api = db.Column(db.String(20)) # Ej: f1_0
    ip_address = db.Column(db.String(15))
    mascara = db.Column(db.String(15))
    estado = db.Column(db.String(10), default='down')
    
    # --- CLAVES FORÁNEAS (RELACIONES) ---
    # 1. A qué router pertenece esta interfaz (Obligatorio)
    router_id = db.Column(db.Integer, db.ForeignKey('routers.id'), nullable=False)
    
    # 2. TOPOLOGÍA: A qué router vecino está conectado este puerto físicamente.
    # Esta es la relación dinámica que llenará el Integrante 1.
    conectado_a_router_id = db.Column(db.Integer, db.ForeignKey('routers.id'), nullable=True)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    nivel_privilegio = db.Column(db.Integer, default=1)

class MetricaOctetos(db.Model):
    __tablename__ = 'metrica_octetos'
    id = db.Column(db.Integer, primary_key=True)
    router_hostname = db.Column(db.String(50), nullable=False) # Relación lógica por nombre
    interfaz_api = db.Column(db.String(20), nullable=False)
    octetos_entrada = db.Column(db.BigInteger, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class EventoTrap(db.Model):
    __tablename__ = 'evento_traps'
    id = db.Column(db.Integer, primary_key=True)
    router_hostname = db.Column(db.String(50), nullable=False)
    interfaz_api = db.Column(db.String(20), nullable=False)
    tipo_evento = db.Column(db.String(50), nullable=False) # 'LinkUp' o 'LinkDown'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)