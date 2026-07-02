"""
spec_service.py — 規格值維護（EditSPEC）+ 規格簽核申請（ApplySPEC / SignSPEC / VOC_SPEC_apply）

對應舊系統 legacy/EditSPEC.aspx.cs、legacy/ApplySPEC.aspx.cs、legacy/SignSPEC.aspx.cs、
legacy/dbVOC.cs 內 InsertSPEC/UpdateSPEC/DeleteSPEC/SPEC送簽/ProcSignSPEC/List我的待辦事項1/
List廠區項目1 等方法。落差清單 #5、#7（見 docs/legacy_source_analysis.md 第五節）。

重要決策：
  - fruleid=9（法遵平台_法規許可值與規格值維護，見 legacy/dbVOC.cs:1643 `簽核流程` enum），
    與隔離簽核的 fruleid=8 不同，不能共用 flow_service 裡寫死 FRULEID_ISOLATION 的
    create_sign_flow()，這裡仿照相同 SQL 模式自寫 create_spec_sign_flow()。
  - ⚠️ legacy 的 SPEC送簽 整條路徑（送簽 + 核准套用）在原始碼裡有多處明顯錯誤
    （INSERT 語法漏逗號、Get簽核人員 的 rtype 參數傳入未加引號的 ftype、ProcSignSPEC 核准套用
    時查的是 VOC_SPEC 現有值而非申請的新值、對 'I' 新增案例會直接丟例外），且 EditSPEC.aspx.cs
    三個按鈕呼叫 SPEC送簽() 的程式碼整段被註解掉──研判這整條路徑從未在 legacy 正式環境跑過，
    是「schema 已設計、頁面已排版，但功能從未真正串接完成」的半成品。本檔案依「這條路徑應有的
    正確行為」重新實作（fruleid/簽核人邏輯沿用隔離簽核的既有模式），詳見各函式內註解。
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from models.spec_model import VocSpec, VocSource
from models.acl_model import VocTranlog
from schemas.spec_schema import (
    SpecCreate, SpecUpdate, SpecResponse,
    SpecApplyCreate, SpecApplyListResponse, SpecSignAction,
)
from services.flow_service import (
    FlowStatus,
    get_signers,
    resolve_new_status,
    _get_emp_id,
    _get_pos_id,
    REVIEWER_TYPE_PERSON,
)
from services.control_service import next_ccno  # yyyyMMddNNN 流水號純函式，formno 沿用此規則

logger = logging.getLogger(__name__)


# ── 既有：規格值查詢 / 直接維護（EditSPEC 唯讀表格 + 既有編輯功能）───────────

def list_specs(db: Session, plantno: str = "", item: str = "") -> List[SpecResponse]:
    """ 查詢舊版 dbVOC.List規格值資料 """
    query = db.query(
        VocSpec.plantno, VocSpec.item, VocSpec.LAW, VocSpec.OOS, VocSpec.OOC, VocSpec.alert,
        VocSpec.source.label('sourceid'),
        VocSource.source
    ).outerjoin(VocSource, VocSpec.source == VocSource.sourceid)
    try:
        if plantno:
            query = query.filter(VocSpec.plantno == plantno)
        if item:
            query = query.filter(VocSpec.item == item)
        result = query.all()
    except Exception as e:
        print(f"DB Query Error: {e}")
        result = []

    if not result:
        return [
            SpecResponse(plantno="K1", item="VOC", LAW="100", OOS="80", OOC="60", alert="50", source="SCADA (SQL)", sourceid=1, tagname="K1_VOC"),
            SpecResponse(plantno="K2", item="pH", LAW="6-9", OOS="6.5-8.5", OOC="7-8", alert="7.2-7.8", source="CIM (Oracle)", sourceid=2, tagname="K2_pH"),
        ]

    return [SpecResponse.model_validate(row) for row in result]


def get_sources(db: Session) -> list:
    """取得資料來源清單，供規格維護表單下拉選單使用"""
    try:
        rows = db.query(VocSource.sourceid, VocSource.source).all()
        return [{"sourceid": r.sourceid, "source": r.source} for r in rows]
    except Exception as e:
        print(f"[get_sources] DB 查詢失敗: {e}")
        return [
            {"sourceid": 1, "source": "SCADA (SQL)"},
            {"sourceid": 2, "source": "CWMS"},
            {"sourceid": 3, "source": "QA 手測"},
        ]

def create_spec(db: Session, current_user_empno: str, data: SpecCreate) -> bool:
    try:
        # 防呆
        existing = db.query(VocSpec).filter_by(plantno=data.plantno, item=data.item).first()
        if existing:
            raise ValueError("此筆資料已存在規格值資料內!")

        new_spec = VocSpec(
            plantno=data.plantno,
            item=data.item,
            LAW=data.LAW,
            OOS=data.OOS,
            OOC=data.OOC,
            alert=data.alert,
            source=data.source_id,
            status=1,
            tagname=f"{data.plantno}_{data.item}"
        )
        db.add(new_spec)

        # 寫入 TranLog
        log_str = f"{data.plantno}/{data.item}/{data.LAW}/{data.OOS}/{data.OOC}/{data.alert}/{data.source_id}"
        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="I",
            databefore="",
            dataafter=log_str,
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Create SPEC Error: {e}")
        return False

def update_spec(db: Session, current_user_empno: str, data: SpecUpdate) -> bool:
    try:
        spec = db.query(VocSpec).filter_by(plantno=data.plantno, item=data.item).first()
        if not spec:
            raise ValueError("找不到資料!")

        old_log_str = f"{spec.plantno}/{spec.item}/{spec.LAW}/{spec.OOS}/{spec.OOC}/{spec.alert}/{spec.source}"

        spec.LAW = data.LAW
        spec.OOS = data.OOS
        spec.OOC = data.OOC
        spec.alert = data.alert
        spec.source = data.source_id
        spec.tagname = f"{data.plantno}_{data.item}"

        new_log_str = f"{data.plantno}/{data.item}/{data.LAW}/{data.OOS}/{data.OOC}/{data.alert}/{data.source_id}"

        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="M", # Modify
            databefore=old_log_str,
            dataafter=new_log_str,
            cdatetime=datetime.now(),
            remark=data.remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Update SPEC Error: {e}")
        return False

def delete_spec(db: Session, current_user_empno: str, plantno: str, item: str, remark: str = "") -> bool:
    try:
        spec = db.query(VocSpec).filter_by(plantno=plantno, item=item).first()
        if not spec:
            raise ValueError("找不到資料!")

        old_log_str = f"{spec.plantno}/{spec.item}/{spec.LAW}/{spec.OOS}/{spec.OOC}/{spec.alert}/{spec.source}"
        db.delete(spec)

        tran_log = VocTranlog(
            empno=current_user_empno,
            logtype="D",
            databefore=old_log_str,
            dataafter="",
            cdatetime=datetime.now(),
            remark=remark
        )
        db.add(tran_log)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Delete SPEC Error: {e}")
        return False


# ── pH1 / COD2 項目別名映射（純函式）─────────────────────────────────────────
# 對應 legacy/EditSPEC.aspx.cs GetData()（第 82-93 行）與 legacy/dbVOC.cs SPEC送簽()（第 2461-2470 行）
# 完全相同的映射規則；反向映射對應 legacy/dbVOC.cs List隔離廠區項目() / List廠區項目1()
# 用的 `Replace(Replace(item,'COD2','COD'),'pH1','pH')`。

_PH1_PLANTS = ("K14B", "K22", "九號放流口")


def to_storage_item(plantno: str, item: str) -> str:
    """
    顯示項目 -> 儲存項目別名。
    K14B / K22 / 九號放流口 的 pH -> pH1；K14B 的 COD -> COD2。其餘廠區/項目原樣不變。
    """
    if plantno in _PH1_PLANTS and item == "pH":
        return "pH1"
    if plantno == "K14B" and item == "COD":
        return "COD2"
    return item


def to_display_item(item: str) -> str:
    """ 儲存項目別名 -> 顯示項目：COD2->COD、pH1->pH，與廠區無關（存檔時已編碼過廠區資訊）。 """
    return item.replace("COD2", "COD").replace("pH1", "pH")


FTYPE_LABELS = {"I": "新增", "M": "修改", "D": "刪除"}


def ftype_label(ftype: str) -> str:
    """ ftype 代碼轉中文說明，對應 legacy List我的待辦事項1() 的 `Iif(ftype='I','新增',Iif(ftype='M','修改','刪除'))`。 """
    return FTYPE_LABELS.get(ftype, ftype)


# ── 規格簽核流程（fruleid=9）─────────────────────────────────────────────────
# 簽核流程.法遵平台_法規許可值與規格值維護 = 9（legacy/dbVOC.cs:1643）
FRULEID_SPEC = 9

# ⚠️ 待確認：legacy dbVOC.SPEC送簽() 呼叫 Proc建立簽核流程() 時，rtype 參數直接傳入 ftype
# （"I"/"M"/"D"），而 Get簽核人員() 是把 rtype 原樣字串接進 `RptType in (...)`（未加引號），
# 等同組出 `RptType in (I)` 這種無效 T-SQL（會噴 "Invalid column name 'I'"）。這條路徑從未被
# 呼叫過（見本檔案開頭說明），因此這個 bug 從未在正式環境爆出來。這裡改比照隔離簽核
# （flow_service.build_rtype_list 的「水保養中/空保養中」模式）用一個固定常數 RptType，
# 讓 VOC_SPEC_apply 送簽有一個能真正查到簽核人的規則；VOC_Mail_List 目前是否已有維護
# 這個 RptType 的名單、或應該用哪個既有值，需業務確認後再調整。
RPTTYPE_SPEC = "規格維護"


def create_spec_sign_flow(db: Session, plantno: str, empno: str, formid: int) -> int:
    """
    仿照 flow_service.create_sign_flow() 的「一階群組簽核」SQL 模式，改用 FRULEID_SPEC(=9)
    與 RPTTYPE_SPEC。flow_service.create_sign_flow() 本身把 fruleid 寫死成隔離專用的
    FRULEID_ISOLATION(=8)，依任務規範不可修改該檔，故在此仿照同一套 SQL 自寫一份規格版；
    員工 ID/職稱 ID 查詢（_get_emp_id/_get_pos_id）與簽核人查詢（get_signers）沿用
    flow_service 既有的通用函式，避免重複實作。
    """
    signer_empnos = get_signers(db, plantno, [RPTTYPE_SPEC], empno)
    if not signer_empnos:
        raise ValueError(
            f"廠區 {plantno} 尚未設定規格簽核人員（VOC_Mail_List.SignGrp=1, RptType={RPTTYPE_SPEC}），無法送簽"
        )

    applicant_empid = _get_emp_id(db, empno)

    flow_row = db.execute(
        text(
            "INSERT INTO [SignFlow].[dbo].[base_flow] "
            "([fruleid],[actstep],[fstatusid],[fid],[empid],[fstime]) "
            "OUTPUT INSERTED.flowid "
            "VALUES (:fruleid, 1, :fstatusid, :fid, :empid, :fstime)"
        ),
        {
            "fruleid": FRULEID_SPEC,
            "fstatusid": int(FlowStatus.簽核中),
            "fid": formid,
            "empid": applicant_empid,
            "fstime": datetime.now(),
        },
    ).first()
    flowid = flow_row[0]

    for signer_empno in signer_empnos:
        sign_empid = _get_emp_id(db, signer_empno)
        sign_posid = _get_pos_id(db, sign_empid)
        db.execute(
            text(
                "INSERT INTO [SignFlow].[dbo].[base_flowd] "
                "([flowid],[fstep],[ftype],[empid],[posid]) "
                "VALUES (:flowid, 1, :ftype, :empid, :posid)"
            ),
            {
                "flowid": flowid,
                "ftype": REVIEWER_TYPE_PERSON,
                "empid": sign_empid,
                "posid": sign_posid,
            },
        )

    return flowid


def _get_last_formno_today(db: Session, today: str) -> Optional[str]:
    row = db.execute(
        text(
            "SELECT TOP 1 formno FROM [VOC].[dbo].[VOC_SPEC_apply] "
            "WHERE formno LIKE :pattern ORDER BY formno DESC"
        ),
        {"pattern": f"{today}%"},
    ).first()
    return row[0] if row else None


def _check_no_pending_apply(db: Session, plantno: str, item: str) -> None:
    """
    對應 legacy dbVOC.CheckSPEC申請()：同廠區/項目若已有一筆「簽核中」的申請單，禁止重覆申請。
    """
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM [VOC].[dbo].[VOC_SPEC_apply] "
            "WHERE plantno=:plantno AND item=:item AND fstatusid=:fstatusid"
        ),
        {"plantno": plantno, "item": item, "fstatusid": int(FlowStatus.簽核中)},
    ).first()
    if row and row[0] > 0:
        raise ValueError("前筆資料待主管簽核中, 不得重覆申請!")


def create_spec_apply(
    db: Session,
    current_user_empno: str,
    current_user_name: str,
    data: SpecApplyCreate,
) -> int:
    """
    對應 legacy dbVOC.SPEC送簽(hrow, ftype)：建立一筆 VOC_SPEC_apply 送簽申請單。

    data.item 一律是「顯示用」項目名稱（如 "pH"），這裡先轉換成儲存別名（pH1/COD2）
    再寫入 VOC_SPEC_apply，與 legacy SPEC送簽() 的轉換時機一致。

    ⚠️ 與 legacy 的刻意差異：
      - legacy INSERT 語句的欄位清單 `[source][remark]` 中間漏了逗號（legacy/dbVOC.cs:2474），
        是語法錯誤，這裡修正。
      - ftype='I'（新增）情境額外補上「VOC_SPEC 是否已存在」防呆（比照 legacy CheckSPEC()，
        雖然 legacy 呼叫端也被註解掉，但新增送簽前擋下重覆項目屬合理防呆，予以保留）。
    """
    try:
        if data.ftype == "I":
            existing_spec = db.query(VocSpec).filter_by(
                plantno=data.plantno, item=to_storage_item(data.plantno, data.item)
            ).first()
            if existing_spec:
                raise ValueError("此筆資料已存在規格值資料內，無法重覆新增!")

        storage_item = to_storage_item(data.plantno, data.item)
        _check_no_pending_apply(db, data.plantno, storage_item)

        today = datetime.today().strftime('%Y%m%d')
        last_formno = _get_last_formno_today(db, today)
        formno = next_ccno(last_formno, today)  # 沿用 control_service 的 11 碼流水號純函式

        row = db.execute(
            text(
                "INSERT INTO [VOC].[dbo].[VOC_SPEC_apply] "
                "([formno],[ftype],[plantno],[item],[LAW],[OOS],[OOC],[alert],[source],[remark],"
                "[empno],[cdatetime],[flowid],[fstatusid]) "
                "OUTPUT INSERTED.formid "
                "VALUES (:formno,:ftype,:plantno,:item,:LAW,:OOS,:OOC,:alert,:source,:remark,"
                ":empno,:cdatetime,NULL,:fstatusid)"
            ),
            {
                "formno": formno, "ftype": data.ftype, "plantno": data.plantno, "item": storage_item,
                "LAW": data.LAW, "OOS": data.OOS, "OOC": data.OOC, "alert": data.alert,
                "source": data.source_id, "remark": data.remark or "",
                "empno": current_user_empno, "cdatetime": datetime.now(),
                "fstatusid": int(FlowStatus.待簽核),
            },
        ).first()
        formid = row[0]

        flowid = create_spec_sign_flow(db, data.plantno, current_user_empno, formid)

        db.execute(
            text(
                "UPDATE [VOC].[dbo].[VOC_SPEC_apply] SET flowid=:flowid, fstatusid=:fstatusid "
                "WHERE formid=:formid"
            ),
            {"flowid": flowid, "fstatusid": int(FlowStatus.簽核中), "formid": formid},
        )

        db.add(VocTranlog(
            empno=current_user_empno, logtype="I", databefore="",
            dataafter=(
                f"規格送簽: formno={formno}, ftype={data.ftype}({ftype_label(data.ftype)}), "
                f"{data.plantno}/{storage_item}/{data.LAW}/{data.OOS}/{data.OOC}/{data.alert}/{data.source_id}"
            ),
            cdatetime=datetime.now(), remark=data.remark or "",
        ))
        db.commit()
        return formid
    except Exception as e:
        db.rollback()
        raise e


# ── 核准後套用回 VOC_SPEC（I=INSERT/M=UPDATE/D=DELETE）──────────────────────
# 對應 legacy SignSPEC.aspx.cs btn簽核_Click() 內 switch(ftype) 呼叫 InsertSPEC/UpdateSPEC/DeleteSPEC
# 的部分，但改套用「申請單裡的新值」而非 legacy 誤用的「VOC_SPEC 現有值」（見本檔開頭說明）。
# 這裡不直接呼叫上面的 create_spec/update_spec/delete_spec，因為那三支各自 commit/rollback，
# 若巢狀呼叫、且後續簽核狀態更新/tranlog 失敗，前面已 commit 的異動就無法被回滾；改寫成
# 不自行 commit 的內部版本，交由呼叫端（process_spec_sign）統一控制交易邊界。

def _source_name(db: Session, source_id: int) -> Optional[str]:
    row = db.execute(
        text("SELECT source FROM [VOC].[dbo].[VOC_source] WHERE sourceid=:sourceid"),
        {"sourceid": source_id},
    ).first()
    return row[0] if row else None


def _sync_scada_web_if_qa(db: Session, plantno: str, item: str, source_id: int, OOS: str, OOC: str, alert: str) -> None:
    """
    對應 legacy dbVOC.UpdateSPEC() 的 QA -> SCADA_WEB 連動（落差清單 #7）：
    來源為 QA（VOC_source.source 精確等於 "QA"）時，把新的 OOS/OOC/alert 同步寫回
    VOC_SCADA_WEB，讓儀表板燈號判斷（讀 VOC_SCADA_WEB 的管制值）能立即反映最新規格。
    ⚠️ VOC_source 實際資料未知（現有 get_sources() 的 fallback mock 是 "QA 手測" 不是 "QA"），
    這裡先比照 legacy 做精確字串比對，待確認 VOC_source.source 真實內容後可能要調整比對方式。
    """
    source_name = _source_name(db, source_id)
    if source_name == "QA":
        db.execute(
            text(
                "UPDATE [VOC].[dbo].[VOC_SCADA_WEB] SET OOS_HH=:OOS, OOC_H=:OOC, alert=:alert "
                "WHERE plantno=:plantno AND item=:item"
            ),
            {"OOS": OOS, "OOC": OOC, "alert": alert, "plantno": plantno, "item": item},
        )


def apply_spec_from_form(db: Session, formid: int, current_user_empno: str) -> None:
    """
    把一筆已核准的 VOC_SPEC_apply 申請內容套用回 VOC_SPEC（I=新增/M=修改/D=刪除），
    並依 ftype 寫對應的 VOC_tranlog（比照 legacy InsertSPEC/UpdateSPEC/DeleteSPEC 各自的
    tranlog 寫法），不在此函式內 commit——交易邊界由呼叫端（process_spec_sign）統一控制。
    """
    apply_row = db.execute(
        text("SELECT * FROM [VOC].[dbo].[VOC_SPEC_apply] WHERE formid=:formid"),
        {"formid": formid},
    ).mappings().first()
    if not apply_row:
        raise ValueError(f"找不到規格申請單 formid={formid}")

    ftype = apply_row["ftype"]
    plantno = apply_row["plantno"]
    item = apply_row["item"]  # 已是儲存別名（pH1/COD2），直接對 VOC_SPEC 操作

    if ftype == "I":
        existing = db.query(VocSpec).filter_by(plantno=plantno, item=item).first()
        if existing:
            raise ValueError("此筆資料已存在規格值資料內，無法重覆新增!")
        db.add(VocSpec(
            plantno=plantno, item=item,
            LAW=apply_row["LAW"], OOS=apply_row["OOS"], OOC=apply_row["OOC"], alert=apply_row["alert"],
            source=apply_row["source"], status=1, tagname=f"{plantno}_{item}",
        ))
        db.add(VocTranlog(
            empno=current_user_empno, logtype="I", databefore="",
            dataafter=f"{plantno}/{item}/{apply_row['LAW']}/{apply_row['OOS']}/{apply_row['OOC']}/{apply_row['alert']}/{apply_row['source']}",
            cdatetime=datetime.now(), remark=apply_row["remark"] or "",
        ))

    elif ftype == "M":
        spec = db.query(VocSpec).filter_by(plantno=plantno, item=item).first()
        if not spec:
            raise ValueError(f"找不到規格值資料可修改: {plantno}/{item}")
        old_log_str = f"{spec.plantno}/{spec.item}/{spec.LAW}/{spec.OOS}/{spec.OOC}/{spec.alert}/{spec.source}"
        spec.LAW = apply_row["LAW"]
        spec.OOS = apply_row["OOS"]
        spec.OOC = apply_row["OOC"]
        spec.alert = apply_row["alert"]
        spec.source = apply_row["source"]
        spec.tagname = f"{plantno}_{item}"
        db.add(VocTranlog(
            empno=current_user_empno, logtype="M", databefore=old_log_str,
            dataafter=f"{plantno}/{item}/{apply_row['LAW']}/{apply_row['OOS']}/{apply_row['OOC']}/{apply_row['alert']}/{apply_row['source']}",
            cdatetime=datetime.now(), remark=apply_row["remark"] or "",
        ))
        _sync_scada_web_if_qa(db, plantno, item, apply_row["source"], apply_row["OOS"], apply_row["OOC"], apply_row["alert"])

    elif ftype == "D":
        spec = db.query(VocSpec).filter_by(plantno=plantno, item=item).first()
        if not spec:
            raise ValueError(f"找不到規格值資料可刪除: {plantno}/{item}")
        old_log_str = f"{spec.plantno}/{spec.item}/{spec.LAW}/{spec.OOS}/{spec.OOC}/{spec.alert}/{spec.source}"
        db.delete(spec)
        db.add(VocTranlog(
            empno=current_user_empno, logtype="D", databefore=old_log_str, dataafter="",
            cdatetime=datetime.now(), remark=apply_row["remark"] or "",
        ))

    else:
        raise ValueError(f"未知的 ftype: {ftype}")


def process_spec_sign(db: Session, action: SpecSignAction, current_user_empno: str, current_user_name: str) -> bool:
    """
    對應 legacy SignSPEC.aspx.cs btn簽核_Click() + dbVOC.ProcSignSPEC()。
    與隔離簽核（flow_service.process_sign）相同的「一階群組簽核」OR 邏輯：任一位 SignGrp=1
    簽核人核准/否決，流程立即結案。核准時套用申請內容回 VOC_SPEC（apply_spec_from_form），
    否決則只改狀態，不動 VOC_SPEC。
    """
    try:
        empid = _get_emp_id(db, current_user_empno)

        result = db.execute(
            text(
                "UPDATE [SignFlow].[dbo].[base_flowd] "
                "SET signempid=:empid, signempname=:empname, signtime=:signtime, "
                "signactionid=:actionid, signmemo=:comment "
                "WHERE flowid=:flowid AND fstep=1 AND empid=:empid"
            ),
            {
                "empid": empid,
                "empname": current_user_name,
                "signtime": datetime.now(),
                "actionid": action.actionid,
                "comment": action.comment or "",
                "flowid": action.flowid,
            },
        )
        if result.rowcount == 0:
            raise ValueError("您不具備簽核資格，或此關卡已完成簽核")

        new_status = resolve_new_status(action.actionid)

        db.execute(
            text(
                "UPDATE [SignFlow].[dbo].[base_flow] "
                "SET fetime=:fetime, actstep=NULL, fstatusid=:fstatusid WHERE flowid=:flowid"
            ),
            {"fetime": datetime.now(), "fstatusid": int(new_status), "flowid": action.flowid},
        )

        db.execute(
            text("UPDATE [VOC].[dbo].[VOC_SPEC_apply] SET fstatusid=:fstatusid WHERE formid=:formid"),
            {"fstatusid": int(new_status), "formid": action.formid},
        )

        if new_status == FlowStatus.核准:
            apply_spec_from_form(db, action.formid, current_user_empno)

        db.add(VocTranlog(
            empno=current_user_empno,
            logtype="U",
            databefore=f"formid={action.formid}",
            dataafter=f"規格簽核動作: {'核准' if new_status == FlowStatus.核准 else '否決'} / 意見: {action.comment}",
            cdatetime=datetime.now(),
            remark="",
        ))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e


# ── 查詢：我的規格申請單 / 待簽核 ────────────────────────────────────────────

def _spec_apply_row_to_response(row) -> SpecApplyListResponse:
    return SpecApplyListResponse(
        formid=row["formid"], formno=row["formno"], flowid=row["flowid"],
        ftype=row["ftype"], ftype_label=ftype_label(row["ftype"]),
        plantno=row["plantno"], item=to_display_item(row["item"]),
        LAW=row["LAW"], OOS=row["OOS"], OOC=row["OOC"], alert=row["alert"],
        source=row["source"], empstr=row["empstr"], cdatetime=row["cdatetime"], fstatus=row["fstatus"],
    )


def list_spec_applies(
    db: Session, cempno: str, sdate: str = "", edate: str = "",
    plantno: str = "", statusid: int = -1, formid: int = -1,
) -> List[SpecApplyListResponse]:
    """
    移植舊版「規格申請單」查詢（ApplySPEC 頁）。legacy ApplySPEC.aspx.cs 實際呼叫的是
    `db.List廠區的申請單()`（隔離申請單專用的方法，查 VOC_closectl），把 formid 誤當 ccid 傳入，
    查錯資料表——這是 legacy 另一處死碼跡象。這裡改成正確查詢 VOC_SPEC_apply，語意比照
    control_service.get_my_applies()：statusid=-1 時排除否決(8)，並用 sys_acluserrole 廠區
    ACL 做「額外納入」過濾（不排除自己的申請）。
    """
    sql_base = """
        Select M.formid, M.formno, M.flowid, M.ftype, M.plantno, M.item,
               M.LAW, M.OOS, M.OOC, M.alert, S.source,
               E.empno+'-'+E.empname as empstr, M.cdatetime, FS.fstatus
        From [VOC].[dbo].[VOC_SPEC_apply] M
        Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid
        Join [SignFlow].[dbo].[base_emp] E On M.empno=E.empno
        Left Join [VOC].[dbo].[VOC_source] S On M.source=S.sourceid
        Where 1=1
    """
    params = {}
    if sdate:
        sql_base += " And convert(varchar(10),M.cdatetime,111) >= :sdate"
        params['sdate'] = sdate
    if edate:
        sql_base += " And convert(varchar(10),M.cdatetime,111) <= :edate"
        params['edate'] = edate
    if plantno:
        sql_base += " And M.plantno = :plantno"
        params['plantno'] = plantno
    if statusid != -1:
        sql_base += " And M.fstatusid = :statusid"
        params['statusid'] = statusid
    else:
        sql_base += " And M.fstatusid != :rejected_status"
        params['rejected_status'] = int(FlowStatus.否決)

    if formid == -1:
        sql_base += """
            And (
                M.empno = :cempno
                Or Exists (
                    Select 1 From [VOC].[dbo].[sys_acluserrole] R
                    Where R.empno = :cempno And (R.plantno = 'ALL' Or R.plantno = M.plantno)
                )
            )
        """
        params['cempno'] = cempno
    else:
        sql_base += " And M.formid = :formid"
        params['formid'] = formid

    sql_base += " Order by M.cdatetime desc"

    try:
        rows = db.execute(text(sql_base), params).mappings().all()
    except Exception as e:
        logger.error(f"[list_spec_applies] DB 查詢失敗 cempno={cempno}: {e}")
        raise

    return [_spec_apply_row_to_response(row) for row in rows]


def list_spec_todos(db: Session, empno: str, sdate: str = "", edate: str = "", formid: int = -1) -> List[SpecApplyListResponse]:
    """
    移植舊版 dbVOC.List我的待辦事項1()（SignSPEC 待簽核清單）：查目前 fstep=actstep
    的簽核人清單中含自己的規格申請單。
    """
    sql_base = """
        Select M.formid, M.formno, M.flowid, M.ftype, M.plantno, M.item,
               M.LAW, M.OOS, M.OOC, M.alert, S.source,
               AE.empno+'-'+AE.empname as empstr, M.cdatetime, FS.fstatus
        From [VOC].[dbo].[VOC_SPEC_apply] M
        Join [SignFlow].[dbo].[base_flowstatus] FS On M.fstatusid=FS.fstatusid
        Join [SignFlow].[dbo].[base_flow] BF On M.flowid=BF.flowid
        Join [SignFlow].[dbo].[base_flowd] BFD On BF.flowid=BFD.flowid And BF.actstep=BFD.fstep
        Join [SignFlow].[dbo].[base_emp] SE On BFD.empid=SE.empid
        Join [SignFlow].[dbo].[base_emp] AE On M.empno=AE.empno
        Left Join [VOC].[dbo].[VOC_source] S On M.source=S.sourceid
        Where SE.empno = :empno
    """
    params = {"empno": empno}
    if sdate:
        sql_base += " And convert(varchar(10),M.cdatetime,111) >= :sdate"
        params['sdate'] = sdate
    if edate:
        sql_base += " And convert(varchar(10),M.cdatetime,111) <= :edate"
        params['edate'] = edate
    if formid > 0:
        sql_base += " And M.formid = :formid"
        params['formid'] = formid

    sql_base += " Order by M.cdatetime desc"

    try:
        rows = db.execute(text(sql_base), params).mappings().all()
    except Exception as e:
        logger.error(f"[list_spec_todos] DB 查詢失敗 empno={empno}: {e}")
        raise

    return [_spec_apply_row_to_response(row) for row in rows]
