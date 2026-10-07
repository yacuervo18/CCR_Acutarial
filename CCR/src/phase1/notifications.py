"""Canales simulados y servicio de notificaciones."""
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from .repository import Repository

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notification:
    proceso: str
    periodo: str
    tipo_evento: str
    mensaje: str
    destinatarios: tuple[str, ...]
    canal: str
    fecha_programada: str
    enlace_app: str = ""


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, notification: Notification) -> None:
        raise NotImplementedError


class PowerAutomateChannel(NotificationChannel):
    def send(self, notification: Notification) -> None:
        log.info("Webhook Power Automate simulado: %s", notification)


class EmailChannel(NotificationChannel):
    def send(self, notification: Notification) -> None:
        log.info("Correo simulado: %s", notification)


def validar_destinatarios(value: str) -> tuple[str, ...]:
    emails = tuple(x.strip() for x in value.split(",") if x.strip())
    if not emails or any(not EMAIL_RE.match(email) for email in emails):
        raise ValueError("Use correos válidos separados por coma.")
    return emails


def parse_destinatarios(value: str) -> list[dict[str, str]]:
    """Convierte líneas ``nombre | correo`` en destinos persistibles."""
    recipients = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|", 1)]
        label = parts[0]
        address = parts[1] if len(parts) == 2 else label
        if "@" in address and not EMAIL_RE.match(address):
            raise ValueError(f"Correo inválido: {address}")
        recipients.append({"label": label, "value": address})
    if not recipients:
        raise ValueError("Agregue al menos un destinatario.")
    return recipients


class NotificationService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.channels = {"Teams": PowerAutomateChannel(), "Correo": EmailChannel()}

    def schedule(self, notification: Notification) -> None:
        for channel in notification.canal.split(","):
            channel = channel.strip()
            if channel not in self.channels:
                raise ValueError(f"Canal no soportado: {channel}")
            self.channels[channel].send(notification)
        self.repository.add_notification(notification.periodo, notification.proceso, json.dumps(notification.__dict__, ensure_ascii=False))

    def send_daily_reminder(self, notification: Notification) -> None:
        """Registra el recordatorio y lo deja listo para conectar con Teams."""
        self.channels["Teams"].send(notification)
        self.repository.add_notification(notification.periodo, notification.proceso, json.dumps(notification.__dict__, ensure_ascii=False))
