"""
scripts/run_dispatch_worker.py — 異常派報 JOB 常駐 worker（GetDataRed 對應）。

刻意與 scripts/run_sync_worker.py 分開成兩支獨立 worker（見 PM 決策）：
  - run_sync_worker：Kepware/A 端現值 → reading_current（讀值同步 + 斷訊看門狗）。
  - run_dispatch_worker（本檔）：讀 reading_current 判斷異常 → 寄派報信 + 寫 mail_log/mail_log_item。
兩者責任、失敗性質、排程週期都不同（對應舊系統本來就是兩支不同 JOB），分開跑才不會
一個出錯拖累另一個（派報要寄信、易受 SMTP 逾時影響，不該卡住讀值同步）。

每一輪呼叫 services_b.dispatch_service.run_dispatch_b(db)（隔離判定用預設 is_item_isolated）。
輪詢間隔讀 system_config['dispatch_interval_minutes']（預設 15，每輪重讀，允許不重啟調整）。
收到 SIGINT（Ctrl+C）時優雅結束：把當前這一輪跑完、commit 完才離開。

用法：
  python scripts/run_dispatch_worker.py
（通常與 run_sync_worker.py 一起常駐；正式環境用 cron/systemd/工作排程器各起一支。）
"""

import logging
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from database_b import BSessionLocal, create_all_b  # noqa: E402
from models_b import SystemConfig  # noqa: E402
from services_b.dispatch_service import run_dispatch_b  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_dispatch_worker")

_shutdown_requested = False


def _handle_sigint(signum, frame) -> None:
    global _shutdown_requested
    logger.info("收到中斷訊號（SIGINT），將在目前這一輪跑完後優雅結束（不會強制中斷）...")
    _shutdown_requested = True


def _get_dispatch_interval_minutes(db) -> int:
    """讀 system_config['dispatch_interval_minutes']（預設 15），讀不到或格式錯誤時回預設。"""
    row = db.execute(
        select(SystemConfig.value).where(SystemConfig.key == "dispatch_interval_minutes")
    ).scalar_one_or_none()
    try:
        return int(row) if row is not None else 15
    except (TypeError, ValueError):
        logger.warning("system_config[dispatch_interval_minutes]=%r 無法轉 int，改用預設 15", row)
        return 15


def _run_one_cycle() -> int:
    """跑一輪派報，回傳下一輪要等待的秒數。"""
    db = BSessionLocal()
    try:
        summary = run_dispatch_b(db)  # 隔離判定用預設 is_item_isolated
        logger.info("run_dispatch_b 完成：%s", summary)
        interval_minutes = _get_dispatch_interval_minutes(db)
    finally:
        db.close()
    return max(interval_minutes, 1) * 60


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    logger.info("派報 JOB worker 啟動（按 Ctrl+C 可優雅結束）")
    create_all_b()  # 冪等：確保 Schema B 表已存在

    while not _shutdown_requested:
        cycle_started = time.monotonic()
        try:
            wait_seconds = _run_one_cycle()
        except Exception:
            logger.exception("本輪派報發生未預期例外，將於下一輪重試")
            wait_seconds = 60

        if _shutdown_requested:
            break

        elapsed = time.monotonic() - cycle_started
        logger.info("本輪耗時 %.1f 秒，等待 %d 秒後進入下一輪...", elapsed, wait_seconds)

        slept = 0
        while slept < wait_seconds and not _shutdown_requested:
            time.sleep(min(1, wait_seconds - slept))
            slept += 1

    logger.info("派報 JOB worker 已優雅結束。")


if __name__ == "__main__":
    main()
