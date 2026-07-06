"""간단 백테스터: 과거 캔들로 퀀트 시그널 전략의 성과를 검증한다.

사용법:
    python backtest.py                          # BTC/USDT 1h 최근 1000캔들
    python backtest.py --symbol ETH/USDT --timeframe 4h --limit 1500

주의: AI 어드바이저 없이 퀀트 시그널만으로 시뮬레이션한다
(과거 시점마다 AI를 호출하면 비용이 크고 미래정보 통제가 어렵기 때문).
"""
import argparse

import ccxt
import pandas as pd

from trader.config import load_config
from trader.quant import compute_signal

FEE_RATE = 0.001


def fetch_history(exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    rows = []
    since = None
    while len(rows) < limit:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=min(1000, limit - len(rows)))
        if not batch:
            break
        if since is None:
            # 최신부터 거꾸로 당길 수 없으므로 필요한 만큼 과거 시점부터 시작
            ms_per = ex.parse_timeframe(timeframe) * 1000
            since = batch[-1][0] - ms_per * limit
            rows = []
            continue
        rows.extend(batch)
        since = batch[-1][0] + 1
        if len(batch) < 2:
            break
    df = pd.DataFrame(rows[-limit:], columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def run_backtest(cfg, df: pd.DataFrame, symbol: str, start_balance: float = 10000.0):
    balance = start_balance
    position = None  # {amount, entry_price}
    trades = []
    warmup = 60

    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        price = float(window.iloc[-1]["close"])

        # 손절/익절
        if position:
            change = price / position["entry_price"] - 1
            if change <= -cfg.stop_loss_pct or change >= cfg.take_profit_pct:
                balance += position["amount"] * price * (1 - FEE_RATE)
                trades.append(change)
                position = None
                continue

        sig = compute_signal(symbol, window, cfg.quant_weights, cfg.entry_threshold)
        if sig.action == "buy" and not position:
            usdt = balance * cfg.position_size_pct
            amount = usdt / price
            balance -= usdt * (1 + FEE_RATE)
            position = {"amount": amount, "entry_price": price}
        elif sig.action == "sell" and position:
            change = price / position["entry_price"] - 1
            balance += position["amount"] * price * (1 - FEE_RATE)
            trades.append(change)
            position = None

    # 마지막 포지션 청산 평가
    if position:
        final_price = float(df.iloc[-1]["close"])
        balance += position["amount"] * final_price * (1 - FEE_RATE)
        trades.append(final_price / position["entry_price"] - 1)

    total_return = (balance / start_balance - 1) * 100
    buy_hold = (df.iloc[-1]["close"] / df.iloc[warmup]["close"] - 1) * 100
    wins = sum(1 for t in trades if t > 0)

    print(f"\n===== 백테스트 결과: {symbol} =====")
    print(f"기간        : {df.iloc[warmup]['ts']} ~ {df.iloc[-1]['ts']}")
    print(f"총 거래     : {len(trades)}회 (승률 {wins/len(trades)*100:.1f}%)" if trades else "총 거래     : 0회")
    print(f"전략 수익률 : {total_return:+.2f}%")
    print(f"단순 보유   : {buy_hold:+.2f}%")
    print(f"최종 잔고   : {balance:,.2f} USDT (시작 {start_balance:,.0f})")


def main():
    parser = argparse.ArgumentParser(description="퀀트 전략 백테스터")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config, require_keys=False)
    print(f"{args.symbol} {args.timeframe} 캔들 {args.limit}개 다운로드 중...")
    df = fetch_history(cfg.exchange_id, args.symbol, args.timeframe, args.limit)
    print(f"{len(df)}개 캔들 확보")
    run_backtest(cfg, df, args.symbol)


if __name__ == "__main__":
    main()
