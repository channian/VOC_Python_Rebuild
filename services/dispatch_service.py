"""
dispatch_service.py — 異常 Email 派報（移植舊版 Job.dbVOC.GetDataRed + Job.SendMail.SendMail_廠務法規許可值標準化管控報表）

依 docs/legacy_source_analysis.md「JOB 派報流程完整還原」「GetDataRed 完整還原」兩節逐行還原。

核心設計：
  evaluate_row()  是 GetDataRed 的純函式版本，輸入一列「廠區+項目」的即時資料與「前一筆派報紀錄」，
  回傳 DispatchResult（是否要派報、燈號、msg/msg1/msg2、首發或再發）。不依賴 DB，可完全用純邏輯測試。

  run_dispatch(db) 是外層流程（對應 SendMail_廠務法規許可值標準化管控報表 主體），
  負責撈資料、逐列呼叫 evaluate_row、依廠區分組寄信、寫 VOC_MAIL_Log。

與舊系統刻意不同之處（皆有明確理由，詳見各函式註解）：
  1. mailto 為空時 continue（記 log）而非 return，避免中止整個派報迴圈（舊系統隱藏 bug）。
  2. 不把計算出的 light 寫回 DB（省略 UpdateData 動作）——燈號一律即時重算、不落地存值。
  3. 不做 SMS（SendSMS）、不做 PushPlus 推播（已與使用者確認不移植）。
  4. 舊版硬寫死的 BCC（Ray/Albee）與內網圖片 UNC 路徑不搬過來；燈號改用彩色圓點 inline style。
  5. 「隔離區間」文字（Get隔離廠區項目區間，如「從 08:00 到 12:00」）不納入信件內文——
     這是舊系統顯示保養中期間起訖時間的附加說明，非派報邏輯核心，且需要逐列額外查詢，
     暫不實作，待業務確認是否必要。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.category_util import is_air_item, is_raingutter_item, is_water_item
from services.dashboard_service import _parse_bounds, _safe_float
from services.maillist_service import get_mail_recipients
from services.notify_service import send_email_sync

logger = logging.getLogger(__name__)

# ── 常數（對應 Job_dbVOC.cs GetDataRed）───────────────────────────────────
ArrOOCS = ["", "15", "30"]  # OOC/OOS escalation 的三個時間點後綴
_SKIP_MARKERS = {"", "-", "N/A", "建置中", "異常"}   # 管制值尚未建置/無效 → 不比對
_SPECIAL_MARKERS = {"斷訊", "保養中"}                # 管制值顯示狀態文字 → 特例訊息

# 簽核狀態「核准」的真實值（見 docs/legacy_source_analysis.md「簽核狀態值」節，MTFlowBase.FlowStatus.核准=7）
FSTATUSID_APPROVED = 7


@dataclass
class DispatchResult:
    """GetDataRed 單列（單一廠區+項目）的判斷結果。"""
    codes: list[str] = field(default_factory=list)   # 派報代碼（sRed），如 ['水Alert-K7']
    msg: str = ""     # 人類可讀訊息，存 VOC_MAIL_Log.msg
    msg1: str = ""    # |item|：條件 比對鍵，存 VOC_MAIL_Log.msg1
    msg2: str = ""    # msg1 排除「(保養中)」後的子集合，存 VOC_MAIL_Log.msg2
    light: str = "G"  # 'R'/'O'/'Y'/'G'（本函式不產生 '-'，斷訊/保養中若無其他條件觸發則維持綠燈，詳見模組說明）
    is_first: bool = False  # True=首發, False=再發（僅在 codes 非空時才有意義）


# ── 數字格式化（對應 dbVOC.ChangeData：一般 2 位小數，導電度/日累積水量 0 位小數）────────

def _decimals_for(item: str) -> int:
    return 0 if ("導電度" in item or "日累積水量" in item) else 2


def _fmt(v: float, item: str) -> str:
    return f"{v:.{_decimals_for(item)}f}"


def _fmt_bound(bounds: tuple[float, float], item: str) -> str:
    lo, hi = bounds
    if lo == hi:
        return _fmt(lo, item)
    return f"{_fmt(lo, item)}-{_fmt(hi, item)}"


# ── SCADA/CWMS 管制值狀態判斷（'-'/'N/A' 等無效值跳過；'斷訊'/'保養中' 是特例訊息；其餘視為數值）──

def _scada_status(raw) -> tuple[str, object]:
    """回傳 ('skip', None) / ('special', '斷訊'|'保養中') / ('value', (lo, hi))。"""
    s = str(raw if raw is not None else "").strip()
    if s in _SKIP_MARKERS:
        return ("skip", None)
    if s in _SPECIAL_MARKERS:
        return ("special", s)
    bounds = _parse_bounds(s)
    if bounds is None:
        return ("skip", None)
    return ("value", bounds)


# ── evaluate_row：GetDataRed 純函式版本 ───────────────────────────────────

def evaluate_row(row: dict, prev_mail: dict | None, now: datetime,
                 category: str | None = None) -> DispatchResult:
    """
    對應 Job.dbVOC.GetDataRed(DataRow row, DateTime dt2)。

    row 欄位（對應 GetData() 撈出、經 SendMail 清理過的單列資料，命名比照 dashboard_service 慣例）：
        plantno, item, rvalue_raw, rvalue（N.D/<0.05 等已轉 '0' 的乾淨數字字串）, broken(int),
        oos, ooc, alert_spec, recv（SPEC 側門檻，字串，pH/溫度雙邊為 'lo-hi'）,
        scada_oos, scada_ooc, scada_alert（SCADA 管制值，可能是 '斷訊'/'保養中'/'-'/數字）,
        cwms_oos, cwms_ooc（CWMS 管制值，同上）

    prev_mail：Get前筆派報資料(plantno, item) 的結果，
        {'cdatetime': datetime, 'msg1': str} 或 None（查無記錄）。

    category（2026-08-01 D7 新增，比照 _calculate_light 的 check_lower_bound 保護模式）：
        項目類型（'水質'/'空汙'/'雨水溝'，來源 models_b.Item.category），決定
        ① 派報代碼前綴 sType（'空'/'水'）② VOC 例外（SCADA 比 SPEC 嚴不算不一致）。
        **預設 None → 完全退回原本的 `"VOC" in item` 名稱字串比對**，A 棧（run_dispatch）
        不傳此參數，行為一個字元都不變；B 棧（run_dispatch_b）傳入 item.category 真實值，
        NULL 時傳 None 一樣退回名稱比對。

    回傳 DispatchResult。若 codes 為空代表這筆不用派報（無異常，或雖有異常但被
    4 小時/15 分鐘節流閘擋下——見函式最後一段）。

    設計簡化說明（相較舊版 C#，行為對業務結果無影響）：
      - 舊版依「一般項目」vs「pH/溫度雙邊規格項目」拆成兩個結構相同的分支（因為 C# 的
        ToDecimal 無法直接處理 'lo-hi' 字串，需要 Split 陣列另外判斷）。Python 用
        dashboard_service._parse_bounds 已經統一處理單邊/雙邊並取上界比對，因此這裡合併成
        單一路徑，數學上與舊版兩分支逐條件比對完全等價。
      - 舊版另外依「SCADA 三個門檻是否全部顯示為 -/N/A/建置中/異常」拆出一個「純 CWMS 來源」
        分支（跳過 SCADA 相關比對）。這裡改用「每個 mismatch 條件各自對無效值直接跳過比對」
        的方式達到同樣效果（SCADA 全部無效時，SCADA 相關 mismatch 自然不會觸發），
        因此不需要另外拆分支。
    """
    plantno = str(row.get("plantno", ""))
    item = str(row.get("item", ""))
    # category=None（A 棧）→ is_air_item() 內部退回舊的 `"VOC" in item` 字串比對
    is_voc = is_air_item(item, category)
    sType = "空" if is_voc else "水"
    # 同理改為資料驅動：category=None（A 棧）→ 退回舊的五個關鍵字比對，行為不變。
    # ⚠️ 2026-08-01 主控驗收 D7 時實測發現：舊的關鍵字比對只認得 pH/Cu/Ni/SS/COD，
    #    像「氨氮」這種水質項目讀值超過 OOS 亮紅燈時 can_escalate 會是 False、
    #    codes 空的、**完全不發異常派報信**。空汙側已由 is_air_item 修好，水質側
    #    若不一起改就只修一半，而水質項目才是絕大多數。
    is_water = is_water_item(item, category)
    can_escalate = is_water or is_voc  # OOC/OOS escalation 只有水質相關 + VOC 項目才會產生代碼

    rvalue_raw = str(row.get("rvalue_raw", "") or "")
    rvalue = _safe_float(row.get("rvalue"))
    broken = int(row.get("broken") or 0)

    oos_b = _parse_bounds(row.get("oos"))
    ooc_b = _parse_bounds(row.get("ooc"))
    alert_b = _parse_bounds(row.get("alert_spec"))
    recv_b = _parse_bounds(row.get("recv"))
    oos = oos_b[1] if oos_b else None
    ooc = ooc_b[1] if ooc_b else None
    alert = alert_b[1] if alert_b else None
    recv = recv_b[1] if recv_b else None

    scada_oos_raw = row.get("scada_oos")
    scada_ooc_raw = row.get("scada_ooc")
    scada_alert_raw = row.get("scada_alert")
    cwms_oos_raw = row.get("cwms_oos")
    cwms_ooc_raw = row.get("cwms_ooc")

    light = 3  # 1=紅 2=黃 3=綠 4=橙（對應舊版 int light 變數）
    msg = ""
    msg1 = ""
    msg3 = ""  # → DispatchResult.msg2（排除保養中）
    codes: list[str] = []

    def add_code(c: str) -> None:
        if c not in codes:
            codes.append(c)

    # ── 首發/再發初判（見「GetDataRed 完整還原」第一段）──────────────────
    if prev_mail is None:
        first = True
        msg0 = ""
    else:
        dt1 = prev_mail["cdatetime"]
        delta = now - dt1
        hours = delta.days * 24 + delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if delta.days >= 1 or hours > 4 or (hours == 4 and minutes > 0):
            first = True
            msg0 = ""
        else:
            first = False
            msg0 = prev_mail.get("msg1") or ""

    def check_first(sdata1: str) -> None:
        """4 小時內但這個條件的內容跟上一筆不同 → 照樣算首發。"""
        nonlocal first
        if not first and sdata1 not in msg0:
            first = True

    def escalate(sdata1: str) -> int:
        """回傳這次要用第幾個 escalation 時間點（0/1/2），3 代表已發滿三次、不再派報。"""
        nonlocal first
        cnt = 0
        if not first:
            if sdata1 not in msg0:
                first = True
            else:
                for idx in range(3):
                    suffix = "；" if idx == 0 else f"({ArrOOCS[idx]})；"
                    if (sdata1 + suffix) in msg0:
                        cnt = idx + 1
                        break
                else:
                    cnt = 3
        return cnt

    # ── 1) Alert < 讀值 < SPEC-OOC → 黃燈 ─────────────────────────────
    if alert is not None and ooc is not None and rvalue is not None and alert < rvalue < ooc:
        sdata1 = f"|{item}|：Alert＜最新讀值＜SPEC-OOC"
        check_first(sdata1)
        add_code(f"{sType}Alert-{plantno}")
        light = 2
        msg += f"{item}：Alert({_fmt(alert, item)})＜最新讀值({_fmt(rvalue, item)})＜SPEC-OOC({_fmt(ooc, item)})；"
        msg1 += sdata1
        msg3 += sdata1

    # ── 2) 讀值 > 允收值 → 黃燈（與上面共用同一個代碼）────────────────
    if recv is not None and rvalue is not None and rvalue > recv:
        sdata1 = f"|{item}|：最新讀值＞允收值"
        check_first(sdata1)
        add_code(f"{sType}Alert-{plantno}")
        light = 2
        msg += f"{item}：最新讀值({_fmt(rvalue, item)})＞允收值({_fmt(recv, item)})；"
        msg1 += sdata1
        msg3 += sdata1

    def mismatch(prefix_label: str, spec_label: str, source_name: str,
                 raw, spec_bounds, voc_exception: bool = False) -> None:
        """
        SCADA/CWMS 管制值與 SPEC 設定值不一致 → 橙燈（保養中特例：不亮橙、不進 msg2）。
        prefix_label 例：'SCADA-OOS' / 'CWMS-OOC'；spec_label 例：'SPEC-OOS' / 'Alert'。
        """
        nonlocal light, msg, msg1, msg3
        if spec_bounds is None:
            return
        kind, val = _scada_status(raw)
        if kind == "skip":
            return
        if kind == "special":
            sdata1 = f"|{item}|：{prefix_label}({val})"
            check_first(sdata1)
            code_kind = "斷訊" if val == "斷訊" else "保養中"
            add_code(f"{sType}{code_kind}-{plantno}")
            if val != "保養中":
                light = 4
            line = f"{item}：{source_name}({val})；"
            if line not in msg:
                msg += line
            msg1 += sdata1
            if val != "保養中":
                msg3 += sdata1
            return
        lo, hi = val
        slo, shi = spec_bounds
        if voc_exception and hi < shi:
            return  # VOC 例外：SCADA 比 SPEC 嚴（更低）不算不一致
        if round(lo, 2) == round(slo, 2) and round(hi, 2) == round(shi, 2):
            return  # 對齊舊系統 ChangeData(text,2) 四捨五入後比對
        sdata1 = f"|{item}|：{prefix_label}與{spec_label}不一致"
        check_first(sdata1)
        add_code(f"{sType}管制值不-{plantno}")
        light = 4
        msg += f"{item}：{prefix_label}({_fmt_bound(val, item)})與{spec_label}({_fmt_bound(spec_bounds, item)})不一致；"
        msg1 += sdata1
        msg3 += sdata1

    # ── 3~7) SCADA / CWMS 管制值不一致（VOC 例外只適用於 OOS/OOC，不適用 Alert）──
    mismatch("SCADA-Alert", "Alert", "SCADA", scada_alert_raw, alert_b)
    mismatch("SCADA-OOS", "SPEC-OOS", "SCADA", scada_oos_raw, oos_b, voc_exception=is_voc)
    mismatch("SCADA-OOC", "SPEC-OOC", "SCADA", scada_ooc_raw, ooc_b, voc_exception=is_voc)
    mismatch("CWMS-OOS", "SPEC-OOS", "CWMS", cwms_oos_raw, oos_b)
    mismatch("CWMS-OOC", "SPEC-OOC", "CWMS", cwms_ooc_raw, ooc_b)

    # ── 8) 讀值空 且 管制值也全空 → 紅燈（僅 broken=0 才進 codes，代表整組資料缺失）──
    if (rvalue_raw == "" and str(scada_oos_raw or "") == ""
            and str(scada_ooc_raw or "") == "" and str(scada_alert_raw or "") == ""):
        light = 1
        if broken == 0:
            add_code(f"{sType}OOS-{plantno}")
            add_code(f"{sType}OOC-{plantno}")

    # ── 9) SPEC-OOC <= 讀值 < SPEC-OOS → 橙燈（0/15/30 escalation）──────
    if oos is not None and ooc is not None and rvalue is not None and ooc <= rvalue < oos:
        if can_escalate:
            sdata1 = f"|{item}|：SPEC-OOC＜＝最新讀值＜SPEC-OOS"
            cnt = escalate(sdata1)
            if cnt != 3:
                suffix = ArrOOCS[cnt]
                add_code(f"{sType}OOC{suffix}-{plantno}")
                light = 4
                msg += (f"{item}：SPEC-OOC({_fmt(ooc, item)})＜＝最新讀值({_fmt(rvalue, item)})"
                        f"＜SPEC-OOS({_fmt(oos, item)})；")
                data2 = sdata1 + (suffix if cnt == 0 else f"({suffix})")
                msg1 += data2
                msg3 += sdata1
            else:
                light = 4
        else:
            light = 4

    # ── 10) 讀值 >= SPEC-OOS → 紅燈（0/15/30 escalation；斷訊時不進 codes）──
    if oos is not None and rvalue is not None and rvalue >= oos:
        if can_escalate:
            sdata1 = f"|{item}|：最新讀值＞＝SPEC-OOS"
            cnt = escalate(sdata1)
            if cnt != 3:
                suffix = ArrOOCS[cnt]
                if broken == 0:
                    add_code(f"{sType}OOS{suffix}-{plantno}")
                light = 1
                msg += f"{item}：最新讀值({_fmt(rvalue, item)})＞＝SPEC-OOS({_fmt(oos, item)})；"
                data2 = sdata1 + (suffix if cnt == 0 else f"({suffix})")
                msg1 += data2
                msg3 += sdata1
            else:
                light = 1
        else:
            light = 1

    if msg1:
        msg1 += "；"
    if msg3:
        msg3 += "；"

    is_first_final = first and bool(codes)

    # ── 再發節流閘（見「0/15/30 分鐘 escalation」節）──────────────────
    # 只有 first 全程維持 False（4 小時內、且每個觸發條件內容都跟上一筆相同）才會走到這裡：
    #   - codes 裡沒有 OOC/OOS escalation 代碼 → 4 小時內內容不變，完全不重發，codes 清空
    #   - codes 裡有 OOC/OOS escalation 代碼 → 只有距離上次派報「剛好 15 分鐘」才放行，
    #     否則 codes 清空（等下一次 15 分鐘節點再檢查一次）
    if not first and prev_mail is not None:
        delta = now - prev_mail["cdatetime"]
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if hours < 4:
            has_ooc_oos = any(("OOC" in c or "OOS" in c) for c in codes)
            if not has_ooc_oos:
                codes = []
            elif not (hours == 0 and minutes == 15):
                codes = []

    light_letter = {1: "R", 2: "Y", 3: "G", 4: "O"}.get(light, "G")

    return DispatchResult(codes=codes, msg=msg, msg1=msg1, msg2=msg3,
                           light=light_letter, is_first=is_first_final)


# ── GetMsg / GetMsg1(...,"msg1"/"msg2") / 首發判斷 的組字函式 ─────────────
# 對應 Job_dbVOC.cs：同廠區所有列的 DispatchResult 依序串接即可（原版用 DataTable 逐列掃描，
# 這裡輸入已經是「同一廠區」的 DispatchResult list，效果相同）。

def build_plant_msg(results: list[DispatchResult]) -> str:
    """對應 GetMsg(dtb, plantno, r)：人類可讀訊息，存 VOC_MAIL_Log.msg、信件內文。"""
    return "".join(r.msg for r in results)


def build_plant_msg1(results: list[DispatchResult]) -> str:
    """對應 GetMsg1(dtb, plantno, r, "msg1")：比對鍵文字，存 VOC_MAIL_Log.msg1。"""
    return "".join(r.msg1 for r in results)


def build_plant_msg2(results: list[DispatchResult]) -> str:
    """對應 GetMsg1(dtb, plantno, r, "msg2")：排除保養中後的比對鍵文字，存 VOC_MAIL_Log.msg2。"""
    return "".join(r.msg2 for r in results)


def plant_is_first(results: list[DispatchResult]) -> bool:
    """對應 GetMsg1(...,"status").IndexOf("首發")>-1：任一列判定首發即整廠信件標「首發」。"""
    return any(r.is_first for r in results)


# ── GetMailList 對應（收件名單，交給 maillist_service 參數化查詢，不重寫 SQL）──

def _rpttypes_for_plant(data_red, plantno: str) -> str:
    """
    從派報代碼清單抽出屬於指定廠區的報表類型（去掉 '-廠區' 後綴），組成逗號字串。
    例：['水Alert-K7', '水OOC15-K7', '水OOS-K9'] + plantno='K7' → '水Alert,水OOC15'
    """
    codes = [c for c in data_red.split(",") if c] if isinstance(data_red, str) else list(data_red)
    types: list[str] = []
    for c in codes:
        if "-" not in c:
            continue
        rtype, plant = c.rsplit("-", 1)
        if plant == plantno and rtype not in types:
            types.append(rtype)
    return ",".join(types)


def get_dispatch_maillist(db: Session, data_red, plantno: str, mailtype: str = "TO") -> list[str]:
    """
    對應 Job.dbVOC.GetMailList(DataRed, plantno, MailType)。
    TO 嚴格綁該廠（RptType+plantno 成對比對）；CC 額外納入 GMO、環工部
    （實際過濾邏輯在 maillist_service.get_mail_recipients / build_maillist_where，全參數化）。
    """
    rpttype_csv = _rpttypes_for_plant(data_red, plantno)
    if not rpttype_csv:
        return []
    return get_mail_recipients(db, rpttype_csv, plantno, mailtype=mailtype)


# ── HTML 信件版型（純函式：輸入列資料，回傳 HTML 字串）──────────────────
# 顏色沿用 static/css/voc.css 的 design token；燈號用彩色圓點取代舊版內網 UNC 圖片路徑。

_LIGHT_COLORS = {
    "R": "#dc3545",  # --status-red
    "O": "#fd7e14",  # --status-orange
    "Y": "#d97706",  # --status-yellow
    "G": "#22c55e",  # --status-green
    "-": "#94a3b8",  # --status-gray
}
_SOURCE_BG = {1: "#fff8dc", 2: "#ffe4b5", 3: "#e2e8f0"}  # SCADA(--data-scada) / CWMS(--data-cwms) / QA(--data-qa)


def _light_dot(light: str) -> str:
    color = _LIGHT_COLORS.get(light, "#94a3b8")
    return (f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
            f'background:{color};border:1px solid #00000022;"></span>')


def build_subject(plantno: str, is_first: bool, now: datetime) -> str:
    """對應 SendMail 主旨格式：【首發/再發】請確認「法遵平台」即時監控狀況 : {plantno}-{時間} (Security C)。"""
    dt_label = now.strftime("%Y/%m/%d %H:%M")
    first_label = "首發" if is_first else "再發"
    return f"【{first_label}】請確認「法遵平台」即時監控狀況 : {plantno}-{dt_label} (Security C)"


def render_dispatch_email(plantno: str, rows: list[dict]) -> str:
    """
    產生信件 HTML body（純函式）。
    rows 每列需含：item, unit, law, oos, ooc, alert, recv,
                   scada_oos, scada_ooc, scada_alert, cwms_oos, cwms_ooc,
                   rvalue, light('R'/'O'/'Y'/'G'/'-'), remark, source(1/2/3)
    """
    legend = (
        f'{_light_dot("R")}&nbsp;<b style="color:{_LIGHT_COLORS["R"]}">最新讀值＞＝OOS</b>&nbsp;&nbsp;'
        f'{_light_dot("O")}&nbsp;<b style="color:{_LIGHT_COLORS["O"]}">OOC＜＝最新讀值＜OOS 或 SCADA/CWMS管制值＜＞SPEC</b>&nbsp;&nbsp;'
        f'{_light_dot("Y")}&nbsp;<b style="color:{_LIGHT_COLORS["Y"]}">Alert＜最新讀值＜OOC 或 最新讀值＞允收值</b>&nbsp;&nbsp;'
        f'{_light_dot("G")}&nbsp;<b style="color:{_LIGHT_COLORS["G"]}">正常狀態</b>'
    )
    head = (
        "<tr style='background:#CCFFFF;font-weight:bold;font-size:small;'>"
        "<td>廠區</td><td>項目</td><td>單位</td><td>法規許可值</td>"
        "<td>SPEC-OOS</td><td>SPEC-OOC</td><td>Alert</td><td>允收值</td>"
        "<td>SCADA-OOS-HH</td><td>SCADA-OOC-H</td><td>SCADA-Alert</td>"
        "<td>CWMS-OOS-HH</td><td>CWMS-OOC-H</td>"
        "<td>最新讀值</td><td>狀態</td><td>備註</td></tr>"
    )
    body_rows = []
    for r in rows:
        source_bg = _SOURCE_BG.get(int(r.get("source") or 1), "#fff8dc")
        body_rows.append(
            "<tr style='font-size:small;text-align:center;'>"
            f"<td>{plantno}</td>"
            f"<td>{r.get('item', '')}</td>"
            f"<td>{r.get('unit', '')}</td>"
            f"<td style='background:#fffde7;'>{r.get('law', '')}</td>"
            f"<td>{r.get('oos', '')}</td>"
            f"<td>{r.get('ooc', '')}</td>"
            f"<td>{r.get('alert', '')}</td>"
            f"<td>{r.get('recv', '')}</td>"
            f"<td>{r.get('scada_oos', '')}</td>"
            f"<td>{r.get('scada_ooc', '')}</td>"
            f"<td>{r.get('scada_alert', '')}</td>"
            f"<td>{r.get('cwms_oos', '')}</td>"
            f"<td>{r.get('cwms_ooc', '')}</td>"
            f"<td style='background:{source_bg};'>{r.get('rvalue', '')}</td>"
            f"<td>{_light_dot(r.get('light', 'G'))}</td>"
            f"<td>{r.get('remark', '')}</td>"
            "</tr>"
        )
    table = ("<table style='border:1px solid black;border-collapse:collapse;' cellpadding='4'>"
              + head + "".join(body_rows) + "</table>")
    return (
        "<html><body>"
        f"<p>Dear Sir,<br>您好, 您所負責的 <b>{plantno}</b> 有以下異常或提醒, "
        "呈現(紅燈/橘燈/黃燈)警示, 請儘速處理, 謝謝!</p>"
        f"<p>{legend}</p>"
        f"{table}"
        "<p><a href='/home'>進行查看</a>　<a href='/warning'>異常原因回覆</a></p>"
        "</body></html>"
    )


# ── VOC_MAIL_Log 寫入（對應 InsertMAIL）──────────────────────────────────

def insert_mail_log(db: Session, plantno: str, msg: str, msg1: str,
                     cdatetime: datetime, msg2: str = "") -> None:
    """
    對應 Job.dbVOC.InsertMAIL(plantno, msg, msg1, DateTime cdatetime, msg2)。
    參數化 SQL。msg2 一律寫入（含空字串），與舊版「msg2==''時省略該欄位」行為在結果上等價
    （欄位允許空字串，跟省略欄位讓它吃 DEFAULT/NULL 對後續 LIKE 查詢沒有差異）。
    """
    db.execute(text("""
        INSERT INTO [VOC].[dbo].[VOC_MAIL_Log] (plantno, cdatetime, msg, msg1, msg2)
        VALUES (:plantno, :cdatetime, :msg, :msg1, :msg2)
    """), {"plantno": plantno, "cdatetime": cdatetime, "msg": msg, "msg1": msg1, "msg2": msg2 or ""})
    db.commit()


def get_prev_mail(db: Session, plantno: str, item: str) -> dict | None:
    """對應 Get前筆派報資料(plantno, item)：查同廠區、msg1 LIKE '%|item|%' 的最後一筆。"""
    row = db.execute(text("""
        SELECT TOP 1 cdatetime, msg1
        FROM [VOC].[dbo].[VOC_MAIL_Log]
        WHERE plantno = :plantno AND msg1 LIKE :pattern
        ORDER BY cdatetime DESC
    """), {"plantno": plantno, "pattern": f"%|{item}|%"}).mappings().first()
    if not row:
        return None
    return {"cdatetime": row["cdatetime"], "msg1": row["msg1"] or ""}


# ── 隔離廠區項目 broken 標記（對應 List隔離廠區項目 + Update隔離廠區項目）──────

def list_isolated_items(db: Session) -> list[dict]:
    """對應 List隔離廠區項目：找目前時刻落在已核准隔離區間內、尚未標記保養中的項目。"""
    now = datetime.now()
    m = now.minute % 15
    dt0 = (now - timedelta(minutes=m)).strftime("%Y/%m/%d %H:%M:00")
    sql = text("""
        WITH ccDT AS (
            SELECT C.ccid
            FROM [VOC].[dbo].[VOC_closectl] C
            JOIN (
                SELECT IIF(orgccid IS NULL, ccid, orgccid) AS orgccid, MAX(ccid) AS ccid
                FROM [VOC].[dbo].[VOC_closectl]
                WHERE fstatusid = :fstatusid
                GROUP BY IIF(orgccid IS NULL, ccid, orgccid)
            ) D ON C.ccid = D.ccid
            WHERE C.stime <= :ttime AND C.etime >= :ttime AND C.fstatusid = :fstatusid
        )
        SELECT W.plantno, W.item, W.cdatetime, S1.source
        FROM ccDT C
        JOIN [VOC].[dbo].[VOC_closectl_list] L ON C.ccid = L.ccid
        JOIN [VOC].[dbo].[VOC_SPEC] S ON L.plantno = S.plantno AND L.item = S.item
        JOIN [VOC].[dbo].[VOC_SCADA_WEB] W ON L.plantno = W.plantno AND L.item = W.item
        JOIN [VOC].[dbo].[VOC_source] S1 ON L.sourceid = S1.sourceid
        WHERE W.rvalue != '保養中'
        GROUP BY W.plantno, W.item, W.cdatetime, S1.source
    """)
    try:
        rows = db.execute(sql, {"ttime": dt0, "fstatusid": FSTATUSID_APPROVED}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[list_isolated_items] DB 查詢失敗: {e}")
        return []


def mark_isolated_item(db: Session, plantno: str, item: str, source: str,
                        category: str | None = None) -> None:
    """
    對應 Update隔離廠區項目：把隔離中項目的 rvalue 標記為「保養中」、broken=2，
    同步更新 VOC_SCADA_WEB 與 VOC_SCADA_HIST（15 分鐘對齊的當期歷史列）。

    category（2026-08-01 D7 新增）：項目類型（來源 models_b.Item.category），用來判斷
    是否為雨水溝項目（雨水溝不覆寫管制值欄位）。**預設 None → 退回原本的
    `"雨水溝" in item` 名稱字串比對**，A 棧 apply_isolation 不傳此參數，行為不變。
    （B 棧不使用本函式——C 項決策：B 版隔離不落地竄改 reading_current，
      改由 isolation_checker 即時 JOIN 推導，見 services_b/dashboard_service.py。）
    """
    is_raingutter = is_raingutter_item(item, category)
    set_extra = ""
    if not is_raingutter:
        if source == "SCADA":
            set_extra = (
                "OOS_HH=IIF(OOS_HH='-','-',:status), OOC_H=IIF(OOC_H='-','-',:status), "
                "alert=IIF(alert='-','-',:status), OOS_LL=IIF(OOS_LL='-','-',:status), "
                "OOC_L=IIF(OOC_L='-','-',:status), alert_L=IIF(alert_L='-','-',:status), "
            )
        else:  # CWMS
            set_extra = "OOS_HH1=:status, OOC_H1=:status, OOS_LL1=:status, OOC_L1=:status, "

    now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    db.execute(text(f"""
        UPDATE [VOC].[dbo].[VOC_SCADA_WEB]
        SET {set_extra} rvalue=:status, cdatetime=:tdate, broken=2, light=3
        WHERE plantno=:plantno AND item=:item
    """), {"tdate": now_str, "plantno": plantno, "item": item, "status": "保養中"})

    now = datetime.now()
    m = now.minute % 15
    dt0 = (now - timedelta(minutes=m)).strftime("%Y/%m/%d %H:%M:00")
    db.execute(text(f"""
        UPDATE [VOC].[dbo].[VOC_SCADA_HIST]
        SET {set_extra} rvalue=:status, cdatetime=:tdate, broken=2, light=3
        WHERE plantno=:plantno AND item=:item AND cdatetime=:tdate
    """), {"tdate": dt0, "plantno": plantno, "item": item, "status": "保養中"})


def apply_isolation(db: Session) -> int:
    """先把隔離中項目的 broken 標成 2（List隔離廠區項目 + Update隔離廠區項目）。回傳處理筆數。"""
    items = list_isolated_items(db)
    for it in items:
        mark_isolated_item(db, it["plantno"], it["item"], it["source"])
    if items:
        db.commit()
    return len(items)


# ── GetData()（無參數）：JOB 撈全廠即時資料 ────────────────────────────

def get_data(db: Session) -> list[dict]:
    """
    對應 Job.dbVOC.GetData()。查詢結構比照 dashboard_service.get_dashboard_data，
    另外多帶 law/recv/source（GetMailList 分類與信件版型需要）。
    """
    sql = text("""
        SELECT
            S.plantno,
            REPLACE(REPLACE(S.item, 'COD2', 'COD'), 'pH1', 'pH') AS item,
            I.unit,
            S.LAW       AS law,
            S.OOS       AS oos,
            S.OOC       AS ooc,
            S.alert     AS alert_spec,
            S.recv      AS recv,
            S.source    AS source,
            W.OOS_HH    AS scada_oos,
            W.OOC_H     AS scada_ooc,
            W.alert     AS scada_alert,
            W.OOS_HH1   AS cwms_oos,
            W.OOC_H1    AS cwms_ooc,
            W.rvalue    AS rvalue_raw,
            REPLACE(REPLACE(REPLACE(REPLACE(
                W.rvalue, 'N.D', '0'), '<0.05', '0'), '<0.02', '0'), '<0.01', '0'
            )           AS rvalue,
            W.broken,
            P.plantid,
            S.seqno,
            E.emptycell
        FROM  [VOC].[dbo].[VOC_SPEC] S
        JOIN  [VOC].[dbo].[VOC_plant] P ON S.plantno = P.plantno
        JOIN  [VOC].[dbo].[VOC_item]  I ON S.item = I.item
        LEFT JOIN [VOC].[dbo].[VOC_SCADA_WEB] W ON S.plantno = W.plantno AND S.item = W.item
        LEFT JOIN [VOC].[dbo].[VOC_EmptyCell] E ON S.plantno = E.plantno AND S.item = E.item
        ORDER BY P.plantid, S.seqno
    """)
    try:
        rows = db.execute(sql).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[get_data] DB 查詢失敗: {e}")
        return []


def _row_to_html_dict(row: dict, result: DispatchResult) -> dict:
    """把 GetData() 的一列資料 + evaluate_row 結果轉成 render_dispatch_email 需要的顯示欄位。"""
    return {
        "item": row.get("item", ""),
        "unit": row.get("unit", ""),
        "law": row.get("law", ""),
        "oos": row.get("oos", ""),
        "ooc": row.get("ooc", ""),
        "alert": row.get("alert_spec", ""),
        "recv": row.get("recv", ""),
        "scada_oos": row.get("scada_oos", ""),
        "scada_ooc": row.get("scada_ooc", ""),
        "scada_alert": row.get("scada_alert", ""),
        "cwms_oos": row.get("cwms_oos", ""),
        "cwms_ooc": row.get("cwms_ooc", ""),
        "rvalue": row.get("rvalue_raw", ""),
        "light": result.light,
        "remark": "",
        "source": row.get("source") or 1,
    }


# ── run_dispatch：主流程 ──────────────────────────────────────────────

def run_dispatch(db: Session) -> dict:
    """
    對應 Job.SendMail.SendMail_廠務法規許可值標準化管控報表()。

    流程：
      1. 隔離中項目標 broken=2（apply_isolation）
      2. GetData() 撈全廠資料
      3. 逐列 evaluate_row 判斷是否派報
      4. 依廠區分組，組 HTML 信件、寄出、insert_mail_log
      5. K14B 跨廠通報：非 K14B 且 msg2 含「＞允收值」時，把「水Alert-K14B」的 TO 名單加進 CC

    ⚠️ 與舊系統刻意不同（詳見模組頂端說明）：mailto 為空時 continue 而非 return；
       不寫回 light 到 DB；不做 SMS/PushPlus。
    """
    now = datetime.now().replace(second=0, microsecond=0)

    apply_isolation(db)
    data = get_data(db)

    plant_rows: dict[str, list[dict]] = defaultdict(list)
    plant_results: dict[str, list[DispatchResult]] = defaultdict(list)

    for row in data:
        prev = get_prev_mail(db, row["plantno"], row["item"])
        result = evaluate_row(row, prev, now)
        plant_rows[row["plantno"]].append(row)
        plant_results[row["plantno"]].append(result)

    summary = {"sent": [], "skipped_no_recipient": [], "no_anomaly_plants": 0}

    for plantno, results in plant_results.items():
        if not any(r.codes for r in results):
            summary["no_anomaly_plants"] += 1
            continue

        msg = build_plant_msg(results)
        msg1 = build_plant_msg1(results)
        msg2 = build_plant_msg2(results)
        is_first = plant_is_first(results)

        data_red: list[str] = []
        for r in results:
            for c in r.codes:
                if c not in data_red:
                    data_red.append(c)

        mail_to = get_dispatch_maillist(db, data_red, plantno, "TO")
        mail_cc = get_dispatch_maillist(db, data_red, plantno, "CC")

        # K14B 跨廠通報
        if plantno != "K14B" and "＞允收值" in msg2:
            k14b_to = get_dispatch_maillist(db, ["水Alert-K14B"], "K14B", "TO")
            for e in k14b_to:
                if e not in mail_cc:
                    mail_cc.append(e)

        if not mail_to:
            # 刻意修正舊系統的隱藏 bug：舊版 mailto 為空時直接 return 0，
            # 會連帶跳過同一輪迴圈裡「後面所有廠區」的信；這裡改成只跳過這個廠區。
            logger.warning(f"[run_dispatch] 廠區 {plantno} 無收件人（TO 為空），略過此廠區信件")
            summary["skipped_no_recipient"].append(plantno)
            continue

        html_rows = [_row_to_html_dict(r, res) for r, res in zip(plant_rows[plantno], results)]
        body = render_dispatch_email(plantno, html_rows)
        subject = build_subject(plantno, is_first, now)

        send_email_sync(subject, body, mail_to, cc_addresses=mail_cc)

        # 注意：燈號不寫回 DB（省略舊版 UpdateData 動作）——與 CLAUDE.md 決策一致，
        # 燈號一律在讀取當下即時重算，不落地存值。
        insert_mail_log(db, plantno, msg, msg1, now, msg2)
        summary["sent"].append(plantno)

    return summary
