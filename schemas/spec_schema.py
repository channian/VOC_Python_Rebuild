from pydantic import BaseModel, model_validator
from typing import Optional, List
from datetime import datetime
import re


# ── 純函式：欄位格式驗證（可獨立單測，不依賴 Pydantic）──────────────────────
# 對應 legacy/EditSPEC.aspx.cs 的 __LAW_TextChanged / __OOS_TextChanged /
# __OOC_TextChanged / __alert_TextChanged 四支事件（欄位格式邏輯完全相同，只是欄位名稱不同）。

def parse_spec_bound(val: str, field_name: str, is_ph: bool, item_name: str) -> Optional[List[float]]:
    """
    解析單一規格欄位字串（如 '6-9' 雙邊 或 '80' 單邊），回傳 [值] 或 [下限, 上限]。
    空字串或 'N/A' 視為未設定，回傳 None（對應 legacy 的 `!= "" && != "N/A"` 才檢查）。

    對應 legacy 逐字元檢查：
      - pH 必須雙邊（Split('-').Length==1 即錯）；非 pH 必須單邊（Length==2 即錯）。
      - 每一段只能是數字，小數點後最多 2 位。
      - 雙邊時下限不可大於等於上限。
    """
    if not val or val == "N/A":
        return None

    val = val.strip()
    parts = val.split('-')

    if is_ph and len(parts) == 1:
        raise ValueError(f"{field_name} 值錯誤, pH 必須為雙邊規格 (如: 6-9)!")
    if not is_ph and len(parts) == 2:
        raise ValueError(f"{field_name} 值錯誤, {item_name} 必須為單邊規格 (如: 6)!")

    for part in parts:
        if not re.match(r'^\d+(\.\d{1,2})?$', part):
            raise ValueError(f"{field_name} 值({part})錯誤, 請確保皆為數字且最多包含兩位小數!")

    if len(parts) == 2 and float(parts[0]) >= float(parts[1]):
        raise ValueError(f"{field_name} 格式錯誤: 下限規格不能大於或等於上限規格!")

    return [float(p) for p in parts]


def check_ooc_alert_hierarchy(ooc_vals: Optional[List[float]], alert_vals: Optional[List[float]], is_ph: bool) -> None:
    """
    OOC 與 Alert 的層遞防呆：OOC 必須比 Alert 寬鬆（更容易觸發）。
    對應 legacy __OOC_TextChanged / __alert_TextChanged 的交叉比對區塊，兩處邏輯彼此對稱一致。

    ⚠️ 與 legacy 原始碼的刻意差異（僅雙邊 / pH 情境）：
    legacy 原始碼要求 `OOC[0] > Alert[0]`（下限），但這與「OOC 應比 Alert 寬」的一般認知相反
    （直覺應該是 OOC 下限 < Alert 下限，OOC 在低端更極端才對；legacy 對上限的方向 `OOC[1] > Alert[1]`
    倒是符合直覺）。這段 pH 雙邊送簽驗證在 legacy 從未真正上線過──EditSPEC.aspx.cs 三個按鈕呼叫
    SPEC送簽() 的程式碼整段被註解掉（見 legacy/EditSPEC.aspx.cs InsertButton_Click 等），
    SPEC送簽() 本身的 INSERT 語法也有漏逗號的錯誤（見 legacy/dbVOC.cs:2474），
    ProcSignSPEC() 核准套用時甚至會對新增案例丟例外──種種跡象顯示這整條路徑是從未執行過的死碼，
    研判 legacy 這段方向判斷本身就是 bug。這裡採用「OOC 範圍需比 Alert 範圍更寬」的直覺方向
    （下限更低、上限更高）做驗證，待業務確認正確方向後再調整。
    """
    if not (ooc_vals and alert_vals):
        return
    if is_ph:
        if ooc_vals[0] >= alert_vals[0] or ooc_vals[1] <= alert_vals[1]:
            raise ValueError(
                "對於 pH 雙邊規格：OOC 範圍必須比 Alert 範圍更寬（OOC 下限需小於 Alert 下限、"
                "OOC 上限需大於 Alert 上限）！"
            )
    else:
        if ooc_vals[0] <= alert_vals[0]:
            raise ValueError("單邊規格中，OOC 上限值必須大於 Alert！")


class SpecBase(BaseModel):
    """ 提供 EditSPEC 建立或更新時的通用資料模型 """
    plantno: str
    item: str
    LAW: str
    OOS: str
    OOC: str
    alert: str
    source_id: int
    remark: Optional[str] = ""

    @model_validator(mode='after')
    def validate_limits(self) -> 'SpecBase':
        """ 移植 legacy EditSPEC.aspx.cs 的欄位格式 + 層遞防呆邏輯（見上方純函式）。 """
        # is_ph 判斷：legacy 嚴格比對下拉選單顯示文字 `_0item.SelectedItem.Text == "pH"`（該下拉
        # 只顯示通用項目名稱，不會顯示 pH1 這種內部存檔別名）。這裡多容忍 item=='pH1' 一種情況，
        # 是因為呼叫端可能直接傳入已轉換過的存檔別名，屬於比 legacy 更寬鬆的防呆，不影響正常流程。
        is_ph = (self.item.lower() == 'ph' or self.item == 'pH1')

        law_vals = parse_spec_bound(self.LAW, "LAW", is_ph, self.item)
        oos_vals = parse_spec_bound(self.OOS, "OOS", is_ph, self.item)
        ooc_vals = parse_spec_bound(self.OOC, "OOC", is_ph, self.item)
        alert_vals = parse_spec_bound(self.alert, "Alert", is_ph, self.item)

        check_ooc_alert_hierarchy(ooc_vals, alert_vals, is_ph)

        return self


class SpecCreate(SpecBase):
    pass


class SpecUpdate(SpecBase):
    pass


class SpecResponse(BaseModel):
    plantno: str
    item: str
    LAW: str
    OOS: str
    OOC: str
    alert: str
    source: str    # 來源顯示名稱
    sourceid: Optional[int] = None
    tagname: Optional[str] = None

    class Config:
        from_attributes = True


# ── 規格簽核申請（VOC_SPEC_apply，落差清單 #5）───────────────────────────────

class SpecApplyCreate(SpecBase):
    """
    規格送簽申請（EditSPEC「送簽」版本，對應 legacy dbVOC.SPEC送簽(hrow, ftype)）。
    item 一律填「顯示用」項目名稱（如 "pH"、"COD"），plantno/item 別名對應（pH1/COD2）
    由 services/spec_service.py 的 to_storage_item() 處理，不在這裡做。
    """
    ftype: str  # 'I'=新增 / 'M'=修改 / 'D'=刪除

    @model_validator(mode='after')
    def validate_ftype(self) -> 'SpecApplyCreate':
        if self.ftype not in ('I', 'M', 'D'):
            raise ValueError("ftype 必須為 I(新增)/M(修改)/D(刪除)")
        return self


class SpecApplyListResponse(BaseModel):
    """ ApplySPEC（我的規格申請單）/ SignSPEC（待簽核）共用的列表列結構 """
    formid: int
    formno: str
    flowid: Optional[int] = None
    ftype: str          # 原始碼 I/M/D
    ftype_label: str    # 新增/修改/刪除
    plantno: str
    item: str            # 顯示用項目名稱（已轉換 pH1->pH、COD2->COD）
    LAW: Optional[str] = None
    OOS: Optional[str] = None
    OOC: Optional[str] = None
    alert: Optional[str] = None
    source: Optional[str] = None   # 來源顯示名稱
    empstr: str                     # 申請人 empno-empname
    cdatetime: datetime
    fstatus: str

    class Config:
        from_attributes = True


class SpecSignAction(BaseModel):
    """ SignSPEC 簽核動作。actionid：1=核准, 9=否決（見 services/flow_service.py） """
    formid: int
    flowid: int
    actionid: int
    comment: Optional[str] = ""
