"""
Scheduler de alertas - Genera alertas y procesa cola de eventos al abrir/refrescar la app.
"""
import streamlit as st
from src.services.alertas_service import (
    generar_alertas_cierre, get_cierre_actual, encolar_evento_salida, get_eventos_pendientes,
    marcar_evento_enviado, marcar_evento_error
)
from src.alerts.power_automate import enviar_evento_teams
from src.services.config_service import get_config


def ejecutar_scheduler():
    """
    Ejecuta el scheduler de alertas:
    1. Genera alertas nuevas para el cierre actual
    2. Procesa la cola de eventos pendientes para Teams
    Debe llamarse al inicio de cada página principal.
    """
    # Evitar ejecución múltiple en misma sesión
    if st.session_state.get("_scheduler_ejecutado"):
        return
    st.session_state["_scheduler_ejecutado"] = True
    
    cierre = get_cierre_actual()
    if not cierre:
        return
    
    # 1. Generar alertas nuevas
    try:
        nuevas = generar_alertas_cierre(cierre.id)
        if nuevas > 0:
            # Encolar eventos para Teams si está activado
            if get_config("alertas_teams_activado", "false").lower() == "true":
                encolar_alertas_para_teams(cierre.id)
    except Exception as e:
        # Log silencioso, no romper la app
        print(f"[Scheduler] Error generando alertas: {e}")
    
    # 2. Procesar cola de eventos Teams
    try:
        procesar_cola_teams()
    except Exception as e:
        print(f"[Scheduler] Error procesando cola Teams: {e}")


def encolar_alertas_para_teams(cierre_id: int):
    """Encola alertas no enviadas como eventos de salida para Teams."""
    from src.database.db_manager import execute_query
    from src.alerts.power_automate import construir_payload_alerta
    
    # Obtener alertas que no tienen evento_salida correspondiente
    alertas = execute_query("""
        SELECT a.* FROM alertas a
        LEFT JOIN eventos_salida es ON es.clave_unica = a.clave_unica
        WHERE a.cierre_id = ? AND es.id IS NULL
        AND a.severidad IN ('Aviso', 'Critica')
    """, (cierre_id,))
    
    for alerta in alertas:
        payload = construir_payload_alerta(alerta)
        encolar_evento_salida(
            tipo_alerta=alerta["tipo"],
            severidad=alerta["severidad"],
            clave_unica=alerta["clave_unica"],
            payload=payload,
            canal="teams"
        )


def procesar_cola_teams():
    """Procesa eventos pendientes de envío a Teams."""
    if get_config("alertas_teams_activado", "false").lower() != "true":
        return
    
    url_teams = get_config("alertas_teams_url", "")
    if not url_teams:
        return
    
    # Verificar horario silencioso
    if _en_horario_silencioso():
        return
    
    eventos = get_eventos_pendientes(limite=10)
    if not eventos:
        return
    
    # Verificar límite por hora
    if _excede_limite_hora():
        return
    
    for evento in eventos:
        if evento["estado"] == "Pendiente":
            ok, error = enviar_evento_teams(evento["payload_json"], url_teams)
            if ok:
                marcar_evento_enviado(evento["id"])
            else:
                marcar_evento_error(evento["id"], error)
                # No seguir procesando si hay error de red
                if "timeout" in error.lower() or "connection" in error.lower():
                    break


def _en_horario_silencioso() -> bool:
    """Verifica si estamos en horario silencioso."""
    from datetime import datetime
    inicio = get_config("alertas_horario_silencioso_inicio", "19:00")
    fin = get_config("alertas_horario_silencioso_fin", "07:00")
    
    ahora = datetime.now().time()
    inicio_t = datetime.strptime(inicio, "%H:%M").time()
    fin_t = datetime.strptime(fin, "%H:%M").time()
    
    if inicio_t > fin_t:  # Cruza medianoche (ej. 19:00 - 07:00)
        return ahora >= inicio_t or ahora <= fin_t
    else:
        return inicio_t <= ahora <= fin_t


def _excede_limite_hora() -> bool:
    """Verifica si se excedió el límite de mensajes por hora."""
    from src.database.db_manager import execute_one
    from datetime import datetime, timedelta
    
    limite = int(get_config("alertas_limite_por_hora", "10"))
    hace_una_hora = (datetime.now() - timedelta(hours=1)).isoformat()
    
    row = execute_one("""
        SELECT COUNT(*) as cnt FROM eventos_salida
        WHERE estado = 'Enviado' AND enviado_en >= ?
    """, (hace_una_hora,))
    
    return row["cnt"] >= limite if row else False


def forzar_refresh_scheduler():
    """Fuerza re-ejecución del scheduler (para botón de refrescar)."""
    st.session_state["_scheduler_ejecutado"] = False
    ejecutar_scheduler()