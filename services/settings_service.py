from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal

from db.repositories import SettingsRepository
from models import AppSettings


class SettingsService:
    def __init__(self, repository: SettingsRepository) -> None:
        self.repository = repository

    def load(self) -> AppSettings:
        raw = self.repository.get_all()
        settings = AppSettings()
        for key, value in raw.items():
            if not hasattr(settings, key):
                continue
            current = getattr(settings, key)
            if isinstance(current, bool):
                setattr(settings, key, value == "1")
            elif isinstance(current, Decimal):
                setattr(settings, key, Decimal(value))
            else:
                setattr(settings, key, value)
        return settings

    def save(self, settings: AppSettings) -> None:
        payload: dict[str, str] = {}
        for key, value in asdict(settings).items():
            if isinstance(value, bool):
                payload[key] = "1" if value else "0"
            else:
                payload[key] = str(value)
        self.repository.set_many(payload)
