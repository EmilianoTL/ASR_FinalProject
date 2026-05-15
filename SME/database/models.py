from flask_sqlalchemy import SQLAlchemy

# Instanciamos la base de datos
db = SQLAlchemy()

class Router(db.Model):
    """Modelo minimalista, solo con ID"""
    __tablename__ = 'routers'

    id = db.Column(db.Integer, primary_key=True)

    def to_dict(self):
        """Devuelve únicamente el ID"""
        return {
            "id": self.id
        }