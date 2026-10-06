"""
Servicio de cronograma - Eventos para el calendario.
"""
from datetime import date, datetime, timedelta
from typing import Optional
from src.database.db_manager import execute_query
from src.services.procesos_service import get_cierre_actual, get_procesos_cierre
from src.services.procesos_masivos_service import get_procesos_masivos
from src.services.sox_service import get_controles_sox_cierre


def get_eventos_calendario(
    cierre_id: int,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    filtro_tipo: Optional[str] = None,
    filtro_responsable: Optional[str] = None
) -> list[dict]:
    """
    Obtiene eventos consolidados para el calendario.
    Retorna lista de dicts compatibles con streamlit-calendar.
    """
    eventos = []
    
    # Procesos
    if not filtro_tipo or filtro_tipo == "Proceso":
        procesos = get_procesos_cierre(cierre_id)
        for p in procesos:
            if filtro_responsable and p.get("responsable_nombre") != filtro_responsable:
                continue
            if p["fecha_limite"]:
                try:
                    fecha = date.fromisoformat(p["fecha_limite"])
                    if fecha_desde and fecha < fecha_desde:
                        continue
                    if fecha_hasta and fecha > fecha_hasta:
                        continue
                    
                    eventos.append({
                        "id": f"proc_{p['id']}",
                        "title": f"📋 {p['nombre']}",
                        "start": fecha.isoformat(),
                        "end": (fecha + timedelta(days=1)).isoformat(),
                        "allDay": True,
                        "color": p["estado_color"],
                        "extendedProps": {
                            "tipo": "Proceso",
                            "estado": p["estado_nombre"],
                            "responsable": p.get("responsable_nombre", ""),
                            "detalle": f"Fecha límite: {fecha.strftime('%d/%m/%Y')}"
                        }
                    })
                except:
                    pass
    
    # Procesos masivos
    if not filtro_tipo or filtro_tipo == "Masivo":
        masivos = get_procesos_masivos()
        for m in masivos:
            if filtro_responsable:
                continue
            try:
                fecha = date.fromisoformat(m["fecha_ejecucion"])
                if fecha_desde and fecha < fecha_desde:
                    continue
                if fecha_hasta and fecha > fecha_hasta:
                    continue
                
                eventos.append({
                    "id": f"masivo_{m['id']}",
                    "title": f"⚙️ {m['codigo']} - {m['nombre']}",
                    "start": fecha.isoformat(),
                    "end": (fecha + timedelta(days=1)).isoformat(),
                    "allDay": True,
                    "color": m["estado_color"],
                    "extendedProps": {
                        "tipo": "Masivo",
                        "estado": m["estado_nombre"],
                        "ramo": m.get("ramo", ""),
                        "detalle": f"Ramo: {m.get('ramo', 'N/A')}"
                    }
                })
            except:
                pass
    
    # Controles SOX
    if not filtro_tipo or filtro_tipo == "SOX":
        controles = get_controles_sox_cierre(cierre_id)
        for c in controles:
            if filtro_responsable and c.get("responsable_nombre") != filtro_responsable:
                continue
            if c["fecha_ejecucion"]:
                try:
                    fecha = date.fromisoformat(c["fecha_ejecucion"])
                    if fecha_desde and fecha < fecha_desde:
                        continue
                    if fecha_hasta and fecha > fecha_hasta:
                        continue
                    
                    color = "#E24B4A" if c.get("vencido") else c["estado_color"]
                    eventos.append({
                        "id": f"sox_{c['id']}",
                        "title": f"🔒 {c['nombre']}",
                        "start": fecha.isoformat(),
                        "end": (fecha + timedelta(days=1)).isoformat(),
                        "allDay": True,
                        "color": color,
                        "extendedProps": {
                            "tipo": "SOX",
                            "estado": c.get("estado_calculado", c["estado_nombre"]),
                            "responsable": c.get("responsable_nombre", ""),
                            "detalle": f"SOX - {c.get('estado_calculado', c['estado_nombre'])}"
                        }
                    })
                except:
                    pass
    
    return eventos


def get_colores_tipos() -> dict:
    """Retorna colores consistentes por tipo de evento."""
    return {
        "Proceso": "#185FA5",
        "Masivo": "#EF9F27",
        "SOX": "#E24B4A",
        "Completado": "#639922",
        "En proceso": "#EF9F27",
        "Vencido": "#E24B4A",
        "Bloqueado": "#888780",
        "Pendiente": "#888780",
    }