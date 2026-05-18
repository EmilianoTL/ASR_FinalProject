import os
import asyncio
import threading
import time
from flask import current_app
from database.models import db, MetricaOctetos

# Importaciones oficiales y recomendadas para PySNMP v7.1
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine, UdpTransportTarget, ContextData, CommunityData, ObjectType, ObjectIdentity, walk_cmd, get_cmd
from pysnmp.entity.rfc3413 import ntfrcv  # API estándar de entidad según ntfrcv.py
from pysnmp.carrier.asyncio.dgram import udp  # Transporte nativo de asyncio (base.py)
from pysnmp.entity import config  # API oficial de configuración de entidad

# Variables Globales de Control de Infraestructura
_HILO_LISTENER_TRAPS = None
_LOCK_LISTENER = threading.Lock()  # Previene condiciones de carrera en hilos

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
def procesar_trap_entrante(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    """
    Firma estricta de 6 argumentos alineada perfectamente con ntfrcv.py:104-106.
    Procesa de manera eficiente las trampas capturadas en el puerto 162.
    """
    from database.models import db, EventoTrap, Router
    
    app_context = cbCtx
    app_obj = app_context.app
    
    OID_LINK_DOWN = '1.3.6.1.6.3.1.1.5.3'
    OID_LINK_UP = '1.3.6.1.6.3.1.1.5.4'
    OID_IF_DESCR = '1.3.6.1.2.1.2.2.1.2'

    tipo_evento = "Desconocido"
    interfaz_afectada = "Desconocida"
    ip_origen = "Desconocida"

    try:
        transport_info = snmpEngine.transportDispatcher.getTransportInfo(stateReference)
        if transport_info:
            ip_origen = transport_info[1][0]
    except Exception:
        pass

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

        # REGLA FILTRADO ESTRICTO (POST/DELETE)
        if not app_obj.hilos_snmp_activos.get(identificador_unico, False):
            return

        print(f"\n🔔 [TRAP CAPTURADO v7.1] -> Evento detectado para interfaz activa: {identificador_unico}")
        
        nuevo_evento = EventoTrap(
            router_hostname=hostname,
            interfaz_api=interfaz_afectada,
            tipo_evento=tipo_evento
        )
        db.session.add(nuevo_evento)
        db.session.commit()
        print(f"   💾 [BD GUARDADO] -> Estado: {tipo_evento}")


def ejecutar_servidor_traps_sincrono(app_context):
    """
    Levanta un socket UDP e implementa de forma matemática runDispatcher() y jobStarted(1).
    Alineado con dispatch.py:58-61 y base.py:90-99.
    """
    puerto_traps = int(os.getenv('SNMP_PORT_TRAPS', 162))
    ip_escucha = "0.0.0.0" 

    # 1. Registro del transporte usando udp.DOMAIN (v7.1 estricto)
    # SOLUCIÓN COMPLEMENTARIA: Le asignamos un event loop propio a este hilo 
    # para que los componentes internos de asyncio de PySNMP v7 no se rompan
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    snmp_engine = SnmpEngine()

    # Tu corrección exacta para el enlace del socket
    try:
        config.addTransport(
            snmp_engine,
            udp.domainName,  # <--- Tu corrección exitosa
            udp.UdpTransport().openServerMode((ip_escucha, puerto_traps))
        )
    except Exception as e:
        print(f"❌ [FALLO PUERTO 162] Error crítico de enlace de socket. ¿Es root? Detalle: {e}")
        return

    # Registrar el NotificationReceiver
    ntfrcv.NotificationReceiver(
        snmp_engine, 
        procesar_trap_entrante, 
        cbCtx=app_context
    )

    # Forzar persistencia del bucle de red
    snmp_engine.transportDispatcher.jobStarted(1)

    print(f"📡 [SERVIDOR UDP TRAPS ONLINE] Escuchando perpetuamente en el puerto {puerto_traps}...")

    # Inicializar el loop de sockets de PySNMP
    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except Exception as e:
        print(f"⚠️ [SERVIDOR TRAPS] Interrupción en el bucle de despacho de red: {e}")
    finally:
        try:
            snmp_engine.transportDispatcher.jobFinished(1)
            snmp_engine.transportDispatcher.closeDispatcher()
        except Exception:
            pass
        loop.close()  # Cerramos el loop local del hilo al finalizar
        print("🛑 [SERVIDOR TRAPS OFFLINE] Socket UDP 162 liberado del sistema.")


def asegurar_receptor_traps_corriendo(app_obj):
    """
    Administrador de hilos con bloqueo (Mutex Lock). Evita colisiones de puertos 
    causadas por el doble proceso del Reloader de Flask (Werkzeug).
    """
    global _HILO_LISTENER_TRAPS
    
    with _LOCK_LISTENER:
        if _HILO_LISTENER_TRAPS is not None and _HILO_LISTENER_TRAPS.is_alive():
            return  # El socket ya está abierto y corriendo felizmente

        # Levantamos el socket en un hilo daemon aislado
        hilo = threading.Thread(
            target=ejecutar_servidor_traps_sincrono, 
            args=(app_obj.app_context(),)
        )
        hilo.daemon = True
        hilo.start()
        _HILO_LISTENER_TRAPS = hilo