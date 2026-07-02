import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import date

from services.report_service import (
    build_summary,
    build_pivot,
    build_ranking,
    default_date_range,
    validate_date_range,
)


def _row(plantno, item):
    return {"plantno": plantno, "item": item, "cdatetime": "2026/07/01 08:00", "logid": 1}


# ── build_summary ────────────────────────────────────────────────────────────
def test_build_summary_empty():
    assert build_summary([]) == []


def test_build_summary_aggregates_by_plant():
    rows = [_row("K1", "COD"), _row("K1", "pH"), _row("K9", "COD")]
    result = build_summary(rows)
    assert result == [
        {"plantno": "K1", "count": 2, "pct": 100.0},
        {"plantno": "K9", "count": 1, "pct": 50.0},
    ]


def test_build_summary_ties_sorted_by_plantno():
    rows = [_row("K9", "COD"), _row("K1", "COD")]
    result = build_summary(rows)
    # 件數相同 -> 依廠區代碼排序
    assert [r["plantno"] for r in result] == ["K1", "K9"]
    assert all(r["pct"] == 100.0 for r in result)


def test_build_summary_single_row_pct_is_100():
    rows = [_row("K1", "COD")]
    result = build_summary(rows)
    assert result == [{"plantno": "K1", "count": 1, "pct": 100.0}]


# ── build_pivot ───────────────────────────────────────────────────────────────
def test_build_pivot_empty():
    assert build_pivot([]) == {"columns": [], "rows": []}


def test_build_pivot_single_plant():
    rows = [_row("K1", "COD"), _row("K1", "COD"), _row("K1", "pH")]
    result = build_pivot(rows)
    assert result["columns"] == ["K1", "Total"]
    # 依 item 字母序排列，最後補「總計」列
    assert result["rows"] == [
        {"item": "COD", "K1": 2, "Total": 2},
        {"item": "pH", "K1": 1, "Total": 1},
        {"item": "總計", "K1": 3, "Total": 3},
    ]


def test_build_pivot_multi_plant_multi_item():
    rows = [
        _row("K1", "COD"), _row("K1", "COD"), _row("K1", "pH"),
        _row("K9", "COD"),
    ]
    result = build_pivot(rows)
    assert result["columns"] == ["K1", "K9", "Total"]

    by_item = {r["item"]: r for r in result["rows"]}
    assert by_item["COD"] == {"item": "COD", "K1": 2, "K9": 1, "Total": 3}
    # K9 沒有 pH 異常紀錄 -> 缺格補 0，不留空白
    assert by_item["pH"] == {"item": "pH", "K1": 1, "K9": 0, "Total": 1}
    assert by_item["總計"] == {"item": "總計", "K1": 3, "K9": 1, "Total": 4}


def test_build_pivot_missing_cell_filled_zero():
    rows = [_row("K1", "COD"), _row("K9", "pH")]
    result = build_pivot(rows)
    by_item = {r["item"]: r for r in result["rows"]}
    assert by_item["COD"]["K9"] == 0
    assert by_item["pH"]["K1"] == 0


# ── build_ranking ─────────────────────────────────────────────────────────────
def test_build_ranking_empty():
    assert build_ranking([]) == {"rows": [], "max_rank": 0}


def test_build_ranking_no_ties():
    rows = [_row("K1", "COD")] * 3 + [_row("K9", "COD")] * 1
    result = build_ranking(rows)
    assert result["rows"] == [
        {"plantno": "K1", "count": 3, "rank": 1},
        {"plantno": "K9", "count": 1, "rank": 2},
    ]
    assert result["max_rank"] == 2


def test_build_ranking_tied_ranks_use_dense_rank():
    # K1=5, K9=5, K14B=3 -> DENSE_RANK: 1,1,2（並列同名次，下一名次不跳號）
    rows = (
        [_row("K1", "COD")] * 5
        + [_row("K9", "COD")] * 5
        + [_row("K14B", "COD")] * 3
    )
    result = build_ranking(rows)
    ranks = {r["plantno"]: r["rank"] for r in result["rows"]}
    assert ranks["K1"] == 1
    assert ranks["K9"] == 1
    assert ranks["K14B"] == 2
    assert result["max_rank"] == 2


def test_build_ranking_all_tied():
    rows = [_row("K1", "COD"), _row("K9", "COD"), _row("K14B", "COD")]
    result = build_ranking(rows)
    assert all(r["rank"] == 1 for r in result["rows"])
    assert result["max_rank"] == 1


# ── 日期預設 / 驗證（沿用 history_service，經 report_service re-export）───────
def test_default_date_range():
    sdate, edate = default_date_range()
    today = date.today()
    assert sdate == today.strftime("%Y/%m/01")
    assert edate == today.strftime("%Y/%m/%d")


def test_validate_date_range_ok():
    validate_date_range("2026/07/01", "2026/07/02")  # 不應 raise


def test_validate_date_range_fail():
    with pytest.raises(ValueError, match="不可大於"):
        validate_date_range("2026/07/02", "2026/07/01")
