"""
Servicio de alertas - Generación y gestión de alertas.
"""
from datetime import date, datetime, timedelta
from typing import Optional
import hashlib
import json
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update, transaction
from src.services.procesos_service import get_cierre_actual, get_procesos_cierre
from src.services.config_service import get_config


def generar_clave_unica(tipo: str, entidad_id: int, cierre_id: int, extra: str = "") -> str:
    """Genera una clave única para deduplicación de alertas."""
    base = f"{tipo}:{entidad_id}:{cierre_id}:{extra}"
    return hashlib.sha256(base.encode()).hexdigest()[:32]


def alerta_existe(clave_unica: str) -> bool:
    """Verifica si ya existe una alerta con esa clave."""
    row = execute_one("SELECT 1 FROM alertas WHERE clave_unica = ?", (clave_unica,))
    return row is not None


def crear_alerta(
    tipo: str,
    severidad: str,
    titulo: str,
    mensaje: str,
    cierre_id: int,
    proceso_id: Optional[int] = None,
    subtarea_id: Optional[int] = None,
    control_sox_id: Optional[int] = None,
    aprobacion_id: Optional[int] = None,
    proceso_masivo_id: Optional[int] = None,
    responsable_id: Optional[int] = None,
    fecha_limite: Optional[date] = None,
    clave_unica: Optional[str] = None
) -> Optional[int]:
    """Crea una alerta si no existe (deduplicación por clave_unica)."""
    if clave_unica and alerta_existe(clave_unica):
        return None
    
    return execute_insert(
        """INSERT INTO alertas 
           (tipo, severidad, titulo, mensaje, proceso_id, subtarea_id, control_sox_id,
            aprobacion_id, proceso_masivo_id, cierre_id, responsable_id, fecha_limite, clave_unica)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tipo, severidad, titulo, mensaje, proceso_id, subtarea_id, control_sox_id,
         aprobacion_id, proceso_masivo_id, cierre_id, responsable_id, 
         fecha_limite.isoformat() if fecha_limite else None, clave_unica)
    )


def generar_alertas_cierre(cierre_id: int) -> int:
    """Genera todas las alertas para un cierre. Retorna cantidad de alertas nuevas."""
    nuevas = 0
    hoy = date.today()
    
    # 1. Procesos vencidos
    procesos = get_procesos_cierre(cierre_id)
    for p in procesos:
        if p["fecha_limite"] and p["estado_codigo"] not in ("completado", "cancelado"):
            fecha_lim = date.fromisoformat(p["fecha_limite"])
            if fecha_lim < hoy:
                clave = generar_clave_unica("vencido", p["id"], cierre_id)
                if crear_alerta(
                    tipo="vencido",
                    severidad="Critica",
                    titulo=f"Proceso vencido: {p['nombre']}",
                    mensaje=f"El proceso '{p['nombre']}' venció el {fecha_lim.strftime('%d/%m/%Y')} y está en estado '{p['estado_nombre']}'.",
                    cierre_id=cierre_id,
                    proceso_id=p["id"],
                    responsable_id=p["responsable_id"],
                    fecha_limite=fecha_lim,
                    clave_unica=clave
                ):
                    nuevas += 1
    
    # 2. Procesos próximos a vencer (7, 3, 1 días)
    dias_anticipacion = [int(d.strip()) for d in get_config("alertas_dias_anticipacion", "7,3,1").split(",")]
    for p in procesos:
        if p["fecha_limite"] and p["estado_codigo"] not in ("completado", "cancelado"):
            fecha_lim = date.fromisoformat(p["fecha_limite"])
            dias_restantes = (fecha_lim - hoy).days
            if dias_restantes in dias_anticipacion:
                clave = generar_clave_unica("fecha_proxima", p["id"], cierre_id, str(dias_restantes))
                if crear_alerta(
                    tipo="fecha_proxima",
                    severidad="Aviso" if dias_restantes > 1 else "Critica",
                    titulo=f"Próximo vencimiento: {p['nombre']} ({dias_restantes} día{'s' if dias_restantes != 1 else ''})",
                    mensaje=f"El proceso '{p['nombre']}' vence el {fecha_lim.strftime('%d/%m/%Y')} ({dias_restantes} día{'s' if dias_restantes != 1 else ''}).",
                    cierre_id=cierre_id,
                    proceso_id=p["id"],
                    responsable_id=p["responsable_id"],
                    fecha_limite=fecha_lim,
                    clave_unica=clave
                ):
                    nuevas += 1
    
    # 3. Procesos bloqueados
    for p in procesos:
        if p["bloqueado"]:
            clave = generar_clave_unica("bloqueado", p["id"], cierre_id)
            if crear_alerta(
                tipo="bloqueado",
                severidad="Aviso",
                titulo=f"Proceso bloqueado: {p['nombre']}",
                mensaje=f"El proceso '{p['nombre']}' está bloqueado: {p['motivo_bloqueo']}.",
                cierre_id=cierre_id,
                proceso_id=p["id"],
                responsable_id=p["responsable_id"],
                clave_unica=clave
            ):
                nuevas += 1
    
    # 4. Controles SOX pendientes
    from src.services.sox_service import get_controles_sox_cierre
    controles = get_controles_sox_cierre(cierre_id)
    for c in controles:
        if c["estado_codigo"] not in ("completado", "cancelado"):
            if c["fecha_ejecucion"]:
                fecha_ejec = date.fromisoformat(c["fecha_ejecucion"])
                if fecha_ejec < hoy:
                    clave = generar_clave_unica("sox_pendiente", c["id"], cierre_id)
                    if crear_alerta(
                        tipo="sox_pendiente",
                        severidad="Critica",
                        titulo=f"Control SOX vencido: {c['nombre']}",
                        mensaje=f"El control SOX '{c['nombre']}' debía ejecutarse el {fecha_ejec.strftime('%d/%m/%Y')} y está pendiente.",
                        cierre_id=cierre_id,
                        control_sox_id=c["id"],
                        responsable_id=c["responsable_id"],
                        fecha_limite=fecha_ejec,
                        clave_unica=clave
                    ):
                        nuevas += 1
            else:
                clave = generar_clave_unica("sox_pendiente", c["id"], cierre_id)
                if crear_alerta(
                    tipo="sox_pendiente",
                    severidad="Aviso",
                    titulo=f"Control SOX pendiente: {c['nombre']}",
                    mensaje=f"El control SOX '{c['nombre']}' no tiene fecha de ejecución asignada y está pendiente.",
                    cierre_id=cierre_id,
                    control_sox_id=c["id"],
                    responsable_id=c["responsable_id"],
                    clave_unica=clave
                ):
                    nuevas += 1
    
    # 5. Aprobaciones pendientes
    from src.services.aprobaciones_service import get_aprobaciones_cierre
    aprobaciones = get_aprobaciones_cierre(cierre_id)
    for a in aprobaciones:
        # Verificar si algún estado no está completado
        estados = execute_query("SELECT codigo FROM estados WHERE id IN (?, ?, ?)",
                               (a["estado_tecnico_id"], a["estado_aprobacion_id"], a["estado_sox_id"]))
        codigos = [e["codigo"] for e in estados]
        if "completado" not in codigos:
            clave = generar_clave_unica("aprobacion_pendiente", a["id"], cierre_id)
            if crear_alerta(
                tipo="aprobacion_pendiente",
                severidad="Aviso",
                titulo=f"Aprobación pendiente: {a['nombre']}",
                mensaje=f"La aprobación '{a['nombre']}' tiene estados pendientes: Técnico={codigos[0]}, Aprobación={codigos[1]}, SOX={codigos[2]}.",
                cierre_id=cierre_id,
                aprobacion_id=a["id"],
                responsable_id=a["responsable_id"],
                clave_unica=clave
            ):
                nuevas += 1
    
    # 6. Procesos masivos próximos
    from src.services.procesos_masivos_service import get_procesos_masivos_proximos
    masivos = get_procesos_masivos_proximos(dias=7)
    for m in masivos:
        if m["estado_codigo"] not in ("completado", "cancelado"):
            fecha_ejec = date.fromisoformat(m["fecha_ejecucion"])
            dias_restantes = (fecha_ejec - hoy).days
            if dias_restantes in dias_anticipacion:
                clave = generar_clave_unica("masivo_proximo", m["id"], cierre_id, str(dias_restantes))
                if crear_alerta(
                    tipo="masivo_proximo",
                    severidad="Aviso" if dias_restantes > 1 else "Critica",
                    titulo=f"Proceso masivo próximo: {m['codigo']} - {m['nombre']} ({dias_restantes} día{'s' if dias_restantes != 1 else ''})",
                    mensaje=f"El proceso masivo '{m['codigo']} - {m['nombre']}' (Ramo: {m['ramo'] or 'N/A'}) se ejecuta el {fecha_ejec.strftime('%d/%m/%Y')}.",
                    cierre_id=cierre_id,
                    proceso_masivo_id=m["id"],
                    fecha_limite=fecha_ejec,
                    clave_unica=clave
                ):
                    nuevas += 1
    
    return nuevas


def get_alertas_cierre(cierre_id: int, solo_no_leidas: bool = False) -> list[dict]:
    """Obtiene alertas de un cierre."""
    where = "WHERE cierre_id = ?"
    params = [cierre_id]
    if solo_no_leidas:
        where += " AND leida = 0"
    
    rows = execute_query(f"""
        SELECT a.*, u.nombre as responsable_nombre, u.email as responsable_email
        FROM alertas a
        LEFT JOIN usuarios u ON a.responsable_id = u.id
        {where}
        ORDER BY 
            CASE a.severidad WHEN 'Critica' THEN 1 WHEN 'Aviso' THEN 2 ELSE 3 END,
            a.creado_en DESC
    """, tuple(params))
    return [dict(row) for row in rows]


def marcar_alerta_leida(alerta_id: int) -> bool:
    return execute_update("UPDATE alertas SET leida = 1 WHERE id = ?", (alerta_id,)) > 0


def posponer_alerta(alerta_id: int, hasta: datetime) -> bool:
    return execute_update(
        "UPDATE alertas SET pospuesta_hasta = ? WHERE id = ?",
        (hasta.isoformat(), alerta_id)
    ) > 0


def get_alertas_activas_para_toast(cierre_id: int) -> list[dict]:
    """Alertas críticas/no leídas para mostrar en toast al abrir dashboard."""
    hoy = date.today().isoformat()
    rows = execute_query("""
        SELECT * FROM alertas
        WHERE cierre_id = ? AND leida = 0
        AND (pospuesta_hasta IS NULL OR pospuesta_hasta <= datetime('now'))
        AND severidad IN ('Critica', 'Aviso')
        ORDER BY 
            CASE severidad WHEN 'Critica' THEN 1 ELSE 2 END,
            creado_en DESC
        LIMIT 5
    """, (cierre_id,))
    return [dict(row) for row in rows]


def encolar_evento_salida(
    tipo_alerta: str,
    severidad: str,
    clave_unica: str,
    payload: dict,
    canal: str = "teams"
) -> int:
    """Encola un evento para envío a Teams."""
    # Verificar si ya existe evento pendiente/enviado con misma clave
    row = execute_one(
        "SELECT id, estado FROM eventos_salida WHERE clave_unica = ?", (clave_unica,)
    )
    if row and row["estado"] in ("Pendiente", "Enviado"):
        return row["id"]
    
    return execute_insert(
        """INSERT INTO eventos_salida (tipo_alerta, severidad, clave_unica, payload_json, canal, estado)
           VALUES (?, ?, ?, ?, ?, 'Pendiente')""",
        (tipo_alerta, severidad, clave_unica, json.dumps(payload, ensure_ascii=False), canal)
    )


def get_eventos_pendientes(limite: int = 50) -> list[dict]:
    rows = execute_query("""
        SELECT * FROM eventos_salida
        WHERE estado IN ('Pendiente', 'Error')
        ORDER BY creado_en
        LIMIT ?
    """, (limite,))
    return [dict(row) for row in rows]


def marcar_evento_enviado(evento_id: int) -> bool:
    return execute_update(
        "UPDATE eventos_salida SET estado = 'Enviado', enviado_en = datetime('now') WHERE id = ?",
        (evento_id,)
    ) > 0


def marcar_evento_error(evento_id: int, error: str) -> bool:
    return execute_update(
        "UPDATE eventos_salida SET estado = 'Error', intentos = intentos + 1, ultimo_error = ? WHERE id = ?",
        (error, evento_id)
    ) > 0


def descartar_evento(evento_id: int) -> bool:
    return execute_update(
        "UPDATE eventos_salida SET estado = 'Omitido' WHERE id = ?",
        (evento_id,)
    ) > 0


def reintentar_evento(evento_id: int) -> bool:
    return execute_update(
        "UPDATE eventos_salida SET estado = 'Pendiente', ultimo_error = NULL WHERE id = ?",
        (evento_id,)
    ) > 0