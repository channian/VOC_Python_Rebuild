"""
scripts/seed_demo_data.py — 豐富版展示資料（直接寫 B，不經 A 轉換，零舊資料品質問題）。

用途：功能測試/展示用的「乾淨新路」資料。與 scripts/seed_test_data.py（整合測試最小基準）
互不取代——測試套件繼續用 seed_test_data，本腳本給人工測試/展示用，內容刻意豐富：

  廠區（3 個）：
    K71（水廠）  ：pH 雙邊/紅/黃/橙(設定不同步)/QA 項目/斷訊/建置中/雨水溝/隔離保養中 全情境
    K72（空/VOC）：VOC 正常/橙/N.D/<0.05
    K14B（中水） ：中水緊急通知（warning_service 寫死查 K14B）用的資料
  人員：優先讀 scripts/migration_personnel.json（你部門同事，email 直接寫）；
        沒有該檔時退回 TEST001/TEST999 佔位身分。
  名單：簽核人種齊 隔離簽核(水/空保養中) + 水質異常 + 14 種派報 rpttype（重用 migration 綁定邏輯）。
  隔離：K71 溫度1 一張「已核准、現行有效」隔離單 → 儀表板顯示保養中、派報抑制可直接驗。

⚠️ 先清後灌：會整庫清空再重建（僅限專用測試庫 voc_b 使用！）。可重複執行。

用法：
  python scripts/seed_demo_data.py
"""

import hashlib
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import BSessionLocal, create_all_b  # noqa: E402
from migration.context import MigrationContext, Person, PersonnelBinding, load_personnel  # noqa: E402
from migration.normalize.personnel import build_personnel  # noqa: E402
from models_b import (  # noqa: E402
    AclUserRole, Curve, Dept, Isolation, IsolationItem, Item, KepwareSim,
    MailTypeModel, Plant, ReadingCurrent, ReadingHistory, Spec, TagMapping,
)
from scripts.seed_test_data import _clear_test_scope, _seed_catalog, _upsert  # noqa: E402
from services.flow_service import FlowStatus, Ttype  # noqa: E402

PERSONNEL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migration_personnel.json")

PLANTS = [
    # (plant_id, plant_no, sort)
    (901, "K71", 1),   # 水廠：全情境
    (902, "K72", 2),   # 空/VOC 廠
    (903, "K14B", 3),  # 中水放流（warning_service 寫死查 K14B）
]


def _load_binding() -> PersonnelBinding:
    """優先用使用者填好的 migration_personnel.json；沒有就退回 TEST001/TEST999 佔位。"""
    if os.path.exists(PERSONNEL_JSON):
        print(f"  人員：讀取 {PERSONNEL_JSON}（你部門同事）")
        return load_personnel(PERSONNEL_JSON)
    print("  人員：未找到 migration_personnel.json，使用佔位身分 TEST001/TEST999")
    return PersonnelBinding(
        applicants=[Person("TEST001", "測試申請人", "TEST_PLACEHOLDER@aseglobal.com")],
        signers=[Person("TEST999", "測試簽核人", "TEST_PLACEHOLDER@aseglobal.com")],
    )


def _spec(plant_no, item, law, oos, ooc, alert, recv, source_id=1, tag=None, seq=0, low=None):
    """單邊規格 helper；low=(oos_l,ooc_l,alert_l,recv_l) 時為雙邊。值為 None 的門檻標 na。"""
    def _s(v):
        return "valid" if v is not None else "na"
    lows = low or (None, None, None, None)
    return Spec(
        plant_no=plant_no, item=item, law_text=law,
        oos_low=lows[0], oos_high=oos, oos_status=_s(oos),
        ooc_low=lows[1], ooc_high=ooc, ooc_status=_s(ooc),
        alert_low=lows[2], alert_high=alert, alert_status=_s(alert),
        recv_low=lows[3], recv_high=recv, recv_status=_s(recv),
        source_id=source_id, tagname=tag, seqno=seq,
        updated_at=datetime.now(timezone.utc),
    )


def _reading(plant_no, item, value, status="normal", raw=None, comm_ok=True, rain=None, **scada):
    """reading_current helper：scada_* 未給時預設鏡射（scada_limit_status 依有無 scada 欄）。"""
    now = datetime.now(timezone.utc)
    return ReadingCurrent(
        plant_no=plant_no, item=item,
        value=value, status=status,
        raw_text=raw if raw is not None else (str(value) if value is not None else None),
        comm_ok=comm_ok, rain_24h=rain,
        scada_limit_status="valid" if scada else "na", cwms_limit_status="na",
        measured_at=now, updated_at=now, **scada,
    )


D = Decimal


def _seed_k71(session) -> None:
    """K71 水廠：一次涵蓋所有燈號/狀態情境。"""
    items = [
        # (item_id, item, display, unit)
        (9101, "pH1", "pH", "pH"), (9102, "COD", None, "mg/L"), (9103, "SS", None, "mg/L"),
        (9104, "Cu", None, "mg/L"), (9105, "Ni", None, "mg/L"), (9106, "氨氮", None, "mg/L"),
        (9107, "導電度", None, "µS/cm"), (9108, "硝酸鹽", None, "mg/L"),
        (9109, "溫度1", "溫度", "°C"), (9110, "雨水溝1", "雨水溝", "-"),
    ]
    for iid, item, disp, unit in items:
        session.add(Item(item_id=iid, item=item, display_name=disp, unit=unit, is_active=True))
    session.flush()

    session.add_all([
        # pH 雙邊 6-9 → 讀值 7.2 綠
        _spec("K71", "pH1", "6-9", D("9"), D("8.5"), D("8.2"), D("8.5"),
              tag="K71.PH1.PV", seq=1, low=(D("6"), D("6.5"), D("6.8"), D("6.5"))),
        # COD → 讀值 120 超 OOS 100 → 紅（派報【首發】素材）
        _spec("K71", "COD", "100", D("100"), D("80"), D("60"), D("80"), tag="K71.COD.PV", seq=2),
        # SS → 讀值 35：Alert30 < 35 < OOC40 → 黃
        _spec("K71", "SS", "50", D("50"), D("40"), D("30"), D("40"), seq=3),
        # Cu → 讀值 1.0 本身綠，但 SCADA OOC(2.4)≠SPEC OOC(2.5) → 橙（設定不同步）
        _spec("K71", "Cu", "3.0", D("3.0"), D("2.5"), D("2.0"), D("2.5"), seq=4),
        # Ni → 讀值 2.3 > 允收 2.2 → 黃（>允收規則）
        _spec("K71", "Ni", "3.0", D("3.0"), D("2.5"), None, D("2.2"), seq=5),
        # 氨氮 → QA 手動輸入來源（/ui/qa 清單要看得到）
        _spec("K71", "氨氮", "10", D("10"), D("8"), D("6"), D("8"), source_id=3, seq=6),
        # 導電度 → 斷訊（灰）
        _spec("K71", "導電度", "750", D("750"), D("700"), D("650"), D("700"), seq=7),
        # 硝酸鹽 → 不給 reading_current → 建置中（灰）
        _spec("K71", "硝酸鹽", "50", D("50"), D("40"), D("30"), D("40"), seq=8),
        # 溫度1 雙邊 → 被隔離中 → 保養中
        _spec("K71", "溫度1", "20-38", D("38"), D("36"), D("35"), D("36"), seq=9,
              low=(D("20"), D("22"), D("23"), D("22"))),
        # 雨水溝1 → 預警頁素材（0=正常）
        _spec("K71", "雨水溝1", "-", None, None, None, None, seq=10),
    ])
    session.flush()

    session.add_all([
        _reading("K71", "pH1", D("7.20"),
                 scada_oos_low=D("6"), scada_oos_high=D("9"),
                 scada_ooc_low=D("6.5"), scada_ooc_high=D("8.5"),
                 scada_alert_low=D("6.8"), scada_alert_high=D("8.2")),
        _reading("K71", "COD", D("120"),
                 scada_oos_high=D("100"), scada_ooc_high=D("80"), scada_alert_high=D("60")),
        _reading("K71", "SS", D("35"),
                 scada_oos_high=D("50"), scada_ooc_high=D("40"), scada_alert_high=D("30")),
        _reading("K71", "Cu", D("1.00"),   # SCADA OOC 2.4 ≠ SPEC 2.5 → 橙
                 scada_oos_high=D("3.0"), scada_ooc_high=D("2.4"), scada_alert_high=D("2.0")),
        _reading("K71", "Ni", D("2.30"),
                 scada_oos_high=D("3.0"), scada_ooc_high=D("2.5")),
        _reading("K71", "氨氮", D("4.50")),                      # QA 來源
        _reading("K71", "導電度", D("720"), comm_ok=False),       # 斷訊 → 灰
        # 硝酸鹽：刻意不給 → 建置中
        _reading("K71", "溫度1", D("30.0"),
                 scada_oos_low=D("20"), scada_oos_high=D("38")),  # 實際顯示由隔離覆蓋為保養中
        _reading("K71", "雨水溝1", D("0"), raw="0", rain=D("0.0")),
    ])
    # 歷史曲線頁連結：指向新儀表板配套工作包在做的 /trend/ui（每廠一頁，故 K71 兩個
    # 項目的曲線連結共用同一個 plant 參數格式），讓儀表板「曲線 ↗」可實際點得進去。
    session.add(Curve(plant_no="K71", item="pH1", url="/trend/ui?plant=K71"))
    session.add(Curve(plant_no="K71", item="COD", url="/trend/ui?plant=K71"))
    session.flush()

    # 溫度1 現行有效隔離（已核准）→ 儀表板保養中 + 派報抑制
    now = datetime.now(timezone.utc)
    iso = Isolation(
        ccno=now.strftime("%Y%m%d") + "901", ttype=int(Ttype.新增), plant_id=901,
        mdfdesc="示範：溫度計保養（seed_demo_data 種入，已核准生效中）", remark="demo",
        stime=now - timedelta(hours=1), etime=now + timedelta(days=30),
        cemp_no="DEMO", cemp_name="示範資料", fstatus=int(FlowStatus.核准),
    )
    session.add(iso)
    session.flush()
    session.add(IsolationItem(isolation_id=iso.id, plant_no="K71", item="溫度1", source_id=1))
    session.flush()


def _seed_k72(session) -> None:
    """K72 空/VOC 廠：VOC 正常/橙/N.D/<0.05。"""
    # display_name 只給 VOC1（→VOC），其餘保留原名，避免儀表板四列全顯示成同名分不清
    for iid, item, disp in [(9201, "VOC1", "VOC"), (9202, "VOC2", None), (9203, "VOC3", None), (9204, "VOC4", None)]:
        session.add(Item(item_id=iid, item=item, display_name=disp, unit="ppm", is_active=True))
    session.flush()
    for i, (item, oos, ooc, alert) in enumerate([
        ("VOC1", D("50"), D("40"), D("30")), ("VOC2", D("50"), D("40"), D("30")),
        ("VOC3", D("5"), D("4"), D("3")), ("VOC4", D("5"), D("4"), D("3")),
    ], start=1):
        session.add(_spec("K72", item, str(oos), oos, ooc, alert, ooc, seq=i, tag=f"K72.{item}.PV"))
    session.flush()
    session.add_all([
        _reading("K72", "VOC1", D("10.0"),
                 scada_oos_high=D("50"), scada_ooc_high=D("40"), scada_alert_high=D("30")),
        _reading("K72", "VOC2", D("45.0"),   # OOC40 <= 45 < OOS50 → 橙
                 scada_oos_high=D("50"), scada_ooc_high=D("40"), scada_alert_high=D("30")),
        _reading("K72", "VOC3", None, status="nd", raw="N.D"),
        _reading("K72", "VOC4", D("0.05"), status="below_lod", raw="<0.05"),
    ])
    session.add(Curve(plant_no="K72", item="VOC1", url="/trend/ui?plant=K72"))
    session.flush()


def _seed_k14b(session) -> None:
    """K14B 中水放流：中水緊急通知（warning_service 寫死查 K14B）用資料。"""
    for iid, item, unit in [(9301, "pH2", "pH"), (9302, "COD3", "mg/L"), (9303, "SS2", "mg/L")]:
        session.add(Item(item_id=iid, item=item, display_name=None, unit=unit, is_active=True))
    session.flush()
    session.add_all([
        _spec("K14B", "pH2", "6-9", D("9"), D("8.5"), D("8.2"), D("8.5"), seq=1,
              low=(D("6"), D("6.5"), D("6.8"), D("6.5"))),
        _spec("K14B", "COD3", "100", D("100"), D("80"), D("60"), D("80"), seq=2),
        _spec("K14B", "SS2", "50", D("50"), D("40"), D("30"), D("40"), seq=3),
    ])
    session.flush()
    session.add_all([
        _reading("K14B", "pH2", D("7.8")),
        _reading("K14B", "COD3", D("90")),   # OOC80 <= 90 < OOS100 → 橙（中水通知有異常可列）
        _reading("K14B", "SS2", D("20")),
    ])
    session.add(Curve(plant_no="K14B", item="COD3", url="/trend/ui?plant=K14B"))
    session.flush()


def _pseudo_jitter(item: str, hour_idx: int) -> float:
    """確定性偽隨機（禁用 random 模組）：md5((item, hour_idx)) 雜湊映射到 [-1, 1)。

    同一個 (item, hour_idx) 組合永遠回傳同一個值——只靠 datetime.now() 決定「現在是幾點」
    這個時間錨點，數值本身不吃任何非確定來源，所以同一天重跑 seed 兩次，每筆讀值都一樣
    （配合 _clear_test_scope 先清後灌，天然冪等，不會累加/翻倍）。
    """
    digest = hashlib.md5(f"{item}:{hour_idx}".encode("utf-8")).hexdigest()
    n = int(digest[:8], 16)
    return (n % 2000 - 1000) / 1000.0


# K71 COD 最後 6 小時的爬升覆寫序列（越過 OOS=100，終點 120 銜接 _seed_k71 現況
# reading_current COD=120 紅燈，讓「曲線頁」與「儀表板目前讀值」的敘事一致）。
_COD_RAMP = [D("70"), D("82"), D("94"), D("106"), D("113"), D("120")]

# (plant_no, item, 基準值, 正弦波振幅)：基準值取自 _seed_k71/_seed_k72/_seed_k14b 已種入的
# reading_current 讀值，讓歷史曲線的最新一點與儀表板目前顯示的讀值銜接得起來。
_HISTORY_SERIES = [
    ("K71", "pH1", D("7.20"), D("0.35")),
    ("K71", "COD", D("55.00"), D("4.00")),   # 前 162 小時正常波動，最後 6 小時被 _COD_RAMP 覆寫
    ("K71", "SS",  D("35.00"), D("3.00")),
    ("K71", "Cu",  D("1.00"),  D("0.08")),
    ("K71", "Ni",  D("2.30"),  D("0.10")),
    ("K72", "VOC1", D("10.00"), D("1.00")),
    ("K72", "VOC2", D("45.00"), D("2.00")),
    ("K14B", "COD3", D("90.00"), D("4.00")),
]

# 各項目對應的 SPEC 三階管制值快照（沿用 _seed_k71/_seed_k72/_seed_k14b 已種入的規格數字，
# 只有 pH1 是雙邊項目才需要 *_low）。
_HISTORY_SPEC_SNAPSHOT = {
    ("K71", "pH1"):   dict(oos=D("9"), ooc=D("8.5"), alert=D("8.2"),
                            oos_low=D("6"), ooc_low=D("6.5"), alert_low=D("6.8")),
    ("K71", "COD"):   dict(oos=D("100"), ooc=D("80"), alert=D("60")),
    ("K71", "SS"):    dict(oos=D("50"), ooc=D("40"), alert=D("30")),
    ("K71", "Cu"):    dict(oos=D("3.0"), ooc=D("2.5"), alert=D("2.0")),
    ("K71", "Ni"):    dict(oos=D("3.0"), ooc=D("2.5"), alert=None),
    ("K72", "VOC1"):  dict(oos=D("50"), ooc=D("40"), alert=D("30")),
    ("K72", "VOC2"):  dict(oos=D("50"), ooc=D("40"), alert=D("30")),
    ("K14B", "COD3"): dict(oos=D("100"), ooc=D("80"), alert=D("60")),
}

_HISTORY_HOURS = 24 * 7  # 過去 7 天、每小時一筆


def _seed_reading_history(session) -> int:
    """K71 pH1/COD/SS/Cu/Ni、K72 VOC1/VOC2、K14B COD3：過去 7 天、每小時一筆 reading_history。

    新儀表板的歷史曲線頁（另一工作包在做）資料源是 reading_history；原本 demo 種子只有
    reading_current 沒有時序，曲線會是空的，這裡補上。

    數值造型：以「目前 reading_current 基準值」為中心的正弦波（模擬日夜週期）+ 依
    (item, 小時索引) 的確定性偽隨機小雜訊（見 _pseudo_jitter；禁用 random 模組，時間基準
    只有 datetime.now() 可用）。K71 COD 最後 6 小時另外覆寫為 _COD_RAMP 爬升序列，越過
    OOS=100；其他項目全程只在基準值附近小幅波動。每筆同時快照當下生效的 SPEC 三階管制值。
    """
    now = datetime.now(timezone.utc)
    base_hour = now.replace(minute=0, second=0, microsecond=0)

    rows = []
    for plant_no, item, baseline, wave_amp in _HISTORY_SERIES:
        snap = _HISTORY_SPEC_SNAPSHOT[(plant_no, item)]
        is_cod_ramp = (plant_no, item) == ("K71", "COD")

        for hour_idx in range(_HISTORY_HOURS):
            hours_ago = _HISTORY_HOURS - 1 - hour_idx  # 167（7 天前）→ 0（現在這一小時）
            measured_at = base_hour - timedelta(hours=hours_ago)

            if is_cod_ramp and hours_ago < len(_COD_RAMP):
                value = _COD_RAMP[len(_COD_RAMP) - 1 - hours_ago]
            else:
                wave = math.sin(2 * math.pi * hour_idx / 24.0)
                jitter = _pseudo_jitter(item, hour_idx)
                value = baseline + wave_amp * D(str(round(wave, 4))) + (wave_amp * D("0.4")) * D(str(round(jitter, 4)))
                value = value.quantize(D("0.01"))

            rows.append(ReadingHistory(
                plant_no=plant_no, item=item, value=value, status="normal",
                raw_text=str(value), measured_at=measured_at,
                spec_oos_high=snap.get("oos"), spec_ooc_high=snap.get("ooc"), spec_alert_high=snap.get("alert"),
                spec_oos_low=snap.get("oos_low"), spec_ooc_low=snap.get("ooc_low"), spec_alert_low=snap.get("alert_low"),
            ))

    session.add_all(rows)
    session.flush()
    return len(rows)


def _seed_shared(session, binding: PersonnelBinding) -> None:
    """廠區主檔、部門、mail_type 補齊、人員綁定（重用 migration 的 build_personnel）、kepware 模擬。"""
    for plant_id, plant_no, sort in PLANTS:
        session.add(Plant(plant_id=plant_id, plant_no=plant_no, kind="normal", is_show=True, sort=sort))
    session.flush()
    for plant_id, _, _ in PLANTS:
        session.add(Dept(plant_id=plant_id, dept_no="SW00"))
    session.flush()

    ctx = MigrationContext(personnel=binding, now=datetime.now(timezone.utc))
    # mail_type 目錄補齊（含 14 種派報 rpttype；unique rpttype，以 rpttype upsert）
    all_rpttypes = list(ctx.isolation_sign_rpttypes) + [ctx.water_dispatch_rpttype] + list(ctx.dispatch_rpttypes)
    for i, rt in enumerate(dict.fromkeys(all_rpttypes), start=10):
        _upsert(session, MailTypeModel, {"rpttype": rt}, {"type_id": i})

    plant_nos = [p[1] for p in PLANTS]
    people = build_personnel(ctx, plant_nos)
    for objs in people.values():
        for obj in objs:
            session.merge(obj)
    # 申請人也給隔離維護角色（role 3），行為與 seed_test_data 一致
    for p in binding.applicants:
        for plant_no in plant_nos:
            session.merge(AclUserRole(role_id=3, emp_no=p.empno, plant_no=plant_no, dept_no="SW00", stype="user"))
    session.flush()

    # kepware 模擬（供 sync worker 測試；值與 demo 基準一致，跑 sync 不會蓋掉異常情境以外的值）
    now = datetime.now(timezone.utc)
    for tag, plant_no, item, value in [
        ("K71.PH1.PV", "K71", "pH1", "7.20"),
        ("K72.VOC1.PV", "K72", "VOC1", "10.0"),
    ]:
        session.add(TagMapping(source_table="kepware_sim", tagname=tag,
                               plant_no=plant_no, item=item, target_field="value", enabled=True))
        session.add(KepwareSim(datetime_=now, tagname=tag, value=value, quality="good"))
    session.flush()


def seed_demo() -> None:
    create_all_b()
    session = BSessionLocal()
    try:
        print("[seed_demo_data] 開始（整庫先清後灌，僅限專用測試庫）")
        _clear_test_scope(session)
        _seed_catalog(session)          # source/acl_role/rights/基本 mail_type/system_config
        binding = _load_binding()
        _seed_shared(session, binding)
        _seed_k71(session)
        _seed_k72(session)
        _seed_k14b(session)
        history_count = _seed_reading_history(session)
        session.commit()
        print("[seed_demo_data] 完成。內容速覽：")
        print("  K71（水）：COD=紅 / SS,Ni=黃 / Cu=橙(SCADA≠SPEC) / pH=綠 / 氨氮=QA /")
        print("            導電度=斷訊 / 硝酸鹽=建置中 / 溫度1=隔離保養中 / 雨水溝1=預警頁")
        print("  K72（空）：VOC2=橙 / VOC3=N.D / VOC4=<0.05 / VOC1=綠")
        print("  K14B（中水）：COD3=橙（中水緊急通知頁可列出）")
        print(f"  reading_history：{history_count} 筆（8 個項目 × 過去 7 天每小時一筆，"
              f"K71 COD 最後 6 小時爬升越過 OOS=100，曲線頁 /trend/ui?plant=... 有資料可畫）")
        print(f"  申請人：{[p.empno for p in binding.applicants]}／簽核人：{[p.empno for p in binding.signers]}")
        print("  → .env 的 MOCK_USER_EMPNO 請設成上面其中一個工號來切身分")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_demo()
