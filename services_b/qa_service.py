"""
services_b/qa_service.py — QA 手測值輸入（Schema B 資料層版本）

對應 services/qa_service.py（A/MSSQL 版）。A 版直接覆寫 VOC_SCADA_WEB.rvalue 字串欄位；
B 版寫入 reading_current(value+status+raw_text+measured_at) 新形狀，並依「與同步 JOB 相同規則」
在寫入 reading_current 的同時 append 一筆 reading_history（含當下生效的 SPEC 三階管制值快照，
供法規稽核回溯「當時管制值」——這是 schema_B_設計提案.md 的稽核決策，任何寫讀值的路徑
都必須遵守，不只是同步 JOB）。

⚠️ 待整合說明：`_append_reading_history()` 是本檔自行實作的最小版本（只寫 spec_* 快照，
不含 SCADA/CWMS 自設管制值快照 limits_extra——QA 手測值本來就與 SCADA/CWMS 無關，
limits_extra 留空合理）。若 WP2 `services_b/sync_service.py` 已提供對應的共用寫入 helper
（例如「組 reading_history 列」的函式），應改 import 該 helper 以避免兩處重複維護規則；
截至本檔案建立時 `services_b/` 目錄尚無 `sync_service.py`，故先自行實作，待 WP2 完成後
由主控評估是否收斂成單一共用函式。

沿用重用（禁止複製）：
  - schemas/qa_schema.py QAUpdate：輸入格式驗證（N.D 或數字最多兩位小數）。
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from models_b import Spec, ReadingCurrent, ReadingHistory, Tranlog
from schemas.qa_schema import QAUpdate

QA_SOURCE_ID = 3


def list_qa_items(db: Session) -> List[dict]:
    """取得所有 QA 手測項目（spec.source_id=QA_SOURCE_ID）與目前讀值，供 qa_modal 表格顯示。"""
    rows = (
        db.query(Spec, ReadingCurrent)
        .outerjoin(
            ReadingCurrent,
            (ReadingCurrent.plant_no == Spec.plant_no) & (ReadingCurrent.item == Spec.item),
        )
        .filter(Spec.source_id == QA_SOURCE_ID)
        .order_by(Spec.plant_no, Spec.seqno)
        .all()
    )
    result = []
    for spec, rc in rows:
        result.append({
            "plant_no": spec.plant_no, "item": spec.item,
            "oos_high": spec.oos_high, "ooc_high": spec.ooc_high, "alert_high": spec.alert_high,
            "value": rc.value if rc else None,
            "status": rc.status if rc else "building",
            "raw_text": rc.raw_text if rc else "",
            "measured_at": rc.measured_at if rc else None,
        })
    return result


def _spec_snapshot(spec: Optional[Spec]) -> dict:
    """組出 reading_history 需要的 spec_* 管制值快照欄位（無 spec 時全 None，理論上不會發生
    ——QA 手測值一定有對應 spec 才允許寫入，見 update_qa_value 的防呆）。"""
    if spec is None:
        return dict(
            spec_oos_low=None, spec_oos_high=None, spec_ooc_low=None, spec_ooc_high=None,
            spec_alert_low=None, spec_alert_high=None, spec_recv_low=None, spec_recv_high=None,
        )
    return dict(
        spec_oos_low=spec.oos_low, spec_oos_high=spec.oos_high,
        spec_ooc_low=spec.ooc_low, spec_ooc_high=spec.ooc_high,
        spec_alert_low=spec.alert_low, spec_alert_high=spec.alert_high,
        spec_recv_low=spec.recv_low, spec_recv_high=spec.recv_high,
    )


def update_qa_value(db: Session, current_user_empno: str, plant_no: str, item: str,
                     rvalue: str, remark: str = "") -> bool:
    """
    更新單筆 QA 手測值（B 版）。
    防呆：該 (plant_no, item) 必須是 QA 來源（spec.source_id=QA_SOURCE_ID），
    避免覆蓋同步 JOB 寫入的 SCADA/CWMS 值（對齊 A 版同一防呆）。

    寫入內容：
      1. reading_current：value/status/raw_text/measured_at（該項目的「目前值」，upsert）。
      2. reading_history：append-only 新增一筆，含當下 spec 三階管制值快照（稽核決策）。
      3. tranlog：異動軌跡（jsonb before/after，H 項決策）。
    """
    validated = QAUpdate(plantno=plant_no, item=item, rvalue=rvalue, remark=remark)
    rvalue = validated.rvalue  # 經過格式驗證/正規化（"N.D" 或數字字串，最多兩位小數）

    spec = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
    if spec is None or spec.source_id != QA_SOURCE_ID:
        raise ValueError("此項目非 QA 手測來源，不可手動輸入!")

    try:
        now = datetime.now(timezone.utc)
        is_nd = (rvalue == "N.D")
        value: Optional[Decimal] = None if is_nd else Decimal(rvalue)
        status = "nd" if is_nd else "normal"

        rc = db.query(ReadingCurrent).filter_by(plant_no=plant_no, item=item).first()
        old_snapshot = {
            "value": float(rc.value) if (rc and rc.value is not None) else None,
            "status": rc.status if rc else None,
            "raw_text": rc.raw_text if rc else None,
        }

        if rc:
            rc.value = value
            rc.status = status
            rc.raw_text = rvalue
            rc.measured_at = now
            rc.updated_at = now
        else:
            rc = ReadingCurrent(
                plant_no=plant_no, item=item, value=value, status=status, raw_text=rvalue,
                comm_ok=True, scada_limit_status="na", cwms_limit_status="na",
                measured_at=now, updated_at=now,
            )
            db.add(rc)

        db.add(ReadingHistory(
            plant_no=plant_no, item=item, value=value, status=status, raw_text=rvalue,
            measured_at=now, **_spec_snapshot(spec),
        ))

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="M",
            data_before={"plant_no": plant_no, "item": item, **old_snapshot},
            data_after={"plant_no": plant_no, "item": item, "value": rvalue, "status": status},
            remark=remark,
        ))

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
