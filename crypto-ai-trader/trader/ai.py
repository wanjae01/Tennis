"""AI 어드바이저: Claude가 퀀트 시그널을 검토하고 최종 매매 결정을 내린다.

퀀트 트레이더(시그널 엔진)의 판단을 기본으로 추종하되,
시장 상황상 위험하다고 판단되면 거부(veto)하거나 비중을 줄인다.
"""
import json
import logging
from dataclasses import dataclass

import anthropic

from .config import Config
from .quant import QuantSignal

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 암호화폐 퀀트 트레이딩 팀의 리스크 총괄 AI입니다.
퀀트 트레이더의 시그널(추세추종, 모멘텀, 평균회귀, 거래량 앙상블)을 받아
그 판단을 추종할지 최종 결정합니다.

원칙:
1. 퀀트 시그널을 기본적으로 존중하되, 시그널 간 모순이 크거나 변동성(ATR)이 과도하면 보수적으로 판단
2. 확신이 없으면 hold — 잃지 않는 것이 우선
3. size_multiplier로 비중 조절 가능 (0.5 = 절반만 진입, 1.0 = 제안대로)

반드시 아래 JSON 형식으로만 응답:
{"decision": "buy" | "sell" | "hold", "confidence": 0-100, "size_multiplier": 0.0-1.0, "reason": "한 문장 근거"}"""


@dataclass
class AIDecision:
    decision: str
    confidence: int
    size_multiplier: float
    reason: str


def _fallback(signal: QuantSignal, reason: str) -> AIDecision:
    """AI 호출 실패 시 퀀트 시그널을 그대로 따르되 보수적 비중 적용."""
    return AIDecision(decision=signal.action, confidence=50, size_multiplier=0.5,
                      reason=f"AI 응답 실패로 퀀트 시그널 추종({reason})")


class AIAdvisor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    def decide(self, signal: QuantSignal, position: dict | None) -> AIDecision:
        user_msg = {
            "symbol": signal.symbol,
            "quant_signal": {
                "action": signal.action,
                "score": signal.score,
                "components": signal.components,
            },
            "market": signal.snapshot,
            "current_position": position or "없음",
        }
        try:
            resp = self.client.messages.create(
                model=self.cfg.ai_model,
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(user_msg, ensure_ascii=False)}],
            )
            text = resp.content[0].text.strip()
            # 모델이 코드블록으로 감쌀 경우 대비
            if text.startswith("```"):
                text = text.strip("`").lstrip("json").strip()
            data = json.loads(text)
            return AIDecision(
                decision=str(data.get("decision", "hold")),
                confidence=int(data.get("confidence", 0)),
                size_multiplier=max(0.0, min(1.0, float(data.get("size_multiplier", 1.0)))),
                reason=str(data.get("reason", "")),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("AI 어드바이저 호출 실패 (%s): %s", signal.symbol, e)
            return _fallback(signal, str(e)[:80])
