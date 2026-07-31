from pydantic import BaseModel, model_validator
from typing import Optional, List
from datetime import datetime
import re


# ── 純函式：欄位格式驗證（可獨立單測，不依賴 Pydantic）──────────────────────
# 對應 legacy/EditSPEC.aspx.cs 的 __LAW_TextChanged / __OOS_TextChanged /
# __OOC_TextChanged / __alert_TextChanged 四支事件（欄位格式邏輯完全相同，只是欄位名稱不同）。

def parse_spec_bound(val: str, field_name: str, is_dual: bool, item_name: str) -> Optional[List[float]]:
    """
    解析單一規格欄位字串（如 '6-9' 雙邊 或 '80' 單邊），回傳 [值] 或 [下限, 上限]。
    空字串或 'N/A' 視為未設定，回傳 None（對應 legacy 的 `!= "" && != "N/A"` 才檢查）。

    對應 legacy 逐字元檢查：
      - 雙邊項目必須雙邊（Split('-').Length==1 即錯）；單邊項目必須單邊（Length==2 即錯）。
      - 每一段只能是數字，小數點後最多 2 位。
      - 雙邊時下限不可大於等於上限。

    ★ 參數原名 `is_ph`，2026-07-31 更名為 `is_dual`：語意本來就是「這個項目是不是雙邊規格」，
      而雙邊規格**不只 pH**——K21 溫度（'20-35'）同樣是雙邊（見 services/dashboard_service.py
      的燈號規則註解）。叫 is_ph 讓呼叫端誤以為「只有 pH 需要雙邊」，正是溫度規格一直建不
      起來的根因之一。此為純粹更名，判斷邏輯完全未動。
    """
    if not val or val == "N/A":
        return None

    val = val.strip()
    parts = val.split('-')

    if is_dual and len(parts) == 1:
        # 訊息把原本寫死的 "pH" 換成 {item_name}，與下面「必須為單邊規格」那句對稱
        # （原文寫死 pH，套到 K21 溫度上會變成「溫度的 OOS 錯誤，pH 必須為雙邊規格」的胡話）。
        # ★ A 棧行為不變：A 棧走到 is_dual=True 幾乎必然是 item=='pH'（前端下拉送的是顯示名，
        #   見 guess_dual_bound_by_name()），代入後字串與改版前逐字元相同；
        #   唯一差異是呼叫端直接傳存檔別名 'pH1' 的邊緣情況，訊息會顯示 pH1（更正確）。
        raise ValueError(f"{field_name} 值錯誤, {item_name} 必須為雙邊規格 (如: 6-9)!")
    if not is_dual and len(parts) == 2:
        raise ValueError(f"{field_name} 值錯誤, {item_name} 必須為單邊規格 (如: 6)!")

    for part in parts:
        if not re.match(r'^\d+(\.\d{1,2})?$', part):
            raise ValueError(f"{field_name} 值({part})錯誤, 請確保皆為數字且最多包含兩位小數!")

    if len(parts) == 2 and float(parts[0]) >= float(parts[1]):
        raise ValueError(f"{field_name} 格式錯誤: 下限規格不能大於或等於上限規格!")

    return [float(p) for p in parts]


def check_ooc_alert_hierarchy(ooc_vals: Optional[List[float]], alert_vals: Optional[List[float]],
                              is_dual: bool, item_name: Optional[str] = None) -> None:
    """
    OOC 與 Alert 的層遞防呆（**2026-07-31 經使用者向環工部確認後定案**）。

    業務規則（已確認）：
      門檻由窄到寬為 Alert（黃燈）→ OOC（橙燈）→ OOS（紅燈），
      **Alert 的觸發範圍必須包含在 OOC 之內**（Alert ⊆ OOC），亦即 Alert 最先觸發。

    ★ 允許「貼齊」（Alert == OOC）：
      Alert 與 OOC 的實際數值**因廠區而異**——有些廠區的內控標準會把 Alert 設得跟 OOC
      完全相同（不留緩衝，直接橙燈），有些廠區則會留一段間距先亮黃燈。兩種都是合法設定，
      因此本函式採「大於等於／小於等於」而非嚴格不等式。
      （讀值同時碰到 Alert 與 OOC 時以 OOC 的橙燈優先，該行為由
      `services/dashboard_service._calculate_light()` 保證，並由
      `tests/test_light_ooc_priority.py` 鎖住，這裡不重複實作。）

    ★ 仍然擋下「反轉」（OOC 比 Alert 窄）：
      這不是保守而是資料錯誤——`_calculate_light()` 的 Alert 分支條件是
      `alert < rvalue < ooc`，一旦 OOC 比 Alert 窄，該區間就是空集合，
      **Alert 這層門檻永遠不會觸發**，等於使用者填了一個永遠無效的值，必須擋在輸入端。

    本版取代 2026-07-31 之前的嚴格版本（當時的 docstring 記載「legacy 這段是死碼、
    方向研判為 bug、待業務確認」——該疑慮已由使用者確認結案：方向正確、且應放寬到允許相等）。
    對應 legacy __OOC_TextChanged / __alert_TextChanged 的交叉比對區塊。

    ★ 參數原名 `is_ph`，2026-07-31 更名為 `is_dual`（理由同 parse_spec_bound()：雙邊規格
      不只 pH，K21 溫度也是）。純更名，判斷邏輯完全未動。

    ★ `item_name`（選填）只影響錯誤訊息的措辭，不影響任何判斷：
      有帶就顯示實際項目名（K21 溫度會看到「對於 溫度 雙邊規格：…」），沒帶則沿用原本寫死的
      「pH」字樣。**預設 None 是為了讓 A 棧（main.py，公司平行測試中）的訊息逐字元不變**——
      A 棧呼叫端不傳這個參數。不加這個參數的話，溫度項目會收到「對於 pH 雙邊規格：…」的胡話。
    """
    if not (ooc_vals and alert_vals):
        return
    if is_dual:
        if ooc_vals[0] > alert_vals[0] or ooc_vals[1] < alert_vals[1]:
            raise ValueError(
                f"對於 {item_name or 'pH'} 雙邊規格：OOC 範圍不可比 Alert 範圍窄（OOC 下限不可高於 Alert 下限、"
                "OOC 上限不可低於 Alert 上限；可相等）！"
            )
    else:
        if ooc_vals[0] < alert_vals[0]:
            raise ValueError("單邊規格中，OOC 上限值不可小於 Alert（可相等）！")


def guess_dual_bound_by_name(item: str) -> bool:
    """
    ⚠️ 過渡性推測：只靠**項目名稱**猜這個項目是不是雙邊規格。

    這不是正解，正解是呼叫端把 `is_dual_bound` 明確帶進來（B 棧由 `models_b.Item.is_dual_bound`
    資料驅動決定，見該欄位 comment）。本函式只在「呼叫端沒有指定」時當 fallback 用。

    為什麼推測一定不夠：雙邊規格**不只 pH**——K21 溫度（'20-35'）同樣是雙邊
    （見 `services/dashboard_service.py` 燈號規則），但名稱裡完全沒有 pH 字樣，
    任何名稱比對都猜不到；而 pH2 這種別名也曾因為兩處實作正則寬窄不一致，
    造成「載得進去卻改不動」。

    ★ 本函式的判斷式**刻意凍結**成 A 棧（`main.py`，公司平行測試中）原本第 97 行的寫法，
      一個字元都不改：legacy 嚴格比對下拉選單顯示文字 `_0item.SelectedItem.Text == "pH"`
      （該下拉只顯示通用項目名稱，不會顯示 pH1 這種內部存檔別名），這裡多容忍 item=='pH1'
      一種情況，是因為呼叫端可能直接傳入已轉換過的存檔別名，屬於比 legacy 更寬鬆的防呆。
      ⚠️ 請**不要**為了「與 scripts/load_user_data.py 的 `^ph\\d*$` 統一」而把這裡放寬——
      那會改變 A 棧對 pH2 的既有行為。兩棧 fallback 暫時不同是刻意的：
      B 棧靠資料（fallback 只是過渡），A 棧凍結。
    """
    return (item.lower() == 'ph' or item == 'pH1')


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
    # 規格型態：True=雙邊（'6-9'）／False=單邊（'80'）／None=未指定→退回名稱推測。
    # B 棧 router 會先查 `models_b.Item.is_dual_bound` 再帶進來（見 routers_b/spec_router_b.py）；
    # A 棧前端不送這個欄位，一律走 None → guess_dual_bound_by_name()，行為與改版前完全相同。
    is_dual_bound: Optional[bool] = None

    def effective_dual_bound(self) -> bool:
        """實際採用的雙邊判定：有明確指定就用指定值，沒指定才退回名稱推測。"""
        if self.is_dual_bound is not None:
            return self.is_dual_bound
        return guess_dual_bound_by_name(self.item)

    @model_validator(mode='after')
    def validate_limits(self) -> 'SpecBase':
        """ 移植 legacy EditSPEC.aspx.cs 的欄位格式 + 層遞防呆邏輯（見上方純函式）。 """
        is_dual = self.effective_dual_bound()

        law_vals = parse_spec_bound(self.LAW, "LAW", is_dual, self.item)
        oos_vals = parse_spec_bound(self.OOS, "OOS", is_dual, self.item)
        ooc_vals = parse_spec_bound(self.OOC, "OOC", is_dual, self.item)
        alert_vals = parse_spec_bound(self.alert, "Alert", is_dual, self.item)

        # 帶 item 進去只影響訊息措辭（溫度不會再看到「對於 pH 雙邊規格」）。
        # A 棧走到 is_dual=True 時 item 幾乎必然是 'pH'，代入後訊息與改版前逐字元相同。
        check_ooc_alert_hierarchy(ooc_vals, alert_vals, is_dual, self.item)

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
