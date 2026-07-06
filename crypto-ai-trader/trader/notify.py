"""텔레그램 알림 (선택 기능)."""
import logging

import requests

from .config import Config

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, cfg: Config):
        self.enabled = cfg.telegram_enabled and cfg.telegram_token and cfg.telegram_chat_id
        self.token = cfg.telegram_token
        self.chat_id = cfg.telegram_chat_id

    def send(self, text: str):
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("텔레그램 알림 실패: %s", e)
