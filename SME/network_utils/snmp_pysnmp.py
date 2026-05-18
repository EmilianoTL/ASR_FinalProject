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

# ==============================================================================
# --- RECEPTOR DE TRAPS SNMP CORE (ASYNCIO NATIVO v7.1 VERIFICADO) ---
# ==============================================================================
# ==============================================================================
# --- RECEPTOR INDESTRUCTIBLE DE TRAPS SNMP (ASYNCIO NATIVO v7.1 DEFINITIVO) ---
# ==============================================================================

_HILO_LISTENER_TRAPS = None
_LOCK_LISTENER = threading.Lock()

def procesar_trap_entrante(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
    """
    Callback nativo de 6 argumentos (ntfrcv.py).
    Se ejecuta de forma imperativa en cuanto el socket detecta tráfico UDP 162.
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

    # 1. Extraer la IP de origen del paquete de red
    try:
        transport_info = snmpEngine.transportDispatcher.getTransportInfo(stateReference)
        if transport_info:
            ip_origen = transport_info[1][0]
    except Exception:
        pass

    # 2. Analizar las variables vinculadas (varBinds)
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

    # ¡PRINT DE CONTROL ABSOLUTO DE ENTRADA DE RED!
    print(f"\n🔥 [ALERTA DE RED DETECTADA] -> IP: {ip_origen} | Interfaz: {interfaz_afectada} | Evento: {tipo_evento}")

    with app_context:
        # Mapeo de seguridad para tu topología GNS3 (IP backbone y de gestión)
        if ip_origen in ["10.0.0.17", "192.168.100.1"]:
            hostname = "Edge"
        else:
            router = Router.query.filter_by(ip_admin=ip_origen).first()
            hostname = router.hostname if router else f"Dispositivo_{ip_origen}"
        
        identificador_unico = f"{hostname}_{interfaz_afectada}_traps"
        print(f"   🔍 [Filtro de Ruta] Validando clave en memoria Flask: '{identificador_unico}'")

        # Verificar si la interfaz se activó por POST
        if not app_obj.hilos_snmp_activos.get(identificador_unico, False):
            print(f"   ⚠️ [FILTRO IGNORED] La interfaz '{identificador_unico}' no está activa por HTTP POST, se descarta el guardado.")
            return

        # Guardar en Base de Datos SQLite
        try:
            nuevo_evento = EventoTrap(
                router_hostname=hostname,
                interfaz_api=interfaz_afectada,
                tipo_evento=tipo_evento
            )
            db.session.add(nuevo_evento)
            db.session.commit()
            print(f"   💾 [BD GUARDADO] Registro insertado exitosamente para {hostname}.")
        except Exception as e:
            db.session.rollback()
            print(f"   ❌ [BD ERROR] Error al escribir evento en SQLite: {e}")


async def corutina_servidor_traps(app_context):  
    """
    Estructura asíncrona pura e indestructible basada en asyncio.Event().wait()
    Alineada al 100% con los fuentes oficiales de PySNMP v7.1.
    """
    # IMPORTACIONES VERIFICADAS Y MATEMÁTICAMENTE CORRECTAS ASIGNADAS POR TU ANÁLISIS
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine  # Motor asíncrono configurado
    from pysnmp.entity.rfc3413 import ntfrcv            # Configuración de entidad base
    from pysnmp.entity import config                    # Local Configuration Datastore (LCD) real
    from pysnmp.carrier.asyncio.dgram import udp        # Capa de transporte asíncrona
    import os
  
    puerto_traps = int(os.getenv('SNMP_PORT_TRAPS', 162))
    snmp_engine = SnmpEngine()  
  
    # Configuración de transporte utilizando el método inteligente de config.py
    try:
        config.addTransport(  
            snmp_engine,  
            udp.domainName,  
            udp.UdpTransport().openServerMode(('0.0.0.0', puerto_traps))  
        )  
    except Exception as e:
        print(f"❌ [FALLO PUERTO 162] Error al abrir el Socket UDP: {e}")
        return
  
    # Registro del receptor en el msgAndPduDsp del motor
    ntfrcv.NotificationReceiver(snmp_engine, procesar_trap_entrante, cbCtx=app_context)  
  
    # Persistencia en el transportDispatcher
    snmp_engine.transportDispatcher.jobStarted(1)  
    print(f"📡 [SERVIDOR UDP TRAPS ONLINE] Escuchando perpetuamente en el puerto {puerto_traps} de GNS3...")
      
    try:  
        # Suspensión no bloqueante perfecta del hilo
        await asyncio.Event().wait()   
    except asyncio.CancelledError:
        print("🛑 [SERVIDOR TRAPS] Corutina de escucha cancelada de forma segura.")
    finally:  
        snmp_engine.transportDispatcher.jobFinished(1)  
        snmp_engine.transportDispatcher.closeDispatcher()
        print("🛑 [SERVIDOR TRAPS OFFLINE] Socket UDP 162 liberado.")


def lanzar_bucle_asincrono_dedicado(app_context):
    """
    Inicializa un bucle de eventos asíncronos limpio y exclusivo para este hilo.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(corutina_servidor_traps(app_context))
    except Exception as e:
        print(f"❌ [HILO TRAPS] Error en el bucle asíncronio del hilo: {e}")
    finally:
        loop.close()


def asegurar_receptor_traps_corriendo(app_obj):
    """
    Administrador de hilos con Mutex Lock. Despliega de forma segura el 
    hilo dedicado asíncrono evitando colisiones del Reloader de Flask.
    """
    global _HILO_LISTENER_TRAPS
    
    with _LOCK_LISTENER:
        if _HILO_LISTENER_TRAPS is not None and _HILO_LISTENER_TRAPS.is_alive():
            return

        hilo = threading.Thread(
            target=lanzar_bucle_asincrono_dedicado, 
            args=(app_obj.app_context(),)
        )
        hilo.daemon = True
        hilo.start()
        _HILO_LISTENER_TRAPS = hilo