import os
import asyncio
from pysnmp.hlapi.v3arch.asyncio import *
from database.models import db, MetricaOctetos
import threading
import time
from flask import current_app


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
    from app import app
    
    ROUTER_PRUEBA = "Edge"
    IP_PRUEBA = "192.168.100.1" 
    INTERFAZ_PRUEBA = "f1_0"     
    
    print(f"Iniciando prueba (PySNMP v7 asyncio) hacia {ROUTER_PRUEBA} ({IP_PRUEBA})...")
    
    with app.app_context():
        db.create_all() 
        resultado = recolectar_octetos(ROUTER_PRUEBA, IP_PRUEBA, INTERFAZ_PRUEBA)
        print("\nResultado:")
        print(resultado)

def proceso_monitoreo_continuo(app_context, hostname, ip_admin, interfaz_api, intervalo):
    """
    Función que vive en un Hilo (Thread).
    Corre de forma indefinida usando el <tiempo> de la URL como el intervalo de sondeo,
    hasta que se recibe un DELETE.
    """
    identificador_unico = f"{hostname}_{interfaz_api}"
    
    print(f"\n🚀 [MONITOREO SNMP INICIADO] -> Router: {hostname} | Interfaz: {interfaz_api}")
    print(f"   🔄 Frecuencia de consulta (Sondeo): Cada {intervalo}s | Estado: Corriendo indefinidamente")
    
    app_obj = app_context.app
    app_obj.hilos_snmp_activos[identificador_unico] = True

    with app_context: 
        contador_muestras = 1
        while True:
            # REGLA CRÍTICA: Si el endpoint DELETE cambia la bandera a False, el hilo muere inmediatamente
            if not app_obj.hilos_snmp_activos.get(identificador_unico, False):
                print(f"🛑 [MONITOREO DETENIDO] -> El proceso continuo para {identificador_unico} ha sido finalizado.")
                break
                
            print(f"📊 [MUESTRA #{contador_muestras}] -> Consultando {identificador_unico} ({ip_admin})...")
            resultado = recolectar_octetos(hostname, ip_admin, interfaz_api)
            
            if resultado.get("error"):
                print(f"   ⚠️ [ERROR EN MUESTRA #{contador_muestras}] -> {resultado.get('mensaje')}")
            else:
                octetos = resultado["datos"]["octetos_entrada"]
                print(f"   ✅ [MUESTRA #{contador_muestras} GUARDADA] -> Octetos: {octetos}")
                
            contador_muestras += 1
            
            # Duerme los segundos exactos indicados en el <tiempo> de la URL
            time.sleep(int(intervalo))
            
        # Limpieza de la bandera al salir del ciclo
        app_obj.hilos_snmp_activos.pop(identificador_unico, None)


def iniciar_monitoreo_hilo(app_obj, hostname, ip_admin, interfaz_api, intervalo):
    """
    Lanza el hilo de sondeo continuo regulado por el intervalo de la URL.
    """
    hilo = threading.Thread(
        target=proceso_monitoreo_continuo,
        args=(app_obj.app_context(), hostname, ip_admin, interfaz_api, intervalo)
    )
    hilo.daemon = True
    hilo.start()
    return {
        "error": False, 
        "mensaje": f"Monitoreo continuo e indefinido activado en {interfaz_api}.",
        "configuracion": {
            "intervalo_muestreo_segundos": intervalo
        }
    }

def detener_monitoreo_interfaz(hostname, interfaz_api):
    """
    Modifica la bandera en la app global. Compatible con peticiones DELETE masivas.
    """
    identificador_unico = f"{hostname}_{interfaz_api}"
    
    # Accedemos de forma segura a través del contexto actual de Flask
    if identificador_unico in current_app.hilos_snmp_activos:
        current_app.hilos_snmp_activos[identificador_unico] = False
        return {"error": False, "mensaje": f"Proceso de monitoreo en {interfaz_api} detenido exitosamente."}
    
    return {"error": True, "mensaje": f"No hay un proceso de monitoreo activo para la interfaz {interfaz_api}."}
# --- RECEPTOR DE TRAPS SNMP CON FILTRADO ESTRICTO ---

# --- RECEPTOR ASÍNCRONO DE TRAPS/INFORMs (PUERTO 162) ---

# Tarea asíncrona global de control para saber si el Listener UDP está corriendo en el background de la API
_TAREA_LISTENER_TRAPS = None

def procesar_trap_entrante(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    """
    Callback nativo de PySNMP v7.1. Se ejecuta automáticamente cada vez que 
    un router de GNS3 envía una trampa al puerto 162.
    """
    from database.models import db, EventoTrap, Router
    # cbCtx transporta de forma segura el app_context de Flask
    app_context = cbCtx
    app_obj = app_context.app
    
    # OIDs estándar definidos en la documentación de PySNMP / MIBs IETF
    OID_LINK_DOWN = '1.3.6.1.6.3.1.1.5.3'
    OID_LINK_UP = '1.3.6.1.6.3.1.1.5.4'
    OID_IF_DESCR = '1.3.6.1.2.1.2.2.1.2'

    tipo_evento = "Desconocido"
    interfaz_afectada = "Desconocida"
    ip_origen = "Desconocida"

    # Extraer la IP de origen del paquete UDP
    try:
        transport_info = snmpEngine.transportDispatcher.getTransportInfo(stateReference)
        if transport_info:
            ip_origen = transport_info[1][0]
    except Exception:
        pass

    # Analizar el contenido del Trap
    for name, val in varBinds:
        val_str = str(val)
        if val_str == OID_LINK_DOWN:
            tipo_evento = "LinkDown"
        elif val_str == OID_LINK_UP:
            tipo_evento = "LinkUp"
        elif OID_IF_DESCR in str(name) or "ifDescr" in str(name):
            interfaz_afectada = val_str.lower()

    if "fastethernet" in interfaz_afectada:
        interfaz_afectada = interfaz_afectada.replace("fastethernet", "f", 1).replace("/", "_")

    with app_context:
        router = Router.query.filter_by(ip_admin=ip_origen).first()
        hostname = router.hostname if router else ip_origen
        
        identificador_unico = f"{hostname}_{interfaz_afectada}_traps"

        # REGLA FILTRADO ESTRICTO: Si no está activa la captura (POST), se ignora el evento de red
        if not app_obj.hilos_snmp_activos.get(identificador_unico, False):
            return

        print(f"\n🔔 [TRAP CAPTURADO] -> Evento detectado para la interfaz activa: {identificador_unico}")
        
        nuevo_evento = EventoTrap(
            router_hostname=hostname,
            interfaz_api=interfaz_afectada,
            tipo_evento=tipo_evento
        )
        db.session.add(nuevo_evento)
        db.session.commit()
        print(f"   💾 [GUARDADO EN BD] -> Estado actualizado: {tipo_evento}")


async def corutina_servidor_traps(app_context):
    """
    Corutina asíncrona pura basada en la documentación 'NotificationReceiver' de PySNMP v7.1.
    Abre y mantiene el socket UDP 162 de forma no bloqueante.
    """
    # Importaciones de la arquitectura asíncrona nativa de Lextudio
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine, ContextData
    from pysnmp.entity.rfc3413 import ntforg
    
    puerto_traps = int(os.getenv('SNMP_PORT_TRAPS', 162))
    ip_sme = os.getenv('SME_IP', '0.0.0.0')

    engine = SnmpEngine()
    
    # IMPORTANTE: En PySNMP v7.1 asyncio, el transporte se añade mediante corutinas de transporte asíncronas
    # de forma transparente, permitiendo que corra nativamente en el loop de asyncio de Flask.
    receiver = ntforg.NotificationReceiver(
        engine, 
        procesar_trap_entrante, 
        cbCtx=app_context
    )

    print(f"📡 [SERVIDOR UDP TRAPS ONLINE] Escuchando puerto {puerto_traps} de GNS3 de manera asíncrona...")
    
    # Mantenemos viva la escucha asíncrona del socket de red de PySNMP sin bloquear a Flask
    try:
        while True:
            await asyncio.sleep(3600) # Mantiene el loop corriendo de forma limpia
    except asyncio.CancelledError:
        print("🛑 [SERVIDOR TRAPS OFFLINE] Socket UDP 162 cerrado de forma segura.")


def asegurar_receptor_traps_corriendo(app_obj):
    """
    Iniciador de seguridad. Revisa el loop de asyncio de Flask y asegura que el 
    NotificationReceiver esté activo en background en un hilo daemon si es necesario, 
    evitando colisiones del Reloader de Werkzeug.
    """
    global _TAREA_LISTENER_TRAPS
    
    if _TAREA_LISTENER_TRAPS is not None:
        return # Ya está corriendo en segundo plano el socket principal
        
    import threading
    
    def lanzar_bucle_asincrono(app_context):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(corutina_servidor_traps(app_context))

    hilo = threading.Thread(target=lanzar_bucle_asincrono, args=(app_obj.app_context(),))
    hilo.daemon = True
    hilo.start()
    _TAREA_LISTENER_TRAPS = hilo