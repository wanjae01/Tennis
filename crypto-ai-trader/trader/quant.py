"""퀀트 트레이더 시그널 엔진.

전문 퀀트 트레이더가 쓰는 대표 전략 4가지를 앙상블로 결합해
-1(강한 매도) ~ +1(강한 매수) 사이의 종합 점수를 만든다.
AI 어드바이저는 이 점수를 '추종'할지 판단한다.
"""
from dataclasses import dataclass, field

import pandas as pd

from .indicators import enrich


@dataclass
class QuantSignal:
    symbol: str
    score: float                 # -1 ~ +1 종합 점수
    action: str                  # buy | sell | hold
    components: dict = field(default_factory=dict)
    snapshot: dict = field(default_factory=dict)  # AI에게 넘길 시장 요약


def _trend_signal(row) -> float:
    """추세추종: 단기 EMA가 장기 EMA/SMA 위에 있으면 상승 추세."""
    s = 0.0
    if row.ema_fast > row.ema_slow:
        s += 0.5
    else:
        s -= 0.5
    if row.close > row.sma_50:
        s += 0.5
    else:
        s -= 0.5
    return s


def _momentum_signal(row) -> float:
    """모멘텀: RSI 구간 + MACD 히스토그램 방향."""
    s = 0.0
    if row.rsi < 30:
        s += 0.5   # 과매도 → 반등 기대
    elif row.rsi > 70:
        s -= 0.5   # 과매수 → 조정 경계
    elif row.rsi > 50:
        s += 0.2
    else:
        s -= 0.2
    if row.macd_hist > 0:
        s += 0.5
    else:
        s -= 0.5
    return max(-1.0, min(1.0, s))


def _mean_reversion_signal(row) -> float:
    """평균회귀: 볼린저밴드 하단 근접 시 매수, 상단 근접 시 매도."""
    band = row.bb_upper - row.bb_lower
    if band <= 0 or pd.isna(band):
        return 0.0
    # 밴드 내 위치: 0(하단) ~ 1(상단)
    pos = (row.close - row.bb_lower) / band
    return max(-1.0, min(1.0, (0.5 - pos) * 2))


def _volume_signal(df: pd.DataFrame) -> float:
    """거래량 확인: 평균 대비 거래량이 실리면 최근 가격 방향에 가중치."""
    row = df.iloc[-1]
    if pd.isna(row.vol_sma) or row.vol_sma <= 0:
        return 0.0
    ratio = row.volume / row.vol_sma
    direction = 1.0 if row.close >= df.iloc[-2].close else -1.0
    if ratio > 1.5:
        return direction * 0.8
    if ratio > 1.0:
        return direction * 0.4
    return 0.0


def compute_signal(symbol: str, ohlcv: pd.DataFrame, weights: dict, entry_threshold: float) -> QuantSignal:
    df = enrich(ohlcv)
    row = df.iloc[-1]

    components = {
        "trend": _trend_signal(row),
        "momentum": _momentum_signal(row),
        "mean_reversion": _mean_reversion_signal(row),
        "volume": _volume_signal(df),
    }

    w = {k: float(weights.get(k, 0.25)) for k in components}
    total_w = sum(w.values()) or 1.0
    score = sum(components[k] * w[k] for k in components) / total_w

    if score >= entry_threshold:
        action = "buy"
    elif score <= -entry_threshold:
        action = "sell"
    else:
        action = "hold"

    change_24h = (row.close / df.iloc[-25].close - 1) * 100 if len(df) > 25 else 0.0
    snapshot = {
        "price": round(float(row.close), 4),
        "change_24h_pct": round(float(change_24h), 2),
        "rsi": round(float(row.rsi), 1),
        "macd_hist": round(float(row.macd_hist), 4),
        "ema_fast_vs_slow": "golden" if row.ema_fast > row.ema_slow else "dead",
        "bb_position": round(float((row.close - row.bb_lower) / max(row.bb_upper - row.bb_lower, 1e-10)), 2),
        "volume_ratio": round(float(row.volume / max(row.vol_sma, 1e-10)), 2),
        "atr_pct": round(float(row.atr / row.close * 100), 2),
    }

    return QuantSignal(symbol=symbol, score=round(score, 3), action=action,
                       components=components, snapshot=snapshot)
