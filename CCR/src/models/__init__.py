"""
Modelos de datos CCR - Dataclasses simples sin lógica de negocio.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
import json


@dataclass
class Usuario:
    id: int
    nombre: str
    email: Optional[str] = None
    activo: bool = True
    creado_en: Optional[datetime] = None


@dataclass
class Estado:
    id: int
    codigo: str
    nombre: str
    color: str
    orden: int
    activo: bool = True


@dataclass
class Prioridad:
    id: int
    codigo: str
    nombre: str
    color: str
    orden: int
    activo: bool = True


@dataclass
class TipoEvidencia:
    id: int
    codigo: str
    nombre: str
    extensiones_permitidas: list[str]
    tamaño_max_mb: int
    activo: bool = True
    
    @staticmethod
    def from_row(row) -> "TipoEvidencia":
        ext = json.loads(row["extensiones_permitidas"]) if row["extensiones_permitidas"] else []
        return TipoEvidencia(
            id=row["id"],
            codigo=row["codigo"],
            nombre=row["nombre"],
            extensiones_permitidas=ext,
            tamaño_max_mb=row["tamaño_max_mb"],
            activo=bool(row["activo"])
        )


@dataclass
class ProcesoPlantilla:
    id: int
    nombre: str
    descripcion: Optional[str]
    responsable_id: Optional[int]
    prioridad_id: Optional[int]
    dias_duracion_estimada: int
    orden: int
    activo: bool
    creado_en: Optional[datetime]


@dataclass
class SubtareaPlantilla:
    id: int
    proceso_plantilla_id: int
    nombre: str
    descripcion: Optional[str]
    orden: int
    activo: bool


@dataclass
class Cierre:
    id: int
    año: int
    mes: int
    nombre: str
    estado: str
    creado_en: Optional[datetime]
    cerrado_en: Optional[datetime]


@dataclass
class Proceso:
    id: int
    cierre_id: int
    proceso_plantilla_id: int
    nombre: str
    descripcion: Optional[str]
    responsable_id: Optional[int]
    prioridad_id: Optional[int]
    fecha_planeada: Optional[date]
    fecha_limite: Optional[date]
    estado_id: int
    observaciones: Optional[str]
    orden: int
    activo: bool
    creado_en: Optional[datetime]
    actualizado_en: Optional[datetime]


@dataclass
class Subtarea:
    id: int
    proceso_id: int
    subtarea_plantilla_id: Optional[int]
    nombre: str
    descripcion: Optional[str]
    orden: int
    completada: bool
    fecha_ejecucion: Optional[date]
    observaciones: Optional[str]
    activo: bool
    creado_en: Optional[datetime]
    actualizado_en: Optional[datetime]


@dataclass
class ProcesoMasivo:
    id: int
    codigo: str
    nombre: str
    fecha_ejecucion: date
    hora: Optional[str]
    ramo: Optional[str]
    estado_id: int
    observaciones: Optional[str]
    activo: bool
    creado_en: Optional[datetime]
    actualizado_en: Optional[datetime]


@dataclass
class ControlSOX:
    id: int
    cierre_id: int
    nombre: str
    descripcion: Optional[str]
    responsable_id: Optional[int]
    fecha_ejecucion: Optional[date]
    estado_id: int
    observaciones: Optional[str]
    activo: bool
    creado_en: Optional[datetime]
    actualizado_en: Optional[datetime]


@dataclass
class Bitacora:
    id: int
    fecha: datetime
    usuario: str
    proceso_id: Optional[int]
    subtarea_id: Optional[int]
    control_sox_id: Optional[int]
    aprobacion_id: Optional[int]
    comentario: str
    creado_en: Optional[datetime]


@dataclass
class Aprobacion:
    id: int
    cierre_id: int
    proceso_id: Optional[int]
    nombre: str
    estado_tecnico_id: int
    estado_aprobacion_id: int
    estado_sox_id: int
    responsable_id: Optional[int]
    fecha_envio: Optional[date]
    fecha_aprobacion: Optional[date]
    observaciones: Optional[str]
    activo: bool
    creado_en: Optional[datetime]
    actualizado_en: Optional[datetime]


@dataclass
class Evidencia:
    id: int
    tipo_evidencia_id: int
    entidad_tipo: str
    entidad_id: int
    nombre_archivo: str
    nombre_original: str
    ruta_relativa: str
    tamaño_bytes: int
    mime_type: Optional[str]
    es_enlace: bool
    enlace_url: Optional[str]
    descripcion: Optional[str]
    subido_por: str
    subido_en: datetime
    activo: bool


@dataclass
class Conocimiento:
    id: int
    proceso_plantilla_id: int
    tipo: str
    titulo: str
    url: str
    descripcion: Optional[str]
    activo: bool
    creado_en: Optional[datetime]


@dataclass
class Alerta:
    id: int
    tipo: str
    severidad: str
    titulo: str
    mensaje: str
    proceso_id: Optional[int]
    subtarea_id: Optional[int]
    control_sox_id: Optional[int]
    aprobacion_id: Optional[int]
    proceso_masivo_id: Optional[int]
    cierre_id: Optional[int]
    responsable_id: Optional[int]
    fecha_limite: Optional[date]
    leida: bool
    pospuesta_hasta: Optional[datetime]
    creado_en: datetime


@dataclass
class EventoSalida:
    id: int
    tipo_alerta: str
    severidad: str
    clave_unica: str
    payload_json: str
    canal: str
    estado: str
    intentos: int
    ultimo_error: Optional[str]
    creado_en: datetime
    enviado_en: Optional[datetime]


@dataclass
class Configuracion:
    clave: str
    valor: Optional[str]
    descripcion: Optional[str]
    actualizado_en: Optional[datetime]