"""
dashboard_schema.py — 儀表板資料列的 Pydantic 資料結構

欄位對應關係：
  law_spec  ← VOC_SPEC.LAW
  oos       ← VOC_SPEC.OOS
  ooc       ← VOC_SPEC.OOC
  alert_spec← VOC_SPEC.alert
  recv      ← VOC_SPEC.recv
  scada_*   ← VOC_SCADA_WEB（SCADA 系統自設的管制值）
  cwms_*    ← VOC_SCADA_WEB（CWMS 系統的管制值）
  rvalue_raw← VOC_SCADA_WEB.rvalue（原始字串，含 N.D / 斷訊 等文字）
  rvalue    ← 同上，但 N.D/<0.05/<0.02/<0.01 已替換為 '0'（供數字比對用）
  broken    ← VOC_SCADA_WEB.broken（0=正常, 1=斷訊, 2=保養中/隔離中）
"""

from pydantic import BaseModel
from typing import Optional


class DashboardRow(BaseModel):
    # ── 基本識別 ───────────────────────────────────────────
    plantno: str
    item: str
    unit: Optional[str] = ""

    # ── SPEC 三階文件規格值 ────────────────────────────────
    law_spec:   Optional[str] = ""   # 法規許可值（政府核准上限）
    oos:        Optional[str] = ""   # Out of Spec 上限
    ooc:        Optional[str] = ""   # Out of Control 上限
    alert_spec: Optional[str] = ""   # 預警值
    recv:       Optional[str] = ""   # 允收值

    # ── SCADA 系統自設管制值（存在 VOC_SCADA_WEB，由 JOB 從 SCADA 讀回）──
    # 與 SPEC 值一旦不一致，系統顯示橙燈提醒兩邊要同步
    scada_oos:    Optional[str] = ""  # SCADA OOS-HH
    scada_ooc:    Optional[str] = ""  # SCADA OOC-H
    scada_alert:  Optional[str] = ""  # SCADA Alert
    scada_oos_ll: Optional[str] = ""  # SCADA OOS 下限（pH 等雙邊規格用）
    scada_ooc_l:  Optional[str] = ""  # SCADA OOC 下限

    # ── CWMS 系統管制值 ────────────────────────────────────
    cwms_oos: Optional[str] = ""     # CWMS OOS-HH
    cwms_ooc: Optional[str] = ""     # CWMS OOC-H

    # ── 最新讀值 ────────────────────────────────────────────
    rvalue_raw: Optional[str] = ""   # 原始讀值（含 N.D / 斷訊 等文字，顯示用）
    rvalue:     Optional[str] = ""   # 處理後讀值（數字字串，計算用）

    # ── 感測器狀態 ──────────────────────────────────────────
    broken: int = 0                  # 0=正常, 1=斷訊, 2=保養中/隔離中

    # ── 附加資訊 ────────────────────────────────────────────
    source:    Optional[int] = 1     # 資料來源：1=SCADA, 2=CWMS, 3=QA手測
    url:       Optional[str] = ""    # 歷史曲線連結
    remark:    Optional[str] = ""    # 備註（斷訊說明、資料來源等）
    emptycell: Optional[str] = ""    # 空格標記（VOC_EmptyCell）

    # ── 計算結果（由 dashboard_service._calculate_light() 產生）──────────
    light_status: str  = "G"         # 燈號：'R'=紅, 'O'=橙, 'Y'=黃, 'G'=綠, '-'=無資料
    is_anomaly:   bool = False       # True = 斷訊 / 保養中 / 無法取得讀值

    # ── 廠區分組（由 dashboard_service 後處理，供 Jinja2 rowspan 使用）──
    plant_rowspan: int  = 1          # 此廠區共幾列（僅第一列設值，其餘為 0）
    show_plant:    bool = True       # 是否渲染廠區 <td>（非第一列設 False）
    plant_has_red: bool = False      # 此廠區是否有任何紅燈（影響廠區格背景色）

    # ── B 棧新增（schema_B_設計提案.md J 項）──────────────────────────────
    # rain_24h：reading_current.rain_24h，由 B 棧轉拋 JOB 直接算好寫入（取代 A 棧 PMS 跨庫 JOIN，
    # 見 docs/PhaseA執行規格書.md 第二節）。A 棧 services/dashboard_service.py 目前不填此欄，
    # 預設空字串對現有模板無影響（純新增選填欄位，向後相容）。
    rain_24h: Optional[str] = ""
