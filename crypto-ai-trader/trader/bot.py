"""메인 트레이딩 루프: 시세 수집 → 퀀트 시그널 → AI 판단 → 리스크 체크 → 주문."""
import logging
import time

from .ai import AIAdvisor
from .config import Config
from .exchange import ExchangeClient
from .executor import Executor
from .notify import Notifier
from .portfolio import Portfolio
from .quant import compute_signal

log = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ex = ExchangeClient(cfg)
        self.pf = Portfolio(cfg)
        self.executor = Executor(cfg, self.ex, self.pf)
        self.ai = AIAdvisor(cfg) if cfg.ai_enabled else None
        self.notifier = Notifier(cfg)

    # ---------- 리스크 체크 ----------
    def _daily_limit_hit(self) -> bool:
        base = self.pf.balance_usdt if self.cfg.mode == "paper" else max(self.ex.fetch_usdt_balance(), 1.0)
        limit = -base * self.cfg.daily_loss_limit_pct
        if self.pf.daily_pnl <= limit:
            log.warning("일일 손실 한도 도달 (%.2f USDT) — 오늘 매매 중단", self.pf.daily_pnl)
            return True
        return False

    def _check_stops(self, symbol: str, price: float):
        """보유 포지션의 손절/익절을 확인한다."""
        pos = self.pf.positions.get(symbol)
        if not pos:
            return
        change = price / pos["entry_price"] - 1
        if change <= -self.cfg.stop_loss_pct:
            pnl = self.executor.sell(symbol, price, f"손절 ({change*100:.2f}%)")
            if pnl is not None:
                self.notifier.send(f"🔻 손절 {symbol} {pnl:+.2f} USDT")
        elif change >= self.cfg.take_profit_pct:
            pnl = self.executor.sell(symbol, price, f"익절 (+{change*100:.2f}%)")
            if pnl is not None:
                self.notifier.send(f"✅ 익절 {symbol} {pnl:+.2f} USDT")

    # ---------- 한 종목 처리 ----------
    def _process_symbol(self, symbol: str):
        ohlcv = self.ex.fetch_ohlcv(symbol, self.cfg.timeframe, limit=200)
        if len(ohlcv) < 60:
            log.warning("%s 캔들 데이터 부족 (%d개) — 건너뜀", symbol, len(ohlcv))
            return
        price = float(ohlcv.iloc[-1]["close"])

        # 1) 손절/익절 우선 확인
        self._check_stops(symbol, price)

        # 2) 퀀트 시그널
        signal = compute_signal(symbol, ohlcv, self.cfg.quant_weights, self.cfg.entry_threshold)
        log.info("%s 가격=%.4f 퀀트점수=%.3f → %s %s",
                 symbol, price, signal.score, signal.action, signal.components)

        position = self.pf.positions.get(symbol)

        # 3) AI 판단 (hold 시그널이고 포지션도 없으면 API 비용 절약을 위해 생략)
        if signal.action == "hold" and not position:
            return
        if self.ai:
            decision = self.ai.decide(signal, position)
            log.info("%s AI 판단: %s (확신 %d%%, 비중 x%.2f) — %s",
                     symbol, decision.decision, decision.confidence,
                     decision.size_multiplier, decision.reason)
            if decision.confidence < self.cfg.ai_min_confidence:
                log.info("%s AI 확신도 미달(%d%% < %d%%) — 보류",
                         symbol, decision.confidence, self.cfg.ai_min_confidence)
                return
            action, size_mult, reason = decision.decision, decision.size_multiplier, f"AI: {decision.reason}"
        else:
            action, size_mult, reason = signal.action, 1.0, f"퀀트 점수 {signal.score}"

        # 4) 실행
        if action == "buy" and not position:
            if len(self.pf.positions) >= self.cfg.max_positions:
                log.info("최대 포지션 수(%d) 도달 — 매수 보류", self.cfg.max_positions)
                return
            base = self.pf.balance_usdt if self.cfg.mode == "paper" else self.ex.fetch_usdt_balance()
            usdt = base * self.cfg.position_size_pct * size_mult
            if usdt < self.cfg.min_order_usdt:
                log.info("%s 주문 금액 %.2f USDT 가 최소 금액 미만 — 보류", symbol, usdt)
                return
            if self.executor.buy(symbol, usdt, price, reason):
                self.notifier.send(f"🟢 매수 {symbol} {usdt:.2f} USDT @ {price:.4f}\n{reason}")
        elif action == "sell" and position:
            pnl = self.executor.sell(symbol, price, reason)
            if pnl is not None:
                self.notifier.send(f"🔴 매도 {symbol} {pnl:+.2f} USDT @ {price:.4f}\n{reason}")

    # ---------- 메인 루프 ----------
    def run(self):
        mode_txt = "모의투자(paper)" if self.cfg.mode == "paper" else "⚠️ 실거래(live)"
        log.info("=== AI 자동매매 시작 [%s] 거래소=%s 종목=%s 주기=%ds ===",
                 mode_txt, self.cfg.exchange_id, self.cfg.symbols, self.cfg.interval_seconds)
        self.notifier.send(f"🤖 자동매매 시작 [{mode_txt}] {', '.join(self.cfg.symbols)}")

        while True:
            try:
                self.pf.roll_daily()
                if not self._daily_limit_hit():
                    for symbol in self.cfg.symbols:
                        self._process_symbol(symbol)
                total = self.pf.balance_usdt + sum(
                    p["amount"] * self.ex.fetch_price(s) for s, p in self.pf.positions.items()
                ) if self.cfg.mode == "paper" else None
                if total is not None:
                    log.info("포트폴리오 평가액: %.2f USDT (현금 %.2f, 일일손익 %+.2f)",
                             total, self.pf.balance_usdt, self.pf.daily_pnl)
            except KeyboardInterrupt:
                raise
            except Exception as e:  # noqa: BLE001
                log.exception("루프 오류 (다음 주기에 재시도): %s", e)
            time.sleep(self.cfg.interval_seconds)
