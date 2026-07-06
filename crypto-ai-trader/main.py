"""AI 코인 자동매매 실행 진입점.

사용법:
    python main.py                 # config.yaml 설정으로 봇 실행
    python main.py --config my.yaml
    python main.py --once          # 한 사이클만 실행하고 종료 (동작 확인용)
"""
import argparse
import logging
import sys

from trader.bot import TradingBot
from trader.config import load_config


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="AI 코인 자동매매 봇")
    parser.add_argument("--config", default=None, help="설정 파일 경로 (기본: config.yaml)")
    parser.add_argument("--once", action="store_true", help="한 사이클만 실행하고 종료")
    args = parser.parse_args()

    setup_logging()
    cfg = load_config(args.config)

    if cfg.mode == "live" and not cfg.testnet:
        print("\n" + "=" * 60)
        print("⚠️  실거래(live) + 실서버 모드입니다. 실제 자산으로 매매합니다!")
        print("=" * 60)
        answer = input("계속하려면 'YES'를 입력하세요: ")
        if answer.strip() != "YES":
            print("중단합니다.")
            return

    bot = TradingBot(cfg)
    if args.once:
        bot.pf.roll_daily()
        for symbol in cfg.symbols:
            bot._process_symbol(symbol)
        print("1사이클 완료. state.json / trades.log 를 확인하세요.")
        return

    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n사용자 종료. 상태는 state.json 에 저장되어 있습니다.")


if __name__ == "__main__":
    main()
