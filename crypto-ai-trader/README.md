# 🤖 Crypto AI Trader — 개인용 AI 코인 자동매매 봇

해외 거래소(Binance, Bybit, OKX 등)에 내 계좌를 연동하고,
**퀀트 트레이더 시그널 엔진**의 판단을 **Claude AI**가 검토·추종하며 자동으로 매매하는 개인용 프로그램입니다.

## 동작 원리

```
시세 수집 (ccxt)
   ↓
퀀트 시그널 엔진 ─ 추세추종 + 모멘텀 + 평균회귀 + 거래량 앙상블 → 종합점수 (-1 ~ +1)
   ↓
AI 어드바이저 (Claude) ─ 퀀트 판단을 추종할지 결정 (매수/매도/보류 + 확신도 + 비중)
   ↓
리스크 관리 ─ 포지션 크기 제한, 손절/익절, 일일 손실 한도
   ↓
주문 실행 ─ paper(모의) 또는 live(실거래)
```

- **퀀트 시그널 엔진**이 전문 퀀트 트레이더 역할을 합니다: EMA 골든/데드크로스 추세추종, RSI+MACD 모멘텀, 볼린저밴드 평균회귀, 거래량 확인 — 4가지 전략을 가중 앙상블로 결합합니다.
- **AI(Claude)** 는 리스크 총괄 역할로, 퀀트 시그널을 기본 추종하되 시그널 간 모순이나 과도한 변동성이 보이면 거부하거나 비중을 줄입니다. 확신도가 기준 미달이면 거래하지 않습니다.

## 설치

```bash
cd crypto-ai-trader
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # 열어서 API 키 입력
```

### API 키 준비
1. **거래소 API 키** — 거래소 계정에서 발급. **반드시 "현물 거래" 권한만 부여하고 "출금" 권한은 끄세요.** 가능하면 IP 화이트리스트도 설정하세요.
2. **Claude API 키** — https://console.anthropic.com 에서 발급.

## 사용법

```bash
# 1) 백테스트로 전략 성과부터 확인 (API 키 불필요)
python backtest.py --symbol BTC/USDT --timeframe 1h --limit 1000

# 2) 모의투자로 검증 (기본 설정: paper 모드 + 테스트넷)
python main.py --once     # 한 사이클만 실행해서 동작 확인
python main.py            # 계속 실행

# 3) 충분히 검증한 후에만 실거래
#    config.yaml 에서 mode: live, testnet: false 로 변경 → 실행 시 YES 확인 필요
```

## 설정 (config.yaml)

| 항목 | 설명 |
|---|---|
| `exchange.id` | 거래소 (binance, bybit, okx, bitget 등 ccxt 지원 거래소) |
| `trading.mode` | `paper`(모의투자) / `live`(실거래) |
| `trading.symbols` | 감시 종목 목록 |
| `quant.weights` | 전략별 가중치 조절 |
| `ai.min_confidence` | AI 확신도 하한 (미달 시 거래 안 함) |
| `risk.*` | 포지션 크기, 손절/익절, 일일 손실 한도 |
| `notify.telegram` | 텔레그램 매매 알림 |

## 생성되는 파일

- `state.json` — 잔고/포지션 상태 (재시작해도 유지)
- `trades.log` — 전체 매매 기록
- `bot.log` — 실행 로그

## ⚠️ 주의사항

- 암호화폐 투자는 원금 손실 위험이 큽니다. 이 프로그램은 수익을 보장하지 않으며, 모든 투자 결정과 손실의 책임은 본인에게 있습니다.
- **반드시 paper 모드와 백테스트로 충분히 검증한 후** 소액으로 실거래를 시작하세요.
- 거래소 API 키에 출금 권한을 절대 부여하지 마세요.
- `.env` 파일은 절대 커밋하거나 공유하지 마세요 (.gitignore에 포함되어 있음).
