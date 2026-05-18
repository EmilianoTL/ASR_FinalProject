import os
import asyncio
from pysnmp.hlapi.v3arch.asyncio import *
from database.models import db, MetricaOctetos

COMUNIDAD = os.getenv('SNMP_COMMUNITY', 'asr_proyecto')
PUERTO_SNMP = int(os.getenv('SNMP_PORT_POLLING', 161))

def estandarizar_nombre_interfaz(interfaz_api):
    nombre = interfaz_api.lower().replace("_", "/")
    if nombre.startswith("f") and not nombre.startswith("fastethernet"):
        nombre = nombre.replace("f", "fastethernet", 1)
    return nombre

async def obtener_indice_dinamico(ip_admin, interfaz_api):
    """
    Refactorizado usando walk_cmd según la documentación oficial de PySNMP v7.1
    Esto maneja los saltos y el límite del OID automáticamente.
    """
    nombre_buscado = estandarizar_nombre_interfaz(interfaz_api)
    oid_base = '1.3.6.1.2.1.2.2.1.2'
    
    transport = await UdpTransportTarget.create((ip_admin, PUERTO_SNMP))
    engine = SnmpEngine()
    
    # walk_cmd hace el trabajo pesado del iterador automáticamente
    async for errorIndication, errorStatus, errorIndex, varBinds in walk_cmd(
        engine,
        CommunityData(COMUNIDAD, mpModel=1),
        transport,
        ContextData(),
        ObjectType(ObjectIdentity(oid_base))
    ):
        if errorIndication or errorStatus:
            return None
            
        for varBind in varBinds:
            oid_completo = str(varBind[0])
            nombre_interfaz = str(varBind[1]).lower()
            
            # Solo evaluamos si encontramos la interfaz
            if nombre_buscado in nombre_interfaz:
                return int(oid_completo.split('.')[-1])
                
    return None

async def consultar_octetos_async(ip_admin, interfaz_api):
    indice = await obtener_indice_dinamico(ip_admin, interfaz_api)
    if not indice:
        return None, f"La interfaz {interfaz_api} no existe en el router."

    oid_octetos = f'1.3.6.1.2.1.2.2.1.10.{indice}'
    
    # 1. Creación asíncrona del transporte UDP
    transport = await UdpTransportTarget.create((ip_admin, PUERTO_SNMP))
    engine = SnmpEngine()

    # 2. Uso de get_cmd en lugar de getCmd
    errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
        engine,
        CommunityData(COMUNIDAD, mpModel=1),
        transport,
        ContextData(),
        ObjectType(ObjectIdentity(oid_octetos))
    )

    if errorIndication or errorStatus:
        return None, f"Fallo SNMP: {errorIndication or errorStatus}"

    return int(varBinds[0][1]), indice

def recolectar_octetos(hostname, ip_admin, interfaz_api):
    """
    Envoltorio síncrono para Flask y SQLAlchemy.
    """
    try:
        octetos, indice_o_error = asyncio.run(consultar_octetos_async(ip_admin, interfaz_api))
        
        if octetos is None:
            return {"error": True, "mensaje": indice_o_error}

        nueva_metrica = MetricaOctetos(
            router_hostname=hostname,
            interfaz_api=interfaz_api,
            octetos_entrada=octetos
        )
        db.session.add(nueva_metrica)
        db.session.commit()

        return {
            "error": False, 
            "mensaje": "Métrica recolectada y guardada",
            "datos": {
                "router": hostname,
                "interfaz": interfaz_api,
                "ifIndex_encontrado": indice_o_error,
                "octetos_entrada": octetos
            }
        }
    except Exception as e:
        return {"error": True, "mensaje": f"Error del sistema: {str(e)}"}

# --- BLOQUE DE PRUEBA LOCAL ---
if __name__ == '__main__':
    from database.models import app
    
    ROUTER_PRUEBA = "Edge"
    IP_PRUEBA = "192.168.100.1" 
    INTERFAZ_PRUEBA = "f1_0"     
    
    print(f"Iniciando prueba (PySNMP v7 asyncio) hacia {ROUTER_PRUEBA} ({IP_PRUEBA})...")
    
    with app.app_context():
        db.create_all() 
        resultado = recolectar_octetos(ROUTER_PRUEBA, IP_PRUEBA, INTERFAZ_PRUEBA)
        print("\nResultado:")
        print(resultado)