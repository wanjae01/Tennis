"""포지션/잔고 상태 관리. state.json 에 저장되어 재시작해도 유지된다."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import BASE_DIR, Config

log = logging.getLogger(__name__)
STATE_FILE = BASE_DIR / "state.json"
TRADES_FILE = BASE_DIR / "trades.log"


class Portfolio:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.balance_usdt = cfg.paper_balance
        self.positions: dict[str, dict] = {}   # symbol -> {amount, entry_price, entry_time}
        self.daily_pnl = 0.0
        self.daily_date = self._today()
        self._load()

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load(self):
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            # paper 잔고는 저장된 값 유지, live는 거래소가 진실이므로 포지션만 복원
            if self.cfg.mode == "paper":
                self.balance_usdt = data.get("balance_usdt", self.cfg.paper_balance)
            self.positions = data.get("positions", {})
            self.daily_pnl = data.get("daily_pnl", 0.0)
            self.daily_date = data.get("daily_date", self._today())
            log.info("상태 복원: 잔고 %.2f USDT, 포지션 %d개", self.balance_usdt, len(self.positions))

    def save(self):
        STATE_FILE.write_text(json.dumps({
            "balance_usdt": self.balance_usdt,
            "positions": self.positions,
            "daily_pnl": self.daily_pnl,
            "daily_date": self.daily_date,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def roll_daily(self):
        """날짜가 바뀌면 일일 손익 리셋."""
        today = self._today()
        if today != self.daily_date:
            log.info("날짜 변경: 일일 손익 리셋 (전일 %.2f USDT)", self.daily_pnl)
            self.daily_date = today
            self.daily_pnl = 0.0
            self.save()

    def open_position(self, symbol: str, amount: float, price: float):
        self.positions[symbol] = {
            "amount": amount,
            "entry_price": price,
            "entry_time": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def close_position(self, symbol: str) -> dict | None:
        pos = self.positions.pop(symbol, None)
        self.save()
        return pos

    def record_trade(self, line: str):
        with open(TRADES_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")
