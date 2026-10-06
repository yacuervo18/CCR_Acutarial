"""
Datos semilla para CCR.
13 procesos iniciales, estados, prioridades, tipos de evidencia, colores.
Todo editable desde Configuración.
"""
import json
from datetime import date, datetime
from src.database.db_manager import (
    get_connection, execute_insert, execute_query, execute_one, transaction
)


# ============================================================
# DATOS SEMILLA
# ============================================================

ESTADOS_SEMILLA = [
    {"codigo": "pendiente", "nombre": "Pendiente", "color": "#888780", "orden": 1},
    {"codigo": "en_proceso", "nombre": "En Proceso", "color": "#EF9F27", "orden": 2},
    {"codigo": "bloqueado", "nombre": "Bloqueado", "color": "#888780", "orden": 3},
    {"codigo": "pendiente_aprobacion", "nombre": "Pendiente Aprobación", "color": "#185FA5", "orden": 4},
    {"codigo": "completado", "nombre": "Completado", "color": "#639922", "orden": 5},
    {"codigo": "cancelado", "nombre": "Cancelado", "color": "#5F5E5A", "orden": 6},
]

PRIORIDADES_SEMILLA = [
    {"codigo": "baja", "nombre": "Baja", "color": "#639922", "orden": 1},
    {"codigo": "media", "nombre": "Media", "color": "#185FA5", "orden": 2},
    {"codigo": "alta", "nombre": "Alta", "color": "#EF9F27", "orden": 3},
    {"codigo": "critica", "nombre": "Crítica", "color": "#E24B4A", "orden": 4},
]

TIPOS_EVIDENCIA_SEMILLA = [
    {"codigo": "pdf", "nombre": "PDF", "extensiones_permitidas": json.dumps([".pdf"]), "tamaño_max_mb": 20},
    {"codigo": "excel", "nombre": "Excel", "extensiones_permitidas": json.dumps([".xlsx", ".xls", ".csv"]), "tamaño_max_mb": 10},
    {"codigo": "correo", "nombre": "Correo", "extensiones_permitidas": json.dumps([".msg", ".eml"]), "tamaño_max_mb": 5},
    {"codigo": "imagen", "nombre": "Imagen", "extensiones_permitidas": json.dumps([".png", ".jpg", ".jpeg", ".bmp"]), "tamaño_max_mb": 10},
    {"codigo": "captura", "nombre": "Captura de pantalla", "extensiones_permitidas": json.dumps([".png", ".jpg", ".jpeg"]), "tamaño_max_mb": 5},
    {"codigo": "enlace", "nombre": "Enlace / Ruta de red", "extensiones_permitidas": json.dumps([]), "tamaño_max_mb": 0},
]

USUARIOS_SEMILLA = [
    {"nombre": "Usuario Actual", "email": "usuario@empresa.com"},
]

PROCESOS_SEMILLA = [
    {
        "nombre": "Rentabilidades",
        "descripcion": "Cálculo y actualización de rentabilidades para reservas",
        "prioridad_codigo": "alta",
        "dias_duracion_estimada": 2,
        "orden": 1,
        "subtareas": [
            "Recopilar tasas de mercado",
            "Actualizar curvas de rentabilidad",
            "Validar consistencia",
            "Generar reporte de rentabilidades"
        ],
        "dependencias": []
    },
    {
        "nombre": "Índices y Monedas",
        "descripcion": "Actualización de índices económicos y tasas de cambio",
        "prioridad_codigo": "media",
        "dias_duracion_estimada": 1,
        "orden": 2,
        "subtareas": [
            "Descargar índices oficiales",
            "Actualizar tasas de cambio",
            "Validar fuentes",
            "Publicar en repositorio"
        ],
        "dependencias": []
    },
    {
        "nombre": "F394",
        "descripcion": "Reporte mensual de reserva matemática F394 (incluye Correcciones ARL)",
        "prioridad_codigo": "critica",
        "dias_duracion_estimada": 3,
        "orden": 3,
        "subtareas": [
            "Actualizar rentabilidades (insumo)",
            "Enviar correo a Carlos",
            "Esperar confirmación",
            "Programar ramo 087",
            "Programar ramo 088",
            "Programar ramo 093",
            "Revisar ejecución",
            "Validar generación",
            "Aplicar correcciones ARL",
            "Validar resultados ARL",
            "Documentar cambios ARL"
        ],
        "dependencias": ["Rentabilidades", "Índices y Monedas"]
    },
    {
        "nombre": "Reserva Salario Mínimo",
        "descripcion": "Cálculo de reserva por salario mínimo",
        "prioridad_codigo": "alta",
        "dias_duracion_estimada": 2,
        "orden": 4,
        "subtareas": [
            "Obtener salario mínimo vigente",
            "Calcular reservas afectadas",
            "Aplicar fórmula",
            "Validar resultados"
        ],
        "dependencias": ["Índices y Monedas"]
    },
    {
        "nombre": "Reserva de siniestros avisados (RBNS)",
        "descripcion": "Cálculo de reserva de siniestros avisados (RBNS)",
        "prioridad_codigo": "critica",
        "dias_duracion_estimada": 2,
        "orden": 5,
        "subtareas": [
            "Identificar siniestros avisados",
            "Calcular reservas por siniestro",
            "Validar suficiencia",
            "Generar reporte RBNS"
        ],
        "dependencias": ["F394"]
    },
    {
        "nombre": "Reserva Matemática Ley 100",
        "descripcion": "Cálculo de reserva matemática bajo Ley 100",
        "prioridad_codigo": "critica",
        "dias_duracion_estimada": 3,
        "orden": 6,
        "subtareas": [
            "Parametrización modelo",
            "Ejecución cálculo",
            "Revisar resultados",
            "Conciliar con contabilidad",
            "Generar reporte"
        ],
        "dependencias": ["Rentabilidades", "Reserva Salario Mínimo"]
    },
    {
        "nombre": "Reserva Matemática Conmutación",
        "descripcion": "Cálculo de reserva matemática por conmutación",
        "prioridad_codigo": "alta",
        "dias_duracion_estimada": 2,
        "orden": 7,
        "subtareas": [
            "Identificar pólizas a conmutar",
            "Calcular valores de conmutación",
            "Validar con área técnica",
            "Contabilizar"
        ],
        "dependencias": ["Reserva Matemática Ley 100"]
    },
    {
        "nombre": "Reserva Matemática ARL",
        "descripcion": "Cálculo de reserva matemática ramo ARL (IBNR + RBNS)",
        "prioridad_codigo": "critica",
        "dias_duracion_estimada": 3,
        "orden": 8,
        "subtareas": [
            "Actualizar siniestralidad",
            "Calcular IBNR",
            "Calcular RBNS",
            "Validar suficiencia",
            "Generar reporte técnico"
        ],
        "dependencias": ["F394", "Reserva de siniestros avisados (RBNS)"]
    },
]

CONFIG_SEMILLA = {
    "app_url_base": "http://localhost:8501",
    "alertas_dias_anticipacion": "7,3,1",
    "alertas_horario_silencioso_inicio": "19:00",
    "alertas_horario_silencioso_fin": "07:00",
    "alertas_limite_por_hora": "10",
    "alertas_modo": "individual",  # individual, resumen, ambos
    "alertas_teams_activado": "false",
    "alertas_teams_url": "",
    "alertas_teams_adaptive_card": "false",
    "evidencias_tamaño_max_mb": "20",
    "usuario_actual": "Usuario Actual",
}


def get_estado_id(codigo: str) -> int:
    row = execute_one("SELECT id FROM estados WHERE codigo = ?", (codigo,))
    return row["id"] if row else None


def get_prioridad_id(codigo: str) -> int:
    row = execute_one("SELECT id FROM prioridades WHERE codigo = ?", (codigo,))
    return row["id"] if row else None


def get_tipo_evidencia_id(codigo: str) -> int:
    row = execute_one("SELECT id FROM tipos_evidencia WHERE codigo = ?", (codigo,))
    return row["id"] if row else None


def get_usuario_id(nombre: str) -> int:
    row = execute_one("SELECT id FROM usuarios WHERE nombre = ?", (nombre,))
    return row["id"] if row else None


def seed_estados():
    for e in ESTADOS_SEMILLA:
        exists = execute_one("SELECT 1 FROM estados WHERE codigo = ?", (e["codigo"],))
        if not exists:
            execute_insert(
                "INSERT INTO estados (codigo, nombre, color, orden) VALUES (?, ?, ?, ?)",
                (e["codigo"], e["nombre"], e["color"], e["orden"])
            )


def seed_prioridades():
    for p in PRIORIDADES_SEMILLA:
        exists = execute_one("SELECT 1 FROM prioridades WHERE codigo = ?", (p["codigo"],))
        if not exists:
            execute_insert(
                "INSERT INTO prioridades (codigo, nombre, color, orden) VALUES (?, ?, ?, ?)",
                (p["codigo"], p["nombre"], p["color"], p["orden"])
            )


def seed_tipos_evidencia():
    for t in TIPOS_EVIDENCIA_SEMILLA:
        exists = execute_one("SELECT 1 FROM tipos_evidencia WHERE codigo = ?", (t["codigo"],))
        if not exists:
            execute_insert(
                "INSERT INTO tipos_evidencia (codigo, nombre, extensiones_permitidas, tamaño_max_mb) VALUES (?, ?, ?, ?)",
                (t["codigo"], t["nombre"], t["extensiones_permitidas"], t["tamaño_max_mb"])
            )


def seed_usuarios():
    for u in USUARIOS_SEMILLA:
        exists = execute_one("SELECT 1 FROM usuarios WHERE nombre = ?", (u["nombre"],))
        if not exists:
            execute_insert(
                "INSERT INTO usuarios (nombre, email) VALUES (?, ?)",
                (u["nombre"], u["email"])
            )


def seed_procesos_y_subtareas():
    """Crea plantillas de procesos con sus subtareas y dependencias."""
    conn = get_connection()
    
    for proc in PROCESOS_SEMILLA:
        # Verificar si ya existe
        exists = execute_one(
            "SELECT id FROM procesos_plantilla WHERE nombre = ?", (proc["nombre"],)
        )
        if exists:
            continue
        
        prioridad_id = get_prioridad_id(proc["prioridad_codigo"])
        
        with transaction() as tx:
            # Insertar proceso plantilla
            proceso_id = execute_insert(
                """INSERT INTO procesos_plantilla 
                   (nombre, descripcion, prioridad_id, dias_duracion_estimada, orden)
                   VALUES (?, ?, ?, ?, ?)""",
                (proc["nombre"], proc["descripcion"], prioridad_id,
                 proc["dias_duracion_estimada"], proc["orden"])
            )
            
            # Insertar subtareas
            for i, sub_nombre in enumerate(proc["subtareas"]):
                execute_insert(
                    """INSERT INTO subtareas_plantilla 
                       (proceso_plantilla_id, nombre, orden)
                       VALUES (?, ?, ?)""",
                    (proceso_id, sub_nombre, i + 1)
                )
            
            # Insertar dependencias (se resuelven después de crear todos los procesos)
            # Guardamos para segunda pasada
            proc["_plantilla_id"] = proceso_id
    
    # Segunda pasada: dependencias
    for proc in PROCESOS_SEMILLA:
        if "dependencias" in proc and proc["dependencias"]:
            proceso_id = proc.get("_plantilla_id")
            if not proceso_id:
                # Buscar el ID
                row = execute_one(
                    "SELECT id FROM procesos_plantilla WHERE nombre = ?", (proc["nombre"],)
                )
                if row:
                    proceso_id = row["id"]
            
            if proceso_id:
                for dep_nombre in proc["dependencias"]:
                    dep_row = execute_one(
                        "SELECT id FROM procesos_plantilla WHERE nombre = ?", (dep_nombre,)
                    )
                    if dep_row:
                        predecesora_id = dep_row["id"]
                        exists = execute_one(
                            "SELECT 1 FROM dependencias_plantilla WHERE proceso_plantilla_id = ? AND predecesora_id = ?",
                            (proceso_id, predecesora_id)
                        )
                        if not exists:
                            execute_insert(
                                "INSERT INTO dependencias_plantilla (proceso_plantilla_id, predecesora_id) VALUES (?, ?)",
                                (proceso_id, predecesora_id)
                            )


def seed_configuracion():
    for clave, valor in CONFIG_SEMILLA.items():
        exists = execute_one("SELECT 1 FROM configuracion WHERE clave = ?", (clave,))
        if not exists:
            execute_insert(
                "INSERT INTO configuracion (clave, valor) VALUES (?, ?)",
                (clave, valor)
            )


def crear_cierre_actual():
    """Crea el cierre del mes actual si no existe y genera sus procesos."""
    hoy = date.today()
    año, mes = hoy.year, hoy.month
    
    # Verificar si ya existe
    cierre = execute_one(
        "SELECT id FROM cierres WHERE año = ? AND mes = ?", (año, mes)
    )
    if cierre:
        return cierre["id"]
    
    # Crear cierre
    nombre_meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    nombre_cierre = f"Cierre {nombre_meses[mes-1]} {año}"
    
    with transaction() as tx:
        cierre_id = execute_insert(
            "INSERT INTO cierres (año, mes, nombre) VALUES (?, ?, ?)",
            (año, mes, nombre_cierre)
        )
        
        # Obtener estado "Pendiente"
        estado_pendiente_id = get_estado_id("pendiente")
        
        # Copiar plantillas a ejecución
        plantillas = execute_query(
            "SELECT * FROM procesos_plantilla WHERE activo = 1 ORDER BY orden"
        )
        
        proceso_map = {}  # plantilla_id -> proceso_id
        
        for pt in plantillas:
            # Calcular fechas planeadas (simplificado: secuencial desde hoy)
            proceso_id = execute_insert(
                """INSERT INTO procesos 
                   (cierre_id, proceso_plantilla_id, nombre, descripcion, 
                    prioridad_id, fecha_planeada, fecha_limite, estado_id, orden)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cierre_id, pt["id"], pt["nombre"], pt["descripcion"],
                 pt["prioridad_id"], None, None, estado_pendiente_id, pt["orden"])
            )
            proceso_map[pt["id"]] = proceso_id
            
            # Copiar subtareas
            subtareas = execute_query(
                "SELECT * FROM subtareas_plantilla WHERE proceso_plantilla_id = ? AND activo = 1 ORDER BY orden",
                (pt["id"],)
            )
            for st in subtareas:
                execute_insert(
                    """INSERT INTO subtareas 
                       (proceso_id, subtarea_plantilla_id, nombre, descripcion, orden)
                       VALUES (?, ?, ?, ?, ?)""",
                (proceso_id, st["id"], st["nombre"], st["descripcion"], st["orden"])
                )
        
        # Copiar dependencias
        for pt_id, proc_id in proceso_map.items():
            deps = execute_query(
                "SELECT predecesora_id FROM dependencias_plantilla WHERE proceso_plantilla_id = ?",
                (pt_id,)
            )
            for dep in deps:
                pred_plantilla_id = dep["predecesora_id"]
                if pred_plantilla_id in proceso_map:
                    execute_insert(
                        "INSERT INTO dependencias (proceso_id, predecesora_id) VALUES (?, ?)",
                        (proc_id, proceso_map[pred_plantilla_id])
                    )
        
        # Crear controles SOX básicos para el cierre
        controles_sox_base = [
            ("Parametrización", "Validación de parámetros de modelos actuariales"),
            ("Pantallazos", "Capturas de ejecución de procesos"),
            ("Conciliaciones", "Conciliación contable-actuarial"),
            ("Validaciones", "Validaciones de consistencia de datos"),
            ("Aprobaciones SOX", "Firmas y aprobaciones formales SOX"),
        ]
        for i, (nombre, desc) in enumerate(controles_sox_base):
            execute_insert(
                """INSERT INTO controles_sox 
                   (cierre_id, nombre, descripcion, estado_id, orden)
                   VALUES (?, ?, ?, ?, ?)""",
                (cierre_id, nombre, desc, estado_pendiente_id, i + 1)
            )
    
    return cierre_id


def init_db():
    """Inicializa la base de datos completa: esquema + semilla + cierre actual."""
    from src.database.schema import init_schema
    
    print("Inicializando base de datos...")
    init_schema()
    print("Esquema creado.")
    
    seed_estados()
    print("Estados cargados.")
    
    seed_prioridades()
    print("Prioridades cargadas.")
    
    seed_tipos_evidencia()
    print("Tipos de evidencia cargados.")
    
    seed_usuarios()
    print("Usuarios cargados.")
    
    seed_procesos_y_subtareas()
    print("Procesos y subtareas cargados.")
    
    seed_configuracion()
    print("Configuración cargada.")
    
    cierre_id = crear_cierre_actual()
    print(f"Cierre actual creado/verificado (ID: {cierre_id}).")
    
    print("Base de datos inicializada correctamente.")


if __name__ == "__main__":
    init_db()