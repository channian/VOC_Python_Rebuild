"""
services_b/spec_service.py — 規格值維護 + 規格簽核申請（Schema B 資料層版本）

對應 services/spec_service.py（A/MSSQL 版）。B 版資料層差異（schema_B_設計提案.md B 項決策）：

  1. 門檻值不再是 varchar（'6-9' 雙邊字串／'-' 無效值），spec 表已拆 low/high numeric + status
     （valid/na/building）欄位，**直接讀寫數值**，不需要 A 版 `_parse_bounds()` 那套字串解析；
     本檔案的驗證只需比較數字大小（low < high），不重寫 A 版 `parse_spec_bound()` 那套逐字元格式
     檢查（那是給「使用者輸入字串」用的，B 版表單輸入格式若仍是字串，轉數字這一步交給呼叫端
     的 Pydantic schema／表單層，不在本檔重複）。
  2. pH1/COD2 顯示映射改用 `item.display_name` 資料驅動查表（`display_name_for()`），
     取代 A 版程式硬編的 `to_storage_item()` / `to_display_item()` 字串替換表。
     ⚠️ 儲存鍵仍是 spec.item（如 'pH1'），呼叫端（router/表單）必須直接傳入正確的儲存鍵，
     B 版不做「同一顯示名稱、不同廠區對應不同儲存鍵」的反查——因為 B 的 item 是全域主檔，
     每個 (plant_no, item) 組合在 spec 表本來就是各自獨立的一列，沒有 A 版那種「同一顯示名稱
     用字串替換橋接多個實際儲存鍵」的必要（此為 B 架構相對 A 架構的簡化差異，見任務回報）。
  3. 規格簽核申請（spec_apply）與 A 版的「架構差異」：**QA 來源連動改為不需要**。
     A 版 `_sync_scada_web_if_qa()` 在來源=QA 時，把新 OOS/OOC/alert 同步寫回 VOC_SCADA_WEB，
     因為 A 版「SPEC 規格值」與「SCADA 管制值」共用同一張 VOC_SCADA_WEB 表（管制值就是拿
     SPEC 的值抄一份過去，QA 改了規格要順便更新那張表的管制值才能讓燈號正確判斷）。
     B 版 spec 是 spec、reading_current 是 reading_current，各自獨立：reading_current 的
     scada_*/cwms_* 管制值是由同步 JOB 依 tag_mapping 從 SCADA/CWMS 端實際讀回寫入的「對方
     系統實際設定值」，不是从 SPEC 複製來的鏡像欄位；spec 改了之後，B 版燈號的「管制值不一致」
     判斷（`_bounds_mismatch`）本來就是在比較 spec vs reading_current.scada_*/cwms_*，
     兩張表天生分離，沒有「改 spec 要順便覆寫 reading_current 管制值」這個必要、也沒有安全的
     做法這樣做（reading_current 的管制值意義是「對方系統目前設定的值」，覆寫等於偽造）。
  4. 簽核流程（sign_flow/sign_flow_step）資料層屬 WP3 範疇（`services_b/flow_service.py`
     尚未建立），本檔案的 `create_spec_apply()` 只建立 spec_apply 申請單主檔（formno/payload/
     fstatus=待簽核），不建立簽核流程；main_b 組裝時應在呼叫本函式後，另外呼叫 WP3 對應函式
     建立流程並回填 flow_id/fstatus。`apply_spec_from_form()` 只負責「核准後套用」這一步，
     交易邊界（commit/rollback）交由呼叫端（WP3 的 process_spec_sign 等價函式）控制，
     本函式與 create_spec_apply 一樣採 fail-fast：例外時各自 rollback 並重新拋出。
  5. ⚠️ 刪除規格的資料完整性（models_b.py 凍結，接手時實測發現的真實 FK 限制）：
     `reading_current` 對 `spec` 有硬 FK（`ForeignKeyConstraint(["plant_no","item"],
     ["spec.plant_no","spec.item"])`，models_b.py 未加 ON DELETE CASCADE），A 版 VOC_SCADA_WEB
     與 VOC_SPEC 之間沒有這種強制約束，所以 A 版 `delete_spec()` 直接刪 VOC_SPEC 也不會出錯。
     B 版若比照 A 版原樣刪 spec，只要該廠區/項目已經有過讀值（reading_current 有一筆），
     就會直接被 DB 擋下（ForeignKeyViolation）。這裡的處理方式：刪除規格時一併刪除對應的
     `reading_current`（該項目已經沒有規格可比對，留著「目前讀值」也沒有意義；
     `reading_history` 沒有 FK 到 spec，是獨立的稽核軌跡，不受影響、不刪除，符合
     append-only 精神——刪規格後仍查得到歷史紀錄，只是「目前值」欄位一併清空）。

沿用重用（禁止複製）：
  - `services.control_service.next_ccno`：formno 與 ccno 格式相同（yyyyMMddNNN 11 碼流水號）。
  - `services.flow_service.FlowStatus`：簽核狀態值（待簽核=0／簽核中=1／核准=7／否決=8），
    禁止在本檔另外寫死數字。
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from models_b import Spec, SpecApply, Item, Source, Tranlog, ReadingCurrent
from services.control_service import next_ccno
from services.flow_service import FlowStatus


# ── 顯示名稱查表（G 項：取代程式硬編 pH1/COD2 映射）─────────────────────────

def display_name_for(db: Session, item: str) -> str:
    """
    回傳 item 的顯示名稱（item.display_name），查無則原樣回傳 item 本身。
    對應 A 版 `to_display_item()`，但資料驅動（查 item 主檔）而非程式硬編字串替換表。
    """
    row = db.query(Item.display_name).filter(Item.item == item).first()
    if row and row[0]:
        return row[0]
    return item


# ── 規格值查詢 / 直接維護（EditSPEC）──────────────────────────────────────────

def list_specs(db: Session, plant_no: str = "", item: str = "") -> List[dict]:
    """
    查詢規格值資料（B 版：numeric 門檻直接回傳，不需要字串化）。
    回傳 dict list（而非 Pydantic model）：B 版門檻形狀（low/high/status 六組）與 A 版
    `SpecResponse`（單一字串門檻）差異太大，暫不強行套用既有 schema；欄位命名與
    schema_B_設計提案.md 的 spec 表定義 1:1 對應，供未來新增 B 專用 schema 時直接映射。
    """
    query = (
        db.query(Spec, Item.display_name, Item.unit, Source.name)
        .join(Item, Item.item == Spec.item)
        .outerjoin(Source, Source.source_id == Spec.source_id)
    )
    if plant_no:
        query = query.filter(Spec.plant_no == plant_no)
    if item:
        query = query.filter(Spec.item == item)
    rows = query.order_by(Spec.plant_no, Spec.seqno).all()

    result = []
    for spec, display_name, unit, source_name in rows:
        result.append({
            "plant_no": spec.plant_no,
            "item": spec.item,
            "display_name": display_name or spec.item,
            "unit": unit,
            "law_text": spec.law_text,
            "oos_low": spec.oos_low, "oos_high": spec.oos_high, "oos_status": spec.oos_status,
            "ooc_low": spec.ooc_low, "ooc_high": spec.ooc_high, "ooc_status": spec.ooc_status,
            "alert_low": spec.alert_low, "alert_high": spec.alert_high, "alert_status": spec.alert_status,
            "recv_low": spec.recv_low, "recv_high": spec.recv_high, "recv_status": spec.recv_status,
            "source_id": spec.source_id, "source_name": source_name,
            "seqno": spec.seqno,
        })
    return result


def get_sources(db: Session) -> List[dict]:
    """取得資料來源清單，供規格維護表單下拉選單使用。

    ⚠️ 回傳 key 必須是 sourceid/source（A 棧形狀）——spec_modal.html 是兩棧共用模板，
    JS 的 SPEC_SOURCES 讀 s.sourceid/s.source；之前回 source_id/name 導致來源下拉
    全部顯示 undefined（2026-07-10 使用者實測發現，誤以為編輯功能沒實作）。
    """
    rows = db.query(Source.source_id, Source.name).order_by(Source.source_id).all()
    return [{"sourceid": r[0], "source": r[1]} for r in rows]


def _num(v: Optional[Decimal]) -> Optional[float]:
    """Decimal -> float，供 JSON 欄位（tranlog.data_before/after）序列化用（Decimal 非原生可序列化型別）。"""
    return float(v) if v is not None else None


def _spec_snapshot_dict(spec: Optional[Spec]) -> Optional[dict]:
    """組出 tranlog 用的 spec 快照（H 項決策：jsonb 取代 A 版斜線字串）。"""
    if spec is None:
        return None
    return {
        "plant_no": spec.plant_no, "item": spec.item, "law_text": spec.law_text,
        "oos_low": _num(spec.oos_low), "oos_high": _num(spec.oos_high), "oos_status": spec.oos_status,
        "ooc_low": _num(spec.ooc_low), "ooc_high": _num(spec.ooc_high), "ooc_status": spec.ooc_status,
        "alert_low": _num(spec.alert_low), "alert_high": _num(spec.alert_high), "alert_status": spec.alert_status,
        "recv_low": _num(spec.recv_low), "recv_high": _num(spec.recv_high), "recv_status": spec.recv_status,
        "source_id": spec.source_id, "seqno": spec.seqno,
    }


def _delete_reading_current_if_exists(db: Session, plant_no: str, item: str) -> None:
    """
    刪除規格前，先清掉對應的 reading_current（見檔頭第 5 點：models_b.py 的硬 FK 限制）。
    reading_history 不受影響（無 FK、append-only，稽核軌跡照留）。
    """
    rc = db.query(ReadingCurrent).filter_by(plant_no=plant_no, item=item).first()
    if rc is not None:
        db.delete(rc)
        db.flush()


_SPEC_EDITABLE_FIELDS = (
    "law_text",
    "oos_low", "oos_high", "oos_status",
    "ooc_low", "ooc_high", "ooc_status",
    "alert_low", "alert_high", "alert_status",
    "recv_low", "recv_high", "recv_status",
    "source_id", "seqno",
)


def create_spec(db: Session, current_user_empno: str, plant_no: str, item: str,
                 remark: str = "", **fields) -> Spec:
    """
    新增規格值。fields 可傳 `_SPEC_EDITABLE_FIELDS` 內任一欄位（numeric 門檻直接傳數字）。
    對應 A 版 `create_spec()`，差異：門檻直接存數值，tranlog 存 jsonb 快照而非斜線字串。
    """
    try:
        existing = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
        if existing:
            raise ValueError("此筆資料已存在規格值資料內!")

        unknown = set(fields) - set(_SPEC_EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"未知的規格欄位: {sorted(unknown)}")

        spec = Spec(
            plant_no=plant_no, item=item,
            source_id=fields.get("source_id", 1),
            seqno=fields.get("seqno", 0),
            updated_at=datetime.now(timezone.utc),
        )
        for f in _SPEC_EDITABLE_FIELDS:
            if f in fields:
                setattr(spec, f, fields[f])
        db.add(spec)
        db.flush()

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="I",
            data_before=None, data_after=_spec_snapshot_dict(spec), remark=remark,
        ))
        db.commit()
        return spec
    except Exception:
        db.rollback()
        raise


def update_spec(db: Session, current_user_empno: str, plant_no: str, item: str,
                 remark: str = "", **fields) -> Spec:
    """更新規格值（僅更新有傳入的欄位）。對應 A 版 `update_spec()`。"""
    try:
        spec = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
        if not spec:
            raise ValueError("找不到資料!")

        unknown = set(fields) - set(_SPEC_EDITABLE_FIELDS)
        if unknown:
            raise ValueError(f"未知的規格欄位: {sorted(unknown)}")

        before = _spec_snapshot_dict(spec)
        for f in _SPEC_EDITABLE_FIELDS:
            if f in fields:
                setattr(spec, f, fields[f])
        spec.updated_at = datetime.now(timezone.utc)
        db.flush()

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="M",
            data_before=before, data_after=_spec_snapshot_dict(spec), remark=remark,
        ))
        db.commit()
        return spec
    except Exception:
        db.rollback()
        raise


def delete_spec(db: Session, current_user_empno: str, plant_no: str, item: str, remark: str = "") -> bool:
    """刪除規格值。對應 A 版 `delete_spec()`。"""
    try:
        spec = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
        if not spec:
            raise ValueError("找不到資料!")

        before = _spec_snapshot_dict(spec)
        _delete_reading_current_if_exists(db, plant_no, item)
        db.delete(spec)

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="D",
            data_before=before, data_after=None, remark=remark,
        ))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


# ── 規格簽核申請（spec_apply，僅建申請單，不建簽核流程——見檔頭說明）────────────

def _check_no_pending_apply(db: Session, plant_no: str, item: str) -> None:
    """
    對應 A 版 `_check_no_pending_apply()`：同廠區/項目若已有一筆「送簽流程尚未結案」的申請單，
    禁止重覆申請。

    ⚠️ 與 A 版的刻意差異（修正半成品遺留的防呆破洞）：A 版 `create_spec_apply()` 在同一次呼叫
    內就會立刻建立簽核流程，把 fstatus 由待簽核(0) 原子推進到簽核中(1)，所以 A 版只需擋
    「簽核中」。本檔 `create_spec_apply()`（見檔頭第 4 點）刻意不建流程——flow 建立延後到
    main_b 組裝時另外呼叫 WP3 對應函式——因此呼叫完當下 fstatus 恆為待簽核(0)。若這裡沿用
    A 版只擋「簽核中」，在 main_b 尚未接上 WP3 建流程之前這個防呆永遠不會生效（DB 裡根本
    不會出現 fstatus=簽核中(1) 的申請單），同一項目可以被重覆送出多筆待簽核申請。
    這裡擴大為「待簽核(0) 或 簽核中(1)」皆視為擋重覆，確保本檔案在 WP3 尚未接線時防呆仍然有效；
    main_b 接上 WP3 建流程後行為不變（因為那時申請單本來就會落在這兩個狀態之一）。
    """
    pending = (
        db.query(SpecApply)
        .filter(
            SpecApply.plant_no == plant_no,
            SpecApply.item == item,
            SpecApply.fstatus.in_((int(FlowStatus.待簽核), int(FlowStatus.簽核中))),
        )
        .first()
    )
    if pending:
        raise ValueError("前筆資料待主管簽核中, 不得重覆申請!")


def _next_formno(db: Session) -> str:
    """formno 流水號（yyyyMMddNNN），沿用 `control_service.next_ccno` 純函式重用同一套規則。"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    last_row = (
        db.query(SpecApply.formno)
        .filter(SpecApply.formno.like(f"{today}%"))
        .order_by(SpecApply.formno.desc())
        .first()
    )
    return next_ccno(last_row[0] if last_row else None, today)


def create_spec_apply(
    db: Session, current_user_empno: str, plant_no: str, item: str, ftype: str,
    payload: dict, remark: str = "",
) -> SpecApply:
    """
    建立一筆規格送簽申請單（B 版）。對應 A 版 `create_spec_apply()`。

    payload 為申請的規格新值（jsonb），鍵名比照 `_SPEC_EDITABLE_FIELDS`，供
    `apply_spec_from_form()` 核准套用時直接讀取。

    ⚠️ 範圍界定（見檔頭第 4 點）：本函式**不建立簽核流程**，fstatus 固定寫入待簽核(0)；
    main_b 組裝時需另外呼叫 WP3 的建流程函式並回填 flow_id/fstatus=簽核中(1)。
    """
    if ftype not in ("I", "M", "D"):
        raise ValueError("ftype 必須為 I(新增)/M(修改)/D(刪除)")

    try:
        if ftype == "I":
            existing_spec = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
            if existing_spec:
                raise ValueError("此筆資料已存在規格值資料內，無法重覆新增!")

        _check_no_pending_apply(db, plant_no, item)

        formno = _next_formno(db)

        apply_row = SpecApply(
            formno=formno, ftype=ftype, plant_no=plant_no, item=item,
            payload=payload, emp_no=current_user_empno, fstatus=int(FlowStatus.待簽核),
        )
        db.add(apply_row)
        db.flush()

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="I", data_before=None,
            data_after={
                "formno": formno, "ftype": ftype, "plant_no": plant_no, "item": item, "payload": payload,
            },
            remark=remark,
        ))
        db.commit()
        return apply_row
    except Exception:
        db.rollback()
        raise


def list_spec_applies(db: Session, plant_no: str = "", item: str = "",
                       fstatus: Optional[int] = None) -> List[SpecApply]:
    """查詢規格申請單（我的申請單／待簽核清單的資料層基礎，排序同 A 版：依建立時間新到舊）。"""
    query = db.query(SpecApply)
    if plant_no:
        query = query.filter(SpecApply.plant_no == plant_no)
    if item:
        query = query.filter(SpecApply.item == item)
    if fstatus is not None:
        query = query.filter(SpecApply.fstatus == fstatus)
    return query.order_by(SpecApply.created_at.desc()).all()


# ── 核准後套用回 spec（I=新增/M=修改/D=刪除）─────────────────────────────────

def apply_spec_from_form(db: Session, spec_apply_id: int, current_user_empno: str) -> None:
    """
    把一筆已核准的 spec_apply 申請內容套用回 spec（I/M/D），對應 A 版 `apply_spec_from_form()`。

    B 版差異：payload 已是 jsonb 數值形狀，直接讀出即可，不需要 A 版重新字串化 LAW/OOS/OOC/alert；
    QA 來源連動（A 版 `_sync_scada_web_if_qa`）在 B 不需要——見檔頭第 3 點架構差異說明。

    不在此函式內 commit——交易邊界交由呼叫端（WP3 的 process_spec_sign 等價函式）統一控制，
    與 A 版設計原則一致（避免巢狀呼叫各自 commit 導致部分異動無法回滾）。
    """
    apply_row = db.query(SpecApply).filter_by(id=spec_apply_id).first()
    if apply_row is None:
        raise ValueError(f"找不到規格申請單 id={spec_apply_id}")

    ftype = apply_row.ftype
    plant_no = apply_row.plant_no
    item = apply_row.item
    payload = apply_row.payload or {}

    if ftype == "I":
        existing = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
        if existing:
            raise ValueError("此筆資料已存在規格值資料內，無法重覆新增!")
        spec = Spec(
            plant_no=plant_no, item=item,
            source_id=payload.get("source_id", 1),
            seqno=payload.get("seqno", 0),
            updated_at=datetime.now(timezone.utc),
        )
        for f in _SPEC_EDITABLE_FIELDS:
            if f in payload:
                setattr(spec, f, payload[f])
        db.add(spec)
        db.flush()
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="I", data_before=None,
            data_after=_spec_snapshot_dict(spec),
            remark=f"規格套用(新增): spec_apply_id={spec_apply_id}",
        ))

    elif ftype == "M":
        spec = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
        if spec is None:
            raise ValueError(f"找不到規格值資料可修改: {plant_no}/{item}")
        before = _spec_snapshot_dict(spec)
        for f in _SPEC_EDITABLE_FIELDS:
            if f in payload:
                setattr(spec, f, payload[f])
        spec.updated_at = datetime.now(timezone.utc)
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="M", data_before=before,
            data_after=_spec_snapshot_dict(spec),
            remark=f"規格套用(修改): spec_apply_id={spec_apply_id}",
        ))

    elif ftype == "D":
        spec = db.query(Spec).filter_by(plant_no=plant_no, item=item).first()
        if spec is None:
            raise ValueError(f"找不到規格值資料可刪除: {plant_no}/{item}")
        before = _spec_snapshot_dict(spec)
        _delete_reading_current_if_exists(db, plant_no, item)
        db.delete(spec)
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="D", data_before=before, data_after=None,
            remark=f"規格套用(刪除): spec_apply_id={spec_apply_id}",
        ))

    else:
        raise ValueError(f"未知的 ftype: {ftype}")
