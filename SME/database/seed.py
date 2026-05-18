import os
from database.models import db, Router, Interface

def ejecutar_poblado_inicial():
    """
    Función ejecutable desde app.py o de forma independiente.
    Verifica si existen routers en la base de datos.
    Si está vacía, crea las tablas y la puebla de forma automática.
    """
    # 1. Asegurar que las tablas existan (si no existen, se crean)
    db.create_all()
    
    # 2. Verificar si ya hay datos de la topología insertados
    if Router.query.count() == 0:
        print("[AUTO-SEED] No se encontraron routers activos. Poblando base de datos...")
        
        routers_data = [
            {
                "hostname": "Edge", "ip_admin": "192.168.100.1", "ip_loopback": "192.168.50.1", "rol": "frontera",
                "interfaces": [
                    {"nombre_api": "f1_0", "ip_address": "10.0.0.1", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f1_1", "ip_address": "10.0.0.5", "mascara": "255.255.255.252", "estado": "up"}
                ]
            },
            {
                "hostname": "R1", "ip_admin": "192.168.100.2", "ip_loopback": "192.168.50.2", "rol": "núcleo",
                "interfaces": [
                    {"nombre_api": "f1_0", "ip_address": "10.0.0.2", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f2_0", "ip_address": "10.0.0.17", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f2_1", "ip_address": "10.0.0.9", "mascara": "255.255.255.252", "estado": "up"}
                ]
            },
            {
                "hostname": "R2", "ip_admin": "192.168.100.3", "ip_loopback": "192.168.50.3", "rol": "núcleo",
                "interfaces": [
                    {"nombre_api": "f1_1", "ip_address": "10.0.0.6", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f2_0", "ip_address": "10.0.0.21", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f2_1", "ip_address": "10.0.0.13", "mascara": "255.255.255.252", "estado": "up"}
                ]
            },
            {
                "hostname": "TOR-1", "ip_admin": "192.168.100.4", "ip_loopback": "192.168.50.4", "rol": "hoja",
                "interfaces": [
                    {"nombre_api": "f1_0", "ip_address": "192.168.0.1", "mascara": "255.255.255.0", "estado": "up"},
                    {"nombre_api": "f1_1", "ip_address": "192.168.1.1", "mascara": "255.255.255.0", "estado": "up"},
                    {"nombre_api": "f2_0", "ip_address": "10.0.0.18", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f2_1", "ip_address": "10.0.0.14", "mascara": "255.255.255.252", "estado": "up"}
                ]
            },
            {
                "hostname": "TOR-2", "ip_admin": "192.168.100.5", "ip_loopback": "192.168.50.5", "rol": "hoja",
                "interfaces": [
                    {"nombre_api": "f1_0", "ip_address": "192.168.10.1", "mascara": "255.255.255.0", "estado": "up"},
                    {"nombre_api": "f1_1", "ip_address": "192.168.11.1", "mascara": "255.255.255.0", "estado": "up"},
                    {"nombre_api": "f2_0", "ip_address": "10.0.0.22", "mascara": "255.255.255.252", "estado": "up"},
                    {"nombre_api": "f2_1", "ip_address": "10.0.0.10", "mascara": "255.255.255.252", "estado": "up"}
                ]
            }
        ]

        for r in routers_data:
            nuevo_router = Router(
                hostname=r["hostname"],
                ip_admin=r["ip_admin"],
                ip_loopback=r["ip_loopback"],
                rol=r["rol"]
            )
            db.session.add(nuevo_router)
            db.session.flush()

            for i in r["interfaces"]:
                nueva_interfaz = Interface(
                    nombre_api=i["nombre_api"],
                    ip_address=i["ip_address"],
                    mascara=i["mascara"],
                    estado=i["estado"],
                    router_id=nuevo_router.id
                )
                db.session.add(nueva_interfaz)

        db.session.commit()
        print("[AUTO-SEED] Base de datos inicializada y poblada correctamente.")
    else:
        print("[AUTO-SEED] Base de datos activa detectada. Omitiendo poblado inicial.")

# Permite que se pueda seguir ejecutando solo si escribes `python seed.py` por separado
if __name__ == '__main__':
    from app import app
    with app.app_context():
        ejecutar_poblado_inicial()