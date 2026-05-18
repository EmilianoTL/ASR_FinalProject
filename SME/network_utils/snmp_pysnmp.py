import os
from pysnmp.hlapi.v3arch.asyncio import *
from database.models import db, MetricaOctetos

# Cargar variables de entorno
COMUNIDAD = os.getenv('SNMP_COMMUNITY', 'asr_proyecto')
PUERTO_SNMP = int(os.getenv('SNMP_PORT_POLLING', 161))
def estandarizar_nombre_interfaz(interfaz_api):
    """
    El PDF requiere que la API reciba formatos como 'f1_0' o 'fastethernet1_0'.
    Esta función lo traduce al formato que suele devolver Cisco en ifDescr ('fastethernet1/0').
    """
    nombre = interfaz_api.lower().replace("_", "/")
    
    # Si empieza con 'f' pero no es 'fastethernet', lo expandimos
    if nombre.startswith("f") and not nombre.startswith("fastethernet"):
        nombre = nombre.replace("f", "fastethernet", 1)
        
    return nombre

def obtener_indice_dinamico(ip_admin, interfaz_api):
    """
    Hace un SNMP WALK sobre ifDescr (1.3.6.1.2.1.2.2.1.2) para encontrar 
    dinámicamente el ifIndex de la interfaz solicitada.
    """
    nombre_buscado = estandarizar_nombre_interfaz(interfaz_api)
    oid_ifdescr = '1.3.6.1.2.1.2.2.1.2'
    
    # nextCmd es la función de PySNMP 7.x para hacer un SNMP WALK
    iterator = next_cmd(
        SnmpEngine(),
        CommunityData(COMUNIDAD, mpModel=1), # v2c
        UdpTransportTarget((ip_admin, PUERTO_SNMP), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(oid_ifdescr)),
        lexicographicMode=False # Solo caminar dentro de ifDescr
    )

    for errorIndication, errorStatus, errorIndex, varBinds in iterator:
        if errorIndication or errorStatus:
            print(f"Error SNMP WALK: {errorIndication or errorStatus}")
            return None
            
        for varBind in varBinds:
            oid_completo = varBind[0]
            nombre_interfaz_router = varBind[1].prettyPrint().lower()
            
            # Si encontramos "fastethernet1/0" en el resultado del router
            if nombre_buscado in nombre_interfaz_router:
                # El OID se ve así: 1.3.6.1.2.1.2.2.1.2.2
                # El índice es el último número del OID
                indice = int(oid_completo[-1])
                return indice
                
    return None # No se encontró la interfaz

def recolectar_octetos(hostname, ip_admin, interfaz_api):
    """
    Busca dinámicamente el índice de la interfaz, obtiene los octetos de entrada
    y guarda el registro en la base de datos (SQLAlchemy 3.x).
    """
    # 1. Búsqueda dinámica (¡Ya no está hardcodeado!)
    indice = obtener_indice_dinamico(ip_admin, interfaz_api)
    
    if not indice:
        return {"error": True, "mensaje": f"La interfaz {interfaz_api} no existe en el router."}

    # 2. OID de ifInOctets armado dinámicamente
    oid_octetos = f'1.3.6.1.2.1.2.2.1.10.{indice}'

    try:
        # 3. Petición GET con PySNMP 7.x
        iterator = get_cmd(
            SnmpEngine(),
            CommunityData(COMUNIDAD, mpModel=1),
            UdpTransportTarget((ip_admin, PUERTO_SNMP), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid_octetos))
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication or errorStatus:
            return {"error": True, "mensaje": "Fallo al consultar octetos."}

        # Extraer el valor
        octetos = int(varBinds[0][1])

        # 4. Guardar en SQLite usando SQLAlchemy 3.x
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
                "ifIndex_encontrado": indice,
                "octetos_entrada": octetos
            }
        }

    except Exception as e:
        return {"error": True, "mensaje": f"Error del sistema: {str(e)}"}
    

if __name__ == '__main__':
    from database.models import app # Necesitamos el contexto de Flask para la BD
    
    # Datos de prueba (Ajusta la IP al router Edge o R1 de tu GNS3)
    ROUTER_PRUEBA = "Edge"
    IP_PRUEBA = "192.168.100.1"  # IP administrativa del router en tu topología
    INTERFAZ_PRUEBA = "f1_0"     # Interfaz que sabemos que existe
    
    print(f"Iniciando prueba SNMP hacia {ROUTER_PRUEBA} ({IP_PRUEBA})...")
    
    with app.app_context(): # Simulamos que estamos dentro de la API
        # Creamos las tablas de prueba si no existen
        db.create_all() 
        
        # Ejecutamos tu función
        resultado = recolectar_octetos(ROUTER_PRUEBA, IP_PRUEBA, INTERFAZ_PRUEBA)
        print("\nResultado de la prueba:")
        print(resultado)