"""설정 로더: config.yaml + .env 를 합쳐서 하나의 설정 객체로 만든다."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    raw: dict = field(default_factory=dict)

    # exchange
    exchange_id: str = "binance"
    testnet: bool = True
    api_key: str = ""
    api_secret: str = ""
    api_password: str = ""

    # trading
    mode: str = "paper"
    symbols: list = field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = "1h"
    interval_seconds: int = 300
    paper_balance: float = 10000.0

    # quant
    quant_weights: dict = field(default_factory=dict)
    entry_threshold: float = 0.35

    # ai
    ai_enabled: bool = True
    ai_model: str = "claude-sonnet-5"
    ai_min_confidence: int = 60
    anthropic_api_key: str = ""

    # risk
    position_size_pct: float = 0.10
    max_positions: int = 3
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    daily_loss_limit_pct: float = 0.05
    min_order_usdt: float = 10.0

    # notify
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""


def load_config(path: str | None = None, require_keys: bool = True) -> Config:
    load_dotenv(BASE_DIR / ".env")

    cfg_path = Path(path) if path else BASE_DIR / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    ex = raw.get("exchange", {})
    tr = raw.get("trading", {})
    qt = raw.get("quant", {})
    ai = raw.get("ai", {})
    rk = raw.get("risk", {})
    nt = raw.get("notify", {})

    cfg = Config(
        raw=raw,
        exchange_id=ex.get("id", "binance"),
        testnet=bool(ex.get("testnet", True)),
        api_key=os.getenv("EXCHANGE_API_KEY", ""),
        api_secret=os.getenv("EXCHANGE_API_SECRET", ""),
        api_password=os.getenv("EXCHANGE_API_PASSWORD", ""),
        mode=tr.get("mode", "paper"),
        symbols=tr.get("symbols", ["BTC/USDT"]),
        timeframe=tr.get("timeframe", "1h"),
        interval_seconds=int(tr.get("interval_seconds", 300)),
        paper_balance=float(tr.get("paper_balance", 10000)),
        quant_weights=qt.get("weights", {}),
        entry_threshold=float(qt.get("entry_threshold", 0.35)),
        ai_enabled=bool(ai.get("enabled", True)),
        ai_model=ai.get("model", "claude-sonnet-5"),
        ai_min_confidence=int(ai.get("min_confidence", 60)),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        position_size_pct=float(rk.get("position_size_pct", 0.10)),
        max_positions=int(rk.get("max_positions", 3)),
        stop_loss_pct=float(rk.get("stop_loss_pct", 0.03)),
        take_profit_pct=float(rk.get("take_profit_pct", 0.06)),
        daily_loss_limit_pct=float(rk.get("daily_loss_limit_pct", 0.05)),
        min_order_usdt=float(rk.get("min_order_usdt", 10)),
        telegram_enabled=bool(nt.get("telegram", False)),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
    )

    if cfg.mode not in ("paper", "live"):
        raise ValueError(f"trading.mode 는 paper 또는 live 여야 합니다: {cfg.mode}")
    if require_keys:
        if cfg.mode == "live" and not (cfg.api_key and cfg.api_secret):
            raise ValueError("live 모드에는 .env 에 EXCHANGE_API_KEY / EXCHANGE_API_SECRET 이 필요합니다.")
        if cfg.ai_enabled and not cfg.anthropic_api_key:
            raise ValueError("AI 어드바이저를 쓰려면 .env 에 ANTHROPIC_API_KEY 가 필요합니다. (ai.enabled: false 로 끌 수 있음)")

    return cfg
