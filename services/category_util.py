"""
category_util.py — 項目類型（水質／空汙／雨水溝）判斷的單一真相來源

背景（docs/標準化與待調整清單.md D7）：
  舊系統與本專案第一階段移植，判斷一個監測項目屬於「水質／空汙／雨水溝」哪一類，
  全靠**項目名稱字串比對**（`"VOC" in item`、`"雨水溝" in item`）。這很脆弱：
  新廠若有不叫 VOC 的空汙項目，會被誤判成水質，連帶找錯簽核人、派報信分錯類。

  2026-07-31 已新增 `models_b.Item.category` 欄位（水質／空汙／雨水溝），由基礎資料建置
  （scripts/load_user_data.py）填入正確值。本模組是「讀取端」改用該欄位的共用純函式。

★ A 棧保護原則（比照 D8 `Item.is_dual_bound` 與 C1 `check_lower_bound` 的做法）：
  所有判斷函式的 `category` 參數一律 **optional，預設 None**；為 None（或值不在三種
  合法類型內，例如舊資料尚未回填）時，**完全退回原本的名稱字串比對，一個字元都不變**。
  A 棧（main.py，公司平行測試中）的呼叫端一律不傳 category，行為逐位元不變；
  只有 B 棧呼叫端會從 `item.category` 取值傳入，才改用資料驅動判斷。

本模組是純函式，不 import 任何 DB／模型，兩棧共用。
"""

from typing import Optional

# item.category 的三種合法值（與 scripts/load_user_data.py ITEM_TYPES 一致）
CATEGORY_WATER = "水質"
CATEGORY_AIR = "空汙"
CATEGORY_RAINGUTTER = "雨水溝"

VALID_CATEGORIES = (CATEGORY_WATER, CATEGORY_AIR, CATEGORY_RAINGUTTER)

# 舊的水質項目名稱關鍵字（category 未回填時的 fallback，見 is_water_item()）。
# 沿用 services/dispatch_service.py 原本寫死的那串，順序與內容一字不改。
_WATER_NAME_KEYS = ("pH", "Cu", "Ni", "SS", "COD")


def _is_known(category: Optional[str]) -> bool:
    """category 是否為可信任的合法值；None／空字串／未知字串一律不可信（退回名稱比對）。"""
    return category in VALID_CATEGORIES


def is_air_item(item: str, category: Optional[str] = None) -> bool:
    """
    是否為「空汙」項目（舊語意：派報代碼前綴 '空'、簽核 rtype '空保養中'、
    燈號的 VOC 例外——SCADA 比 SPEC 嚴時不算管制值不一致）。

    - category 為合法值 → 直接以 category 判定（'空汙' 才是空汙，水質/雨水溝皆非）。
    - category 為 None／未回填／未知值 → 退回舊行為 `"VOC" in item`。
    """
    if _is_known(category):
        return category == CATEGORY_AIR
    return "VOC" in (item or "")


def is_water_item(item: str, category: Optional[str] = None) -> bool:
    """
    是否為「水質」項目。

    - category 為合法值 → 直接以 category 判定（'水質' 才是，空汙/雨水溝皆非）。
    - category 為 None／未回填／未知值 → 退回舊行為：比對名稱是否含五個水質關鍵字。

    ⚠️ 這個判斷會決定 `dispatch_service.evaluate_row()` 的 `can_escalate`——
    也就是 OOC/OOS 超標時**到底要不要產生派報代碼**。舊的關鍵字比對只認得
    pH/Cu/Ni/SS/COD 五個名字，因此像「氨氮」這種名稱不在清單內的水質項目，
    讀值超過 OOS 亮紅燈時 `codes` 會是空的、**完全不發異常派報信**（2026-08-01
    主控驗收 D7 時實測確認）。這是比「分錯類」更嚴重的漏報，故一併改為資料驅動。
    """
    if _is_known(category):
        return category == CATEGORY_WATER
    return any(k in (item or "") for k in _WATER_NAME_KEYS)


def is_raingutter_item(item: str, category: Optional[str] = None) -> bool:
    """
    是否為「雨水溝」項目。

    - category 為合法值 → 直接以 category 判定。
    - category 為 None／未回填／未知值 → 退回舊行為 `"雨水溝" in item`。
    """
    if _is_known(category):
        return category == CATEGORY_RAINGUTTER
    return "雨水溝" in (item or "")
