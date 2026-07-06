"""ccxt 기반 거래소 연동. 시세 조회는 항상 실서버, 주문은 mode/testnet 설정을 따른다."""
import logging

import ccxt
import pandas as pd

from .config import Config

log = logging.getLogger(__name__)


class ExchangeClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        klass = getattr(ccxt, cfg.exchange_id)

        # 시세 전용 클라이언트 (키 불필요, 항상 실서버 데이터)
        self.public = klass({"enableRateLimit": True})

        # 주문/잔고용 클라이언트
        params = {
            "apiKey": cfg.api_key,
            "secret": cfg.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
        if cfg.api_password:
            params["password"] = cfg.api_password
        self.private = klass(params)

        if cfg.testnet:
            try:
                self.private.set_sandbox_mode(True)
                log.info("거래소 테스트넷(sandbox) 모드 활성화")
            except Exception as e:  # noqa: BLE001
                log.warning("이 거래소는 테스트넷을 지원하지 않습니다: %s", e)

    # ---------- 시세 ----------
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        rows = self.public.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        return df

    def fetch_price(self, symbol: str) -> float:
        return float(self.public.fetch_ticker(symbol)["last"])

    # ---------- 계좌/주문 (live 모드에서만 사용) ----------
    def fetch_usdt_balance(self) -> float:
        bal = self.private.fetch_balance()
        return float(bal.get("USDT", {}).get("free", 0.0))

    def market_buy(self, symbol: str, amount: float) -> dict:
        log.info("[LIVE] 시장가 매수 %s 수량 %.8f", symbol, amount)
        return self.private.create_order(symbol, "market", "buy", amount)

    def market_sell(self, symbol: str, amount: float) -> dict:
        log.info("[LIVE] 시장가 매도 %s 수량 %.8f", symbol, amount)
        return self.private.create_order(symbol, "market", "sell", amount)

    def amount_to_precision(self, symbol: str, amount: float) -> float:
        try:
            self.private.load_markets()
            return float(self.private.amount_to_precision(symbol, amount))
        except Exception:  # noqa: BLE001
            return round(amount, 6)
