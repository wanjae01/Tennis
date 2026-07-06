"""기술적 지표 계산 (pandas만 사용, 외부 TA 라이브러리 불필요)."""
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(close: pd.Series, period: int = 20, std_mult: float = 2.0):
    mid = sma(close, period)
    std = close.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV 데이터프레임에 모든 지표 컬럼을 추가한다."""
    out = df.copy()
    close = out["close"]
    out["ema_fast"] = ema(close, 12)
    out["ema_slow"] = ema(close, 26)
    out["sma_50"] = sma(close, 50)
    out["rsi"] = rsi(close)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(close)
    out["bb_upper"], out["bb_mid"], out["bb_lower"] = bollinger(close)
    out["atr"] = atr(out)
    out["vol_sma"] = sma(out["volume"], 20)
    return out
