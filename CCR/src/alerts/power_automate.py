"""
Integración con Microsoft Teams vía Power Automate.
Envía POST JSON usando urllib (stdlib only).
"""
import urllib.request
import urllib.error
import json
import time
from typing import Optional
from src.services.config_service import get_config


def construir_payload_alerta(alerta: dict) -> dict:
    """Construye el payload JSON estándar para Power Automate."""
    from src.services.procesos_service import get_cierre_actual
    from src.services.config_service import get_config
    
    cierre = get_cierre_actual()
    periodo = f"{cierre.año}-{cierre.mes:02d}" if cierre else "2026-10"
    app_url = get_config("app_url_base", "http://localhost:8501")
    
    # Obtener email del responsable
    responsable_email = alerta.get("responsable_email", "")
    
    payload = {
        "schema_version": "1.0",
        "event_id": alerta.get("clave_unica", ""),
        "tipo": alerta.get("tipo", ""),
        "severidad": alerta.get("severidad", "Info"),
        "titulo": alerta.get("titulo", ""),
        "mensaje": alerta.get("mensaje", ""),
        "proceso": alerta.get("proceso_nombre", "") or alerta.get("nombre", ""),
        "periodo": periodo,
        "responsable": alerta.get("responsable_nombre", ""),
        "responsable_email": responsable_email,
        "fecha_limite": alerta.get("fecha_limite", ""),
        "enlace_app": f"{app_url}/Procesos",
        "generado_en": alerta.get("creado_en", "")
    }
    
    # Agregar Adaptive Card opcional
    if get_config("alertas_teams_adaptive_card", "false").lower() == "true":
        payload["card"] = construir_adaptive_card(payload)
    
    return payload


def construir_adaptive_card(data: dict) -> dict:
    """Construye una Adaptive Card para Teams."""
    sev_colors = {
        "Critica": "#E24B4A",
        "Aviso": "#EF9F27",
        "Info": "#185FA5"
    }
    color = sev_colors.get(data.get("severidad", "Info"), "#185FA5")
    
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "Container",
                "style": "emphasis",
                "bleed": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "🔔 CCR - Alerta de Cierre Actuarial",
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Accent",
                        "wrap": True
                    }
                ]
            },
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": data.get("titulo", ""),
                        "weight": "Bolder",
                        "size": "Large",
                        "wrap": True,
                        "color": "Attention" if data.get("severidad") == "Critica" else "Default"
                    },
                    {
                        "type": "TextBlock",
                        "text": data.get("mensaje", ""),
                        "wrap": True,
                        "size": "Medium",
                        "spacing": "Medium"
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Proceso:", "value": data.get("proceso", "N/A")},
                            {"title": "Período:", "value": data.get("periodo", "N/A")},
                            {"title": "Responsable:", "value": data.get("responsable", "N/A")},
                            {"title": "Severidad:", "value": data.get("severidad", "Info")},
                            {"title": "Fecha límite:", "value": data.get("fecha_limite", "N/A")[:10] if data.get("fecha_limite") else "N/A"}
                        ],
                        "spacing": "Medium"
                    }
                ],
                "spacing": "Medium"
            },
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "Ver en CCR",
                        "url": data.get("enlace_app", "")
                    }
                ],
                "spacing": "Medium"
            }
        ],
        "backgroundImage": {
            "url": "",
            "fillMode": "Cover"
        }
    }


def enviar_evento_teams(payload_json: str, url_webhook: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Envía evento a Power Automate via HTTP POST.
    Retorna (exito, mensaje_error).
    Nunca debe romper la app.
    """
    if not url_webhook:
        return False, "URL de Power Automate no configurada"
    
    try:
        data = payload_json.encode("utf-8")
        req = urllib.request.Request(
            url_webhook,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CCR-Actuarial/1.0"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return True, ""
            else:
                return False, f"HTTP {response.status}: {response.read().decode('utf-8', errors='ignore')}"
    
    except urllib.error.URLError as e:
        return False, f"Error de red: {e.reason}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}"
    except TimeoutError:
        return False, "Timeout (10s)"
    except Exception as e:
        return False, f"Error inesperado: {type(e).__name__}: {e}"


def enviar_mensaje_prueba(url_webhook: str) -> tuple[bool, str]:
    """Envía un mensaje de prueba a Teams."""
    payload = {
        "schema_version": "1.0",
        "event_id": "test-" + str(int(time.time())),
        "tipo": "test",
        "severidad": "Info",
        "titulo": "✅ Prueba de conexión CCR → Teams",
        "mensaje": "Este es un mensaje de prueba desde el Centro de Control de Reservas y Cierres Actuariales. Si ves esto, la integración funciona correctamente.",
        "proceso": "Sistema",
        "periodo": "2026-10",
        "responsable": "Usuario de prueba",
        "responsable_email": "",
        "fecha_limite": "",
        "enlace_app": get_config("app_url_base", "http://localhost:8501"),
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    
    if get_config("alertas_teams_adaptive_card", "false").lower() == "true":
        payload["card"] = construir_adaptive_card(payload)
    
    return enviar_evento_teams(json.dumps(payload, ensure_ascii=False), url_webhook)


def log_tecnico(mensaje: str):
    """Registra en bitácora técnica (data/ccr.log) sin exponer URL completa."""
    from pathlib import Path
    from datetime import datetime
    
    log_path = Path(__file__).parent.parent.parent / "data" / "ccr.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Enmascarar URL si está en el mensaje
    import re
    mensaje_limpio = re.sub(r'https?://[^\s]+', '[URL_ENMASCARADA]', mensaje)
    
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} | {mensaje_limpio}\n")