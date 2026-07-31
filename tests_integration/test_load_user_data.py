"""
tests_integration/test_load_user_data.py — 真 PG 整合測試：基礎資料一鍵載入器

涵蓋 scripts/load_user_data.py。用 conftest.py 的 `b_db` fixture（每個測試前先
seed_test_data.seed() 重灌基準資料：廠區 TEST1(plant_id=990)、項目 pH1(9001)/Cu1(9002)/
VOC1(9003)、spec 3 筆、tag_mapping 6 筆，皆 source_table='kepware_sim'；沒有可連線的
PostgreSQL 時整個目錄會被自動 skip，見 conftest.py）。

測試分兩類：
  1. 直接呼叫模組內函式（validate_main_rows / validate_plant_config / apply_load）驗證
     純邏輯與 DB 寫入結果——用 b_db session，測試內自行 commit/rollback。
  2. 透過 subprocess 實際跑 CLI（python scripts/load_user_data.py ...），驗證命令列參數、
     檔案格式讀取（.csv／.xlsx 多工作表）、--dry-run、逐列錯誤報告輸出的整合行為——用一個
     獨立的 BSessionLocal() 新 session 查驗結果（CLI 子程序是另一個行程，各自獨立連線）。

因為 seed_test_data 已佔用 plant_id=990、item_id 9001~9003，所有測試自建的廠區/項目一律
用不會與種子資料衝突的代號（ZZ*/XL*/K7 等），並用 plant_id/item_id 的「現有最大值 +1」
來驗證自動配號行為（配號邏輯本身就是讀 DB 現有最大值，不需要寫死期望值）。
"""

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from database_b import BSessionLocal
from models_b import Item, Plant, Spec, TagMapping
from scripts.load_user_data import (
    COL_ALERT, COL_DISPLAY, COL_ITEM, COL_LAW, COL_OOC, COL_OOS, COL_PLANT_NO,
    COL_RECV, COL_SEQ, COL_SOURCE, COL_TAG, COL_TYPE,
    apply_load, is_ph_item, read_main_and_config, validate_main_rows, validate_plant_config,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "load_user_data.py"

MAIN_HEADERS = [
    COL_PLANT_NO, COL_ITEM, COL_DISPLAY, "單位", COL_TYPE, COL_LAW,
    COL_OOS, COL_OOC, COL_ALERT, COL_RECV, COL_SOURCE, COL_TAG, COL_SEQ,
]


# ══════════════════════════════════════════════════════════════════════════
# 共用小工具
# ══════════════════════════════════════════════════════════════════════════

def _write_csv(path, rows, headers=MAIN_HEADERS):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _run_cli(file_path, extra_args=None):
    args = [sys.executable, str(SCRIPT_PATH), "--file", str(file_path)]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)


def _row(plant_no, item, display="", unit="", type_="水質", law="", oos="", ooc="", alert="",
         recv="", source="SCADA", tag="", seq=""):
    return [plant_no, item, display, unit, type_, law, oos, ooc, alert, recv, source, tag, seq]


# ══════════════════════════════════════════════════════════════════════════
# 1. 純邏輯 + 直接呼叫 apply_load（用 b_db）
# ══════════════════════════════════════════════════════════════════════════

def test_normal_load_creates_plant_item_spec_tagmapping(b_db):
    rows = [
        _row("ZZ1", "CODZ", unit="mg/L", law="100", oos="100", ooc="80", alert="60", recv="80",
             tag="ZZ1.COD.PV", seq="1"),
        _row("ZZ1", "pH1", display="pH", unit="pH", law="6-9", oos="6-9", ooc="6.5-8.5",
             alert="6.8-8.2", recv="6.5-8.5", tag="ZZ1.PH1.PV", seq="2"),
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])
    assert errors == []
    assert len(parsed) == 2

    summary = apply_load(b_db, parsed, {}, "kepware_sim")
    b_db.commit()

    assert summary["spec_upsert"] == 2
    assert summary["tag_upsert"] == 2

    plant = b_db.execute(select(Plant).where(Plant.plant_no == "ZZ1")).scalar_one()
    assert plant.sort == 1  # 主表首次出現順序
    assert plant.is_show is True

    codz = b_db.execute(select(Item).where(Item.item == "CODZ")).scalar_one()
    assert codz.unit == "mg/L"

    # pH1 已在種子資料中存在（item_id=9001），沿用既有 id，不應該產生第二筆
    ph_items = b_db.execute(select(Item).where(Item.item == "pH1")).scalars().all()
    assert len(ph_items) == 1
    assert ph_items[0].item_id == 9001

    spec_codz = b_db.execute(
        select(Spec).where(Spec.plant_no == "ZZ1", Spec.item == "CODZ")
    ).scalar_one()
    assert spec_codz.oos_low is None
    assert float(spec_codz.oos_high) == 100.0
    assert spec_codz.oos_status == "valid"
    assert spec_codz.source_id == 1

    spec_ph = b_db.execute(
        select(Spec).where(Spec.plant_no == "ZZ1", Spec.item == "pH1")
    ).scalar_one()
    assert float(spec_ph.oos_low) == 6.0
    assert float(spec_ph.oos_high) == 9.0

    tags = b_db.execute(
        select(TagMapping).where(TagMapping.source_table == "kepware_sim", TagMapping.plant_no == "ZZ1")
    ).scalars().all()
    assert {t.tagname for t in tags} == {"ZZ1.COD.PV", "ZZ1.PH1.PV"}
    assert all(t.target_field == "value" and t.enabled for t in tags)


def test_dry_run_via_apply_then_rollback_writes_nothing(b_db):
    """模擬 CLI --dry-run 的作法：apply_load 後 rollback，確認完全沒有落地。"""
    rows = [_row("YY1", "CODY", unit="mg/L", oos="100", tag="YY1.COD.PV")]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])
    assert errors == []

    apply_load(b_db, parsed, {}, "kepware_sim")
    b_db.rollback()

    # 開一個全新的 session 查詢（避免同一個 session 的 identity map 造成誤判）
    fresh = BSessionLocal()
    try:
        assert fresh.execute(select(Plant).where(Plant.plant_no == "YY1")).scalar_one_or_none() is None
        assert fresh.execute(select(Item).where(Item.item == "CODY")).scalar_one_or_none() is None
    finally:
        fresh.close()


def test_plant_id_allocation_reuses_existing_and_increments_for_new(b_db):
    """既有廠區(TEST1)沿用既有 id；新廠區從目前最大 plant_id + 1 開始配號。"""
    max_before = b_db.execute(select(func.max(Plant.plant_id))).scalar()

    rows = [
        _row("TEST1", "Cu1", unit="mg/L", law="3.0", oos="3.0"),  # 既有廠區+既有項目
        _row("NEWPLANT1", "NEWITEM1", unit="mg/L", oos="10"),      # 全新廠區+全新項目
        _row("NEWPLANT2", "NEWITEM2", unit="mg/L", oos="10"),      # 另一個全新廠區
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])
    assert errors == []

    summary = apply_load(b_db, parsed, {}, "kepware_sim")
    b_db.commit()

    assert summary["plant_reused"] == 1
    assert summary["plant_new"] == 2

    test1 = b_db.execute(select(Plant).where(Plant.plant_no == "TEST1")).scalar_one()
    assert test1.plant_id == 990  # 種子資料既有 id，未被改動

    new1 = b_db.execute(select(Plant).where(Plant.plant_no == "NEWPLANT1")).scalar_one()
    new2 = b_db.execute(select(Plant).where(Plant.plant_no == "NEWPLANT2")).scalar_one()
    assert new1.plant_id == max_before + 1
    assert new2.plant_id == max_before + 2


def test_tag_mapping_only_for_scada_with_tagname(b_db):
    rows = [
        _row("TT1", "ITEM_QA", source="QA", tag="TT1.QA.PV"),          # QA 來源，即使填了 Tag 也不建
        _row("TT1", "ITEM_NOTAG", source="SCADA", tag=""),             # SCADA 但沒填 Tag，不建
        _row("TT1", "ITEM_OK", source="SCADA", tag="TT1.OK.PV"),       # SCADA + 有 Tag，才建
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])
    assert errors == []

    summary = apply_load(b_db, parsed, {}, "kepware_sim")
    b_db.commit()

    assert summary["tag_upsert"] == 1
    tags = b_db.execute(
        select(TagMapping).where(TagMapping.source_table == "kepware_sim", TagMapping.plant_no == "TT1")
    ).scalars().all()
    assert len(tags) == 1
    assert tags[0].tagname == "TT1.OK.PV"
    assert tags[0].item == "ITEM_OK"


def test_idempotent_rerun_no_duplicates(b_db):
    rows = [_row("II1", "ITEMI", unit="mg/L", oos="100", tag="II1.I.PV", seq="1")]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])
    assert errors == []

    apply_load(b_db, parsed, {}, "kepware_sim")
    b_db.commit()
    apply_load(b_db, parsed, {}, "kepware_sim")  # 重跑一次
    b_db.commit()

    plants = b_db.execute(select(Plant).where(Plant.plant_no == "II1")).scalars().all()
    items = b_db.execute(select(Item).where(Item.item == "ITEMI")).scalars().all()
    specs = b_db.execute(select(Spec).where(Spec.plant_no == "II1", Spec.item == "ITEMI")).scalars().all()
    tags = b_db.execute(
        select(TagMapping).where(TagMapping.source_table == "kepware_sim", TagMapping.tagname == "II1.I.PV")
    ).scalars().all()

    assert len(plants) == 1
    assert len(items) == 1
    assert len(specs) == 1
    assert len(tags) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2. 純邏輯驗證（不需要 DB，但仍走 conftest 的 PG 可用性 autouse fixture）
# ══════════════════════════════════════════════════════════════════════════

def test_ph_single_sided_rejected_row_by_row_not_blocking_others():
    rows = [
        _row("K7", "CODZ", unit="mg/L", oos="100", ooc="80", alert="60", recv="80"),   # 正常
        _row("K7", "pH1", unit="pH", oos="9", ooc="8.5", alert="8.2", recv="8.5"),      # pH 單邊 → 應報錯
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert len(parsed) == 1
    assert parsed[0].item == "CODZ"

    error_fields = {e.field for e in errors}
    assert {"OOS", "OOC", "Alert", "允收值"} <= error_fields
    assert all(e.row == 3 for e in errors)  # 第 2 筆資料列＝Excel 第 3 列（表頭佔第 1 列）
    assert all("pH" in e.message and "雙邊" in e.message for e in errors)


def test_missing_required_field_reported():
    rows = [
        _row("", "ITEMX", oos="1"),                 # 廠區代號空白
        _row("K7", "", oos="1"),                     # 項目空白
        _row("K7", "ITEMY", type_="", oos="1"),       # 類型空白
        _row("K7", "ITEMZ", source="", oos="1"),      # 資料來源空白
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert parsed == []
    assert len(errors) == 4
    msgs = {(e.row, e.field): e.message for e in errors}
    assert msgs[(2, COL_PLANT_NO)] == "不可空白"
    assert msgs[(3, COL_ITEM)] == "不可空白"
    assert msgs[(4, COL_TYPE)] == "不可空白"
    assert msgs[(5, COL_SOURCE)] == "不可空白"


def test_invalid_type_and_source_enum_rejected():
    rows = [
        _row("K7", "ITEMA", type_="奇怪類型", oos="1"),
        _row("K7", "ITEMB", source="EXCEL", oos="1"),
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert parsed == []
    assert len(errors) == 2
    assert errors[0].field == COL_TYPE
    assert "水質/空汙/雨水溝" in errors[0].message
    assert errors[1].field == COL_SOURCE
    assert "SCADA/CWMS/QA" in errors[1].message


def test_item_display_name_conflict_across_rows_rejected():
    rows = [
        _row("K7", "SHARED", display="顯示A", unit="mg/L", oos="1"),
        _row("K9", "SHARED", display="顯示B", unit="mg/L", oos="1"),  # 顯示名與第一次出現不一致
    ]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert len(parsed) == 1
    assert parsed[0].plant_no == "K7"
    assert len(errors) == 1
    assert errors[0].row == 3
    assert errors[0].field == COL_DISPLAY
    assert "不一致" in errors[0].message


def test_building_status_parsed_for_all_bound_fields():
    rows = [_row("K7", "ITEMC", law="建置中", oos="建置中", ooc="建置中", alert="建置中", recv="建置中")]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert errors == []
    row = parsed[0]
    assert row.oos == (None, None, "building")
    assert row.ooc == (None, None, "building")
    assert row.alert == (None, None, "building")
    assert row.recv == (None, None, "building")


def test_blank_bound_status_na():
    rows = [_row("K9", "雨水溝1", type_="雨水溝")]  # OOS/OOC/Alert/允收值 全空
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert errors == []
    row = parsed[0]
    assert row.oos == (None, None, "na")
    assert row.recv == (None, None, "na")


def test_seqno_optional_int_validation():
    rows = [_row("K7", "ITEMD", oos="1", seq="abc")]
    parsed, errors = validate_main_rows([dict(zip(MAIN_HEADERS, r)) for r in rows])

    assert parsed == []
    assert len(errors) == 1
    assert errors[0].field == COL_SEQ


def test_is_ph_item_detection():
    assert is_ph_item("pH") is True
    assert is_ph_item("pH1") is True
    assert is_ph_item("PH2") is True
    assert is_ph_item("pHz") is False
    assert is_ph_item("COD") is False


def test_plant_config_sort_and_show():
    conf_rows = [
        {"廠區代號": "K7", "顯示排序": "5", "是否顯示": "N"},
        {"廠區代號": "K9", "顯示排序": "", "是否顯示": ""},
    ]
    conf, errors = validate_plant_config(conf_rows)
    assert errors == []
    assert conf["K7"] == {"sort": 5, "is_show": False}
    assert conf["K9"] == {"sort": None, "is_show": True}


def test_plant_config_invalid_show_value_reported():
    conf_rows = [{"廠區代號": "K7", "顯示排序": "1", "是否顯示": "也許"}]
    conf, errors = validate_plant_config(conf_rows)
    assert len(errors) == 1
    assert "Y/N" in errors[0].message


# ══════════════════════════════════════════════════════════════════════════
# 3. 檔案讀取（CSV BOM / xlsx 多工作表）
# ══════════════════════════════════════════════════════════════════════════

def test_read_csv_with_bom(tmp_path):
    path = tmp_path / "主表.csv"
    _write_csv(path, [_row("K7", "CODZ", unit="mg/L", oos="100")])

    main_rows, conf_rows = read_main_and_config(str(path))
    assert conf_rows == []
    assert len(main_rows) == 1
    assert main_rows[0][COL_PLANT_NO] == "K7"
    assert main_rows[0][COL_ITEM] == "CODZ"


def test_read_csv_with_sibling_plant_config(tmp_path):
    main_path = tmp_path / "主表.csv"
    _write_csv(main_path, [_row("K7", "CODZ", unit="mg/L", oos="100")])
    conf_path = tmp_path / "廠區設定.csv"
    with open(conf_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["廠區代號", "顯示排序", "是否顯示"])
        writer.writerow(["K7", "9", "N"])

    main_rows, conf_rows = read_main_and_config(str(main_path))
    assert len(main_rows) == 1
    assert len(conf_rows) == 1
    assert conf_rows[0]["廠區代號"] == "K7"


def test_read_xlsx_multi_sheet(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "主表.xlsx"
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "主表"
    ws1.append(MAIN_HEADERS)
    ws1.append(_row("XL1", "CODX", unit="mg/L", oos="100"))
    ws2 = wb.create_sheet("廠區設定")
    ws2.append(["廠區代號", "顯示排序", "是否顯示"])
    ws2.append(["XL1", 7, "Y"])
    wb.save(path)

    main_rows, conf_rows = read_main_and_config(str(path))
    assert len(main_rows) == 1
    assert main_rows[0][COL_PLANT_NO] == "XL1"
    assert len(conf_rows) == 1
    assert conf_rows[0]["廠區代號"] == "XL1"


def test_read_unsupported_extension_raises(tmp_path):
    path = tmp_path / "主表.txt"
    path.write_text("dummy")
    with pytest.raises(ValueError):
        read_main_and_config(str(path))


# ══════════════════════════════════════════════════════════════════════════
# 4. 端到端 CLI（subprocess，真的跑 python scripts/load_user_data.py）
# ══════════════════════════════════════════════════════════════════════════

def test_cli_dry_run_end_to_end_writes_nothing(b_db, tmp_path):
    path = tmp_path / "主表.csv"
    _write_csv(path, [_row("CLI1", "CLIITEM1", unit="mg/L", oos="100", tag="CLI1.I1.PV")])

    result = _run_cli(path, ["--dry-run"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRY-RUN" in result.stdout
    assert "成功 1 列、失敗 0 列" in result.stdout

    fresh = BSessionLocal()
    try:
        assert fresh.execute(select(Plant).where(Plant.plant_no == "CLI1")).scalar_one_or_none() is None
    finally:
        fresh.close()


def test_cli_real_run_writes_and_reports_summary(b_db, tmp_path):
    path = tmp_path / "主表.csv"
    _write_csv(path, [
        _row("CLI2", "CLIITEM2", unit="mg/L", oos="100", tag="CLI2.I2.PV", seq="1"),
        _row("CLI2", "pH1", display="pH", unit="pH", oos="6-9", ooc="6.5-8.5",
             alert="6.8-8.2", recv="6.5-8.5", tag="CLI2.PH1.PV", seq="2"),
    ])

    result = _run_cli(path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "已寫入資料庫" in result.stdout
    assert "成功 2 列、失敗 0 列" in result.stdout

    fresh = BSessionLocal()
    try:
        plant = fresh.execute(select(Plant).where(Plant.plant_no == "CLI2")).scalar_one()
        assert plant.is_show is True
        specs = fresh.execute(select(Spec).where(Spec.plant_no == "CLI2")).scalars().all()
        assert len(specs) == 2
        tags = fresh.execute(
            select(TagMapping).where(TagMapping.source_table == "kepware_sim", TagMapping.plant_no == "CLI2")
        ).scalars().all()
        assert len(tags) == 2
    finally:
        fresh.close()


def test_cli_row_errors_do_not_block_valid_rows(b_db, tmp_path):
    path = tmp_path / "主表.csv"
    _write_csv(path, [
        _row("CLI3", "CLIOK", unit="mg/L", oos="100"),
        _row("CLI3", "pH1", unit="pH", oos="9"),  # pH 單邊 → 錯誤
    ])

    result = _run_cli(path)
    assert result.returncode == 2  # 有列失敗，但仍有成功列被寫入
    assert "第 3 列 [OOS]" in result.stdout
    assert "成功 1 列、失敗 1 列" in result.stdout

    fresh = BSessionLocal()
    try:
        ok_spec = fresh.execute(
            select(Spec).where(Spec.plant_no == "CLI3", Spec.item == "CLIOK")
        ).scalar_one_or_none()
        assert ok_spec is not None
        bad_spec = fresh.execute(
            select(Spec).where(Spec.plant_no == "CLI3", Spec.item == "pH1")
        ).scalar_one_or_none()
        assert bad_spec is None
    finally:
        fresh.close()


def test_cli_missing_file_reports_error():
    result = _run_cli("/tmp/definitely_does_not_exist_load_user_data.csv")
    assert result.returncode == 1
    assert "找不到檔案" in result.stdout


def test_cli_idempotent_rerun(b_db, tmp_path):
    path = tmp_path / "主表.csv"
    _write_csv(path, [_row("CLI4", "CLIITEM4", unit="mg/L", oos="100", tag="CLI4.I4.PV")])

    r1 = _run_cli(path)
    assert r1.returncode == 0
    r2 = _run_cli(path)
    assert r2.returncode == 0
    assert "新增 0 筆、沿用既有 1 筆" in r2.stdout

    fresh = BSessionLocal()
    try:
        plants = fresh.execute(select(Plant).where(Plant.plant_no == "CLI4")).scalars().all()
        specs = fresh.execute(select(Spec).where(Spec.plant_no == "CLI4")).scalars().all()
        assert len(plants) == 1
        assert len(specs) == 1
    finally:
        fresh.close()


def test_cli_missing_required_column_reports_structural_error(tmp_path):
    path = tmp_path / "主表.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["廠區代號", "項目"])  # 缺 類型/資料來源 等必要欄
        writer.writerow(["K7", "CODZ"])

    result = _run_cli(path)
    assert result.returncode == 1
    assert "缺少必要欄位" in result.stdout
