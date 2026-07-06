"""주문 실행: paper 모드는 내부 장부로, live 모드는 거래소에 실제 주문."""
import logging

from .config import Config
from .exchange import ExchangeClient
from .portfolio import Portfolio

log = logging.getLogger(__name__)
FEE_RATE = 0.001  # paper 모드 수수료 가정 0.1%


class Executor:
    def __init__(self, cfg: Config, exchange: ExchangeClient, portfolio: Portfolio):
        self.cfg = cfg
        self.ex = exchange
        self.pf = portfolio

    def buy(self, symbol: str, usdt_amount: float, price: float, reason: str) -> bool:
        amount = usdt_amount / price
        if self.cfg.mode == "live":
            amount = self.ex.amount_to_precision(symbol, amount)
            try:
                self.ex.market_buy(symbol, amount)
            except Exception as e:  # noqa: BLE001
                log.error("매수 주문 실패 %s: %s", symbol, e)
                return False
        else:
            cost = usdt_amount * (1 + FEE_RATE)
            if cost > self.pf.balance_usdt:
                log.warning("잔고 부족으로 매수 불가 %s (필요 %.2f, 보유 %.2f)", symbol, cost, self.pf.balance_usdt)
                return False
            self.pf.balance_usdt -= cost

        self.pf.open_position(symbol, amount, price)
        msg = f"BUY {symbol} 수량={amount:.8f} 가격={price:.4f} 금액={usdt_amount:.2f}USDT | {reason}"
        log.info("[%s] %s", self.cfg.mode.upper(), msg)
        self.pf.record_trade(f"[{self.cfg.mode}] {msg}")
        return True

    def sell(self, symbol: str, price: float, reason: str) -> float | None:
        """포지션 전량 매도. 실현 손익(USDT)을 반환."""
        pos = self.pf.positions.get(symbol)
        if not pos:
            return None
        amount = pos["amount"]

        if self.cfg.mode == "live":
            try:
                self.ex.market_sell(symbol, amount)
            except Exception as e:  # noqa: BLE001
                log.error("매도 주문 실패 %s: %s", symbol, e)
                return None

        proceeds = amount * price * (1 - FEE_RATE)
        cost = amount * pos["entry_price"] * (1 + FEE_RATE)
        pnl = proceeds - cost
        if self.cfg.mode == "paper":
            self.pf.balance_usdt += proceeds

        self.pf.close_position(symbol)
        self.pf.daily_pnl += pnl
        self.pf.save()
        pnl_pct = (price / pos["entry_price"] - 1) * 100
        msg = (f"SELL {symbol} 수량={amount:.8f} 가격={price:.4f} "
               f"손익={pnl:+.2f}USDT ({pnl_pct:+.2f}%) | {reason}")
        log.info("[%s] %s", self.cfg.mode.upper(), msg)
        self.pf.record_trade(f"[{self.cfg.mode}] {msg}")
        return pnl
