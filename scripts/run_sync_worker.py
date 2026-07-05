"""
scripts/run_sync_worker.py — 同步 JOB 常駐 worker（WP2）

用途：本機/沙盒環境常駐執行 A→B 同步 JOB，也可作為正式環境排程器
（cron / systemd timer / Windows 工作排程器）呼叫 services_b.sync_service 的參考實作。

每一輪做兩件事：
  1. run_sync(db)：tag_mapping 驅動的 A→B 同步（見 services_b/sync_service.py）
  2. check_staleness(db)：斷訊看門狗（雙向：過期切 comm_ok=False、恢復新鮮切回 True）

輪詢間隔讀 system_config['sync_interval_minutes']（每輪重新讀取一次，允許不重啟 worker
就動態調整頻率）。收到 SIGINT（Ctrl+C）時優雅結束：一定會把目前這一輪的 run_sync +
check_staleness 跑完、DB 都 commit 完成才離開，不會在寫一半時被打斷。

用法：
  python scripts/run_sync_worker.py
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

# 讓腳本可以在 repo 根目錄外執行時仍然找得到 database_b/services_b（專案根目錄加入 sys.path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import BSessionLocal, create_all_b  # noqa: E402
from services_b.sync_service import check_staleness, get_sync_interval_minutes, run_sync  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_sync_worker")

# 模組層級旗標：SIGINT handler 與主迴圈都要看得到，故不放在 main() 區域變數裡。
_shutdown_requested = False


def _handle_sigint(signum, frame) -> None:
    global _shutdown_requested
    logger.info("收到中斷訊號（SIGINT），將在目前這一輪跑完後優雅結束（不會強制中斷）...")
    _shutdown_requested = True


def _run_one_cycle() -> int:
    """
    跑一輪 run_sync + check_staleness，回傳下一輪要等待的秒數
    （讀自 system_config['sync_interval_minutes']，預設 5 分鐘）。
    """
    db = BSessionLocal()
    try:
        now = datetime.now(timezone.utc)

        sync_result = run_sync(db, now=now)
        logger.info(
            "run_sync 完成：synced=%d skipped=%d stale=%d errors=%d",
            sync_result.synced, sync_result.skipped, sync_result.stale, len(sync_result.errors),
        )
        for err in sync_result.errors:
            logger.warning("  同步錯誤：%s", err)

        staleness_result = check_staleness(db, now=now)
        logger.info(
            "check_staleness 完成：本輪新標記斷訊=%d、本輪恢復正常=%d",
            staleness_result.stale, staleness_result.recovered,
        )

        interval_minutes = get_sync_interval_minutes(db)
    finally:
        db.close()
    return max(interval_minutes, 1) * 60


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    logger.info("同步 JOB worker 啟動（按 Ctrl+C 可優雅結束）")
    create_all_b()  # 冪等：確保 Schema B 表已存在，方便本機/沙盒環境直接執行不用先跑別的腳本

    while not _shutdown_requested:
        cycle_started = time.monotonic()
        try:
            wait_seconds = _run_one_cycle()
        except Exception:
            logger.exception("本輪同步發生未預期例外，將於下一輪重試")
            wait_seconds = 60  # 發生例外時用保守的固定間隔重試，避免設定錯誤造成緊密迴圈灌爆 log

        if _shutdown_requested:
            break

        elapsed = time.monotonic() - cycle_started
        logger.info("本輪耗時 %.1f 秒，等待 %d 秒後進入下一輪...", elapsed, wait_seconds)

        # 用 1 秒為單位輪詢 _shutdown_requested，讓 SIGINT 可以在等待期間也能即時反應，
        # 不必整整等完 wait_seconds 才發現該結束（同時仍保證目前這輪已經完整跑完並 commit）。
        slept = 0
        while slept < wait_seconds and not _shutdown_requested:
            time.sleep(min(1, wait_seconds - slept))
            slept += 1

    logger.info("同步 JOB worker 已優雅結束。")


if __name__ == "__main__":
    main()
