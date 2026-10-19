"""Verified HTTPS transport using the operating system's trusted CA store."""

import ssl

import requests
from requests.adapters import HTTPAdapter


class SystemTrustStoreAdapter(HTTPAdapter):
    """Keeps certificate verification enabled with the system CA certificates."""

    def __init__(self, *args, **kwargs) -> None:
        self._ssl_context = ssl.create_default_context()
        super().__init__(*args, **kwargs)

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs,
    ) -> None:
        pool_kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            **pool_kwargs,
        )


def session_with_system_trust() -> requests.Session:
    session = requests.Session()
    session.mount("https://", SystemTrustStoreAdapter())
    return session
