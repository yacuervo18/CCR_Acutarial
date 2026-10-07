"""Canales simulados y servicio de notificaciones."""
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
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
