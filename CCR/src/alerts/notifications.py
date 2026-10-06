"""
Sistema de notificaciones - Interfaz común y implementaciones (Toast, Panel, Teams).
"""
from abc import ABC, abstractmethod
from typing import Optional
import streamlit as st
from src.ui.theme import alert_row, ICONS


class Notificador(ABC):
    """Interfaz base para notificadores."""
    
    @abstractmethod
    def enviar(self, evento: dict) -> tuple[bool, str]:
        """
        Envía una notificación.
        Retorna (exito, mensaje_error).
        """
        pass
    
    @abstractmethod
    def nombre(self) -> str:
        """Nombre identificador del notificador."""
        pass


class ToastNotificador(Notificador):
    """Notificador via st.toast (siempre activo, en pantalla)."""
    
    def nombre(self) -> str:
        return "toast"
    
    def enviar(self, evento: dict) -> tuple[bool, str]:
        try:
            payload = evento.get("payload_json", "{}")
            import json
            data = json.loads(payload)
            titulo = data.get("titulo", "Alerta")
            mensaje = data.get("mensaje", "")
            severidad = data.get("severidad", "Info")
            
            icon_map = {
                "Critica": "🔴",
                "Aviso": "🟡",
                "Info": "🔵"
            }
            icon = icon_map.get(severidad, "🔔")
            
            st.toast(f"{icon} {titulo}: {mensaje}", icon="⚠️" if severidad == "Critica" else "ℹ️")
            return True, ""
        except Exception as e:
            return False, str(e)


class PanelNotificador(Notificador):
    """Notificador via panel de alertas en la UI (siempre activo)."""
    
    def nombre(self) -> str:
        return "panel"
    
    def enviar(self, evento: dict) -> tuple[bool, str]:
        # El panel se renderiza automáticamente leyendo la BD
        # Este notificador solo marca que el evento fue "procesado" para el panel
        return True, ""


# Registro de notificadores disponibles
_NOTIFICADORES = {
    "toast": ToastNotificador(),
    "panel": PanelNotificador(),
}


def get_notificador(nombre: str) -> Optional[Notificador]:
    return _NOTIFICADORES.get(nombre)


def get_todos_notificadores() -> list[Notificador]:
    return list(_NOTIFICADORES.values())


def registrar_notificador(nombre: str, notificador: Notificador):
    _NOTIFICADORES[nombre] = notificador


def notificar_todos(evento: dict) -> dict:
    """Envía evento a todos los notificadores registrados. Retorna dict con resultados."""
    resultados = {}
    for nombre, notif in _NOTIFICADORES.items():
        try:
            ok, error = notif.enviar(evento)
            resultados[nombre] = {"exito": ok, "error": error}
        except Exception as e:
            resultados[nombre] = {"exito": False, "error": str(e)}
    return resultados


def mostrar_toast_alertas_cierre(cierre_id: int):
    """Muestra toasts para alertas activas del cierre (llamar en dashboard)."""
    from src.services.alertas_service import get_alertas_activas_para_toast
    
    alertas = get_alertas_activas_para_toast(cierre_id)
    for alerta in alertas:
        severidad = alerta["severidad"]
        icon_map = {"Critica": "🔴", "Aviso": "🟡", "Info": "🔵"}
        icon = icon_map.get(severidad, "🔔")
        st.toast(f"{icon} {alerta['titulo']}: {alerta['mensaje']}", 
                 icon="⚠️" if severidad == "Critica" else "ℹ️")


def render_panel_alertas(cierre_id: int, solo_no_leidas: bool = False):
    """Renderiza el panel completo de alertas con filtros."""
    from src.services.alertas_service import get_alertas_cierre, marcar_alerta_leida, posponer_alerta
    from src.ui.theme import status_dot, badge
    from datetime import datetime, timedelta
    
    alertas = get_alertas_cierre(cierre_id, solo_no_leidas)
    
    if not alertas:
        st.info("No hay alertas para mostrar.")
        return
    
    # Filtros
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        severidad_filtro = st.selectbox(
            "Severidad", ["Todas", "Critica", "Aviso", "Info"], key="filtro_severidad"
        )
    with col2:
        tipo_filtro = st.selectbox(
            "Tipo", ["Todos", "vencido", "fecha_proxima", "bloqueado", "sox_pendiente", "aprobacion_pendiente", "masivo_proximo"],
            key="filtro_tipo"
        )
    with col3:
        if st.button("Marcar todas leídas", key="marcar_todas_leidas"):
            for a in alertas:
                if not a["leida"]:
                    marcar_alerta_leida(a["id"])
            st.rerun()
    
    # Aplicar filtros
    if severidad_filtro != "Todas":
        alertas = [a for a in alertas if a["severidad"] == severidad_filtro]
    if tipo_filtro != "Todos":
        alertas = [a for a in alertas if a["tipo"] == tipo_filtro]
    
    # Renderizar alertas
    for alerta in alertas:
        with st.container():
            cols = st.columns([1, 10, 2, 1])
            
            # Punto de severidad
            with cols[0]:
                sev_color = {"Critica": "rojo", "Aviso": "ambar", "Info": "azul"}.get(alerta["severidad"], "gris")
                st.markdown(f'<span class="ccr-status-dot ccr-status-dot--{sev_color}" style="margin-top: 6px;"></span>', 
                           unsafe_allow_html=True)
            
            # Contenido
            with cols[1]:
                leida_badge = "" if alerta["leida"] else ' <span class="ccr-badge ccr-badge--azul">Nueva</span>'
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <strong>{alerta['titulo']}</strong>{leida_badge}
                    </div>
                    <div style="font-size: 12px; color: #5F5E5A; margin-top: 2px;">{alerta['mensaje']}</div>
                    <div style="font-size: 11px; color: #888780; margin-top: 4px;">
                        {alerta.get('responsable_nombre', 'Sin responsable')} · {alerta['creado_en'][:16].replace('T', ' ')}
                    </div>
                """, unsafe_allow_html=True)
            
            # Acciones
            with cols[2]:
                if not alerta["leida"]:
                    if st.button("Leída", key=f"leida_{alerta['id']}", use_container_width=True):
                        marcar_alerta_leida(alerta["id"])
                        st.rerun()
            
            with cols[3]:
                if st.button("⏰", key=f"posponer_{alerta['id']}", help="Posponer 24h"):
                    posponer_alerta(alerta["id"], datetime.now() + timedelta(hours=24))
                    st.rerun()
            
            st.divider()