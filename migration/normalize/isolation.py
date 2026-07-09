"""
migration/normalize/isolation.py — A VOC_closectl + VOC_closectl_list → B Isolation + IsolationItem 純轉換函式。

契約（見 migration/normalize/__init__.py）：
    normalize_isolation(closectl_rows, closectl_list_rows, ctx)
        -> tuple[list[Isolation], list[IsolationItem]]

A 端來源欄位：
    VOC_closectl（models/control_model.py VocCloseCtl）：
        ccid, ttypeid, ccno, plantid, mdfdesc, stime, etime, remark,
        cempname, cempno, ctime, flowid, fstatusid, delclerk, orgccid,
        軟刪除欄位 —— ⚠️ ORM 屬性名是 del_flag，但實際 DB／dict key 是 'del'
        （見 VocCloseCtl: `del_flag = Column('del', Integer, default=0)`），
        本模組吃的是 SELECT * 匯出的原始 dict，故一律用 row.get('del', 0) 讀。
    VOC_closectl_list（models/control_model.py VocCloseCtlList）：
        id, ccid, plantno, item, sourceid

規則：
    - 只搬「現行有效」隔離：未刪除（row.get('del', 0) == 0）且結束時間未到（etime > ctx.now）。
      其餘（含已刪除、已過期）整列略過，連帶的 IsolationItem 明細也一併不搬。
    - id 保留原 ccid 當主鍵，讓 IsolationItem.isolation_id 對得上（不重新編號）。
    - 申請人改綁 ctx.personnel.applicants：A 端真人不進 B，依「有效隔離」的處理順序
      round-robin 分配（applicants[index % len(applicants)]），cemp_no/cemp_name 取自該人。
    - flow_id 一律 None（簽核流程不搬，使用者上線後會重新走簽核）。
    - org_id 一律 None（修改單的原單參照 orgccid 可能指向未搬入的列，一律斷開避免自我參照 FK 違反）。
    - deleted 固定 False（能進到這裡的都是未刪除、有效的）；del_clerk 固定 None。
    - IsolationItem 只保留 ccid 屬於「有被搬入」主檔的列；source_id 原始是字串，轉 int。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from migration.context import MigrationContext
from models_b import Isolation, IsolationItem

__all__ = ["normalize_isolation"]


def _parse_dt(value: Any) -> Optional[datetime]:
    """A 時間欄位（stime/etime/ctime）→ tz-aware datetime。

    容忍 str（ISO 格式，含 'Z' 尾綴）或 datetime；沒有 tzinfo 一律補 UTC。
    None/無法解析回傳 None（交給呼叫端決定要不要因此略過該列）。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_active(row: Dict[str, Any], now: datetime) -> bool:
    """「現行有效」判定：未刪除 且 結束時間未到。"""
    if row.get("del", 0) != 0:
        return False
    etime = _parse_dt(row.get("etime"))
    if etime is None:
        return False
    return etime > now


def normalize_isolation(
    closectl_rows: List[Dict[str, Any]],
    closectl_list_rows: List[Dict[str, Any]],
    ctx: MigrationContext,
) -> Tuple[List[Isolation], List[IsolationItem]]:
    """A VOC_closectl + VOC_closectl_list → B (list[Isolation], list[IsolationItem])。

    只搬現行有效隔離（del==0 且 etime > ctx.now）；申請人改綁 ctx.personnel.applicants
    （round-robin）；flow_id/org_id 一律 None；明細只保留有被搬入主檔的 ccid。
    """
    applicants = ctx.personnel.applicants
    isolations: List[Isolation] = []
    migrated_ccids: set = set()

    active_index = 0
    for row in closectl_rows:
        if not _is_active(row, ctx.now):
            continue

        ccid = row.get("ccid")
        stime = _parse_dt(row.get("stime"))
        etime = _parse_dt(row.get("etime"))
        ctime = _parse_dt(row.get("ctime"))

        person = applicants[active_index % len(applicants)]
        active_index += 1

        isolations.append(
            Isolation(
                id=ccid,
                ccno=row.get("ccno"),
                ttype=row.get("ttypeid"),
                org_id=None,
                plant_id=row.get("plantid"),
                mdfdesc=row.get("mdfdesc"),
                remark=row.get("remark"),
                stime=stime,
                etime=etime,
                cemp_no=person.empno,
                cemp_name=person.name,
                created_at=ctime,
                flow_id=None,
                fstatus=row.get("fstatusid"),
                deleted=False,
                del_clerk=None,
            )
        )
        migrated_ccids.add(ccid)

    items: List[IsolationItem] = []
    for row in closectl_list_rows:
        ccid = row.get("ccid")
        if ccid not in migrated_ccids:
            continue

        source_id = row.get("sourceid")
        items.append(
            IsolationItem(
                isolation_id=ccid,
                plant_no=row.get("plantno"),
                item=row.get("item"),
                source_id=int(source_id) if source_id is not None else None,
            )
        )

    return isolations, items
