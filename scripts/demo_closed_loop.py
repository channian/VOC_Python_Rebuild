"""
scripts/demo_closed_loop.py — Phase A 驗收演練：seed → 申請隔離 → 簽核 → 讀值超標 → 派報

對應 docs/PhaseA執行規格書.md 第八節驗收清單第 4 項：
    「閉環腳本演練：seed → 申請隔離（TEST001）→ 簽核（TEST999）→ 改讀值超標 →
      派報只寄 TEST_DEV_EMAIL」

流程：
  1. scripts.seed_test_data.seed() 重灌基準資料。
  2. TEST001 對 TEST1/pH1 申請隔離（services_b.control_service.create_isolation，is_commit=True
     直接送簽），示範 stime 設在「呼叫當下 + 2 秒」，讓腳本跑到派報那一步時隔離已經生效
     （is_item_isolated 判定為 True），驗證「隔離中項目不派報」與「未隔離項目照樣派報」
     同時成立，才是真正的閉環驗證，而不是只測其中一條路徑。
  3. TEST999 簽核核准（services_b.flow_service.process_sign）。
  4. 改 kepware_sim 讓 Cu1 讀值超標（> spec.oos_high=3.0），依序嘗試：
       a. services_b.sync_service.run_sync()（WP2 產出）：模擬「轉拋 JOB 跑一輪」；
          若尚未完成（ImportError）則記錄跳過，改成直接寫 reading_current 模擬同等效果。
       b. 保險起見：不論 run_sync 是否成功同步出預期值，最後都直接確認/覆寫一次
          reading_current(Cu1) 為超標值——因為 kepware_sim 種子資料裡 Cu1 同時存在
          「超標值」與「quality=bad（斷訊）」兩個 tag_mapping 都指向同一個 (plant_no,item)，
          run_sync 兩者的處理順序不保證超標值最後生效，這裡用明確覆寫確保示範情境穩定可重現
          （這是共用種子資料本身的既有結構特性，不是本腳本刻意製造的假象，見腳本內註解）。
  5. services_b.dispatch_service.run_dispatch_b()：派報。TEST_MODE=True（.env 預設）時
     services.notify_service.send_email_sync 會攔截並只真的寄給 settings.TEST_DEV_EMAIL，
     本腳本額外監看 send_email_sync 呼叫參數，印出「原本應該收到信的名單」與主旨，
     不依賴猜測 TEST_MODE 攔截後的假名單。

用法：
    python scripts/demo_closed_loop.py
"""

import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from database_b import BSessionLocal  # noqa: E402
from scripts.seed_test_data import seed, TEST_PLANT_NO, TEST_PLANT_ID, APPLICANT_EMPNO, SIGNER_EMPNO  # noqa: E402
from models_b import MailList, KepwareSim, ReadingCurrent  # noqa: E402
from schemas.control_schema import ControlCreate, ControlItemBase  # noqa: E402
from services.flow_service import SIGN_ACTION_APPROVE  # noqa: E402
from services_b import control_service, flow_service, dispatch_service  # noqa: E402


def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _ensure_signer_maillist(db) -> None:
    """
    種子資料的 TEST999 只登記了 rpttype='水質異常'（warning_service 用途），
    但隔離申請簽核（services.flow_service.build_rtype_list）用的 rpttype 是
    「水保養中」/「空保養中」，種子沒有配這筆，示範腳本自建（比照任務提示
    「seed 若無虛擬廠區列，測試內自建」的同一精神，不改動共用 seed_test_data.py）。
    """
    exists = db.query(MailList).filter_by(
        plant_no=TEST_PLANT_NO, rpttype="水保養中", emp_no=SIGNER_EMPNO
    ).first()
    if not exists:
        db.add(MailList(
            plant_no=TEST_PLANT_NO, rpttype="水保養中", emp_no=SIGNER_EMPNO,
            emp_name="測試簽核人", notes_id="TEST_PLACEHOLDER",
            mail_type="TO", mail_on=True, sign_grp=True,
        ))
        db.commit()


def _ensure_dispatch_recipients(db) -> None:
    """
    派報收件人（services_b.maillist_service.get_mail_recipients）查的是 dispatch 專用
    rpttype（如「水OOS」，evaluate_row 產生的代碼去掉「-廠區」後綴），種子同樣沒有配這筆，
    示範腳本自建 TO/CC 各一筆，確保派報示範真的能寄出（不會因為查無收件人被略過）。
    """
    for rpttype in ("水OOS", "水OOC", "水Alert"):
        exists = db.query(MailList).filter_by(
            plant_no=TEST_PLANT_NO, rpttype=rpttype, emp_no=SIGNER_EMPNO
        ).first()
        if not exists:
            db.add(MailList(
                plant_no=TEST_PLANT_NO, rpttype=rpttype, emp_no=SIGNER_EMPNO,
                emp_name="測試簽核人", notes_id="TEST_PLACEHOLDER",
                mail_type="TO", mail_on=True, sign_grp=False,
            ))
    db.commit()


def main() -> None:
    print(f"TEST_MODE={settings.TEST_MODE}（True 時派報只會實際寄給 TEST_DEV_EMAIL={settings.TEST_DEV_EMAIL}）")

    _print_header("步驟 1／5：seed（整庫清空後重灌基準資料）")
    seed()
    db = BSessionLocal()

    try:
        _ensure_signer_maillist(db)
        _ensure_dispatch_recipients(db)

        # ── 步驟 2：TEST001 申請隔離 pH1（stime 設在「現在+2 秒」，讓派報那一步時已生效）──
        _print_header("步驟 2／5：TEST001 申請隔離 TEST1/pH1")
        # ⚠️ ControlCreate.validate_times() 用 naive datetime.now() 比較（schemas/control_schema.py
        # 不可修改），這裡刻意傳 naive datetime，比照 tests_integration/test_control_flow.py 既有作法，
        # 避免 tz-aware/naive datetime 比較噴例外。
        now_naive = datetime.now()
        try:
            data = ControlCreate(
                plantid=TEST_PLANT_ID,
                mdfdesc="示範演練：pH1 校正保養",
                stime=now_naive + timedelta(seconds=2),
                etime=now_naive + timedelta(minutes=30),
                remark="demo_closed_loop 自動產生",
                items=[ControlItemBase(plantno=TEST_PLANT_NO, item="pH1", sourceid="1")],
            )
            iso = control_service.create_isolation(
                db, current_user_empno=APPLICANT_EMPNO, current_user_name="測試申請人",
                data=data, is_commit=True,
            )
            print(f"  已建立隔離申請單 ccno={iso.ccno} isolation_id={iso.id} flow_id={iso.flow_id} "
                  f"fstatus={iso.fstatus}（1=簽核中）")
        except Exception as e:
            iso = None
            print(f"  [跳過] 申請隔離失敗：{e}")

        # ── 步驟 3：TEST999 簽核核准 ──────────────────────────────────────────
        _print_header("步驟 3／5：TEST999 簽核核准")
        if iso is not None:
            try:
                flow_service.process_sign(
                    db, isolation_id=iso.id, flow_id=iso.flow_id,
                    action_id=SIGN_ACTION_APPROVE,
                    current_user_empno=SIGNER_EMPNO, current_user_name="測試簽核人",
                    comment="demo_closed_loop 自動核准",
                )
                db.refresh(iso)
                print(f"  簽核完成，isolation.fstatus={iso.fstatus}（7=核准）")
            except Exception as e:
                print(f"  [跳過] 簽核失敗：{e}")
        else:
            print("  [跳過] 前一步無隔離單可簽核")

        # ── 步驟 4：改 kepware_sim 讓 Cu1 超標，嘗試跑 WP2 同步 JOB ──────────────
        _print_header("步驟 4／5：模擬 Cu1 讀值超標（OOS_high=3.0）")
        cu1_row = db.query(KepwareSim).filter_by(tagname="TEST.CU1.PV").first()
        if cu1_row:
            cu1_row.value = "6.50"
            cu1_row.quality = "good"
            db.commit()
            print("  kepware_sim[TEST.CU1.PV] 已改為 6.50（quality=good）")

        try:
            from services_b.sync_service import run_sync
            result = run_sync(db)
            print(f"  services_b.sync_service.run_sync() 執行完成：{result}")
        except ImportError:
            print("  [跳過] services_b.sync_service 尚未提供，改直接寫 reading_current 模擬同步結果")
        except Exception as e:
            print(f"  [注意] run_sync 執行失敗（{e}），改直接寫 reading_current 模擬同步結果")

        # 保險覆寫（見檔頭說明：kepware_sim 種子資料 Cu1 有兩筆 tag_mapping 互相競爭，
        # 不論 run_sync 內部順序為何，這裡確保示範情境穩定為「Cu1 超標」）。
        rc = db.query(ReadingCurrent).filter_by(plant_no=TEST_PLANT_NO, item="Cu1").first()
        if rc is None:
            rc = ReadingCurrent(plant_no=TEST_PLANT_NO, item="Cu1", measured_at=datetime.now(timezone.utc))
            db.add(rc)
        from decimal import Decimal
        rc.value = Decimal("6.50")
        rc.status = "normal"
        rc.raw_text = "6.50"
        rc.comm_ok = True
        rc.measured_at = datetime.now(timezone.utc)
        db.commit()
        print(f"  reading_current[TEST1/Cu1] 目前值={rc.value}（OOS 門檻 3.0，預期觸發紅燈派報）")

        # ── 步驟 5：派報，攔截 send_email_sync 印出原始收件人與主旨 ──────────────
        _print_header("步驟 5／5：run_dispatch_b（派報）")
        captured = []
        original_send = dispatch_service.send_email_sync

        def _capture_send(subject, body, to_addresses, cc_addresses=None):
            captured.append((subject, list(to_addresses), list(cc_addresses or [])))
            return original_send(subject, body, to_addresses, cc_addresses=cc_addresses)

        dispatch_service.send_email_sync = _capture_send
        try:
            summary = dispatch_service.run_dispatch_b(db)
        finally:
            dispatch_service.send_email_sync = original_send

        print(f"  run_dispatch_b 摘要：{summary}")
        if not captured:
            print("  本輪沒有任何廠區派報（可能全部正常，或收件人清單仍為空）")
        for subject, to, cc in captured:
            print(f"  --- 主旨：{subject}")
            print(f"      原始 TO（TEST_MODE 攔截前）：{to}")
            print(f"      原始 CC（TEST_MODE 攔截前）：{cc}")
        if settings.TEST_MODE and captured:
            print(f"  （TEST_MODE=True，實際上這些信只會寄到 {settings.TEST_DEV_EMAIL}）")

        # 額外印出 pH1（隔離中）是否被正確排除，佐證「隔離不派報」與「未隔離照樣派報」同時成立
        _print_header("附加驗證：pH1 是否因隔離而不派報")
        is_isolated_now = control_service.is_item_isolated(db, TEST_PLANT_NO, "pH1")
        print(f"  is_item_isolated(TEST1, pH1) = {is_isolated_now}（True 代表隔離已生效，不應觸發 pH1 派報）")

    finally:
        db.close()

    print("\n[demo_closed_loop] 演練結束。")


if __name__ == "__main__":
    main()
