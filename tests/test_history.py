import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import date
from schemas.history_schema import ReasonUpdate
from services.history_service import (
    default_date_range,
    validate_date_range,
    align_to_5min,
    classify_msg,
)


# ── 預設日期範圍 ─────────────────────────────────────────────────────────────
def test_default_date_range():
    sdate, edate = default_date_range()
    today = date.today()
    assert sdate == today.strftime("%Y/%m/01")
    assert edate == today.strftime("%Y/%m/%d")
    assert sdate <= edate


# ── 日期範圍驗證 ─────────────────────────────────────────────────────────────
def test_validate_date_range_ok():
    validate_date_range("2024/06/01", "2024/06/21")  # 不應 raise


def test_validate_date_range_same_day():
    validate_date_range("2024/06/15", "2024/06/15")  # 同日合法


def test_validate_date_range_fail():
    with pytest.raises(ValueError, match="不可大於"):
        validate_date_range("2024/06/21", "2024/06/01")


# ── 5 分鐘邊界對齊 ───────────────────────────────────────────────────────────
def test_align_to_5min_already_aligned():
    assert align_to_5min("2024/06/20 14:35") == "2024/06/20 14:35"


def test_align_to_5min_rounds_down():
    assert align_to_5min("2024/06/20 14:37") == "2024/06/20 14:35"
    assert align_to_5min("2024/06/20 09:59") == "2024/06/20 09:55"
    assert align_to_5min("2024/06/20 00:01") == "2024/06/20 00:00"


def test_align_to_5min_with_seconds():
    assert align_to_5min("2024/06/20 14:37:45") == "2024/06/20 14:35"


def test_align_to_5min_invalid_passthrough():
    # 格式不符時原樣回傳
    assert align_to_5min("not-a-date") == "not-a-date"


# ── 異常訊息分類（決定回覆 mail 類型）───────────────────────────────────────
def test_classify_msg_normal():
    assert classify_msg("VOC 超標") == "normal"
    assert classify_msg("pH 異常") == "normal"


def test_classify_msg_24h():
    assert classify_msg("24H累積雨量超過標準") == "雨水溝"


def test_classify_msg_water():
    assert classify_msg("水質異常 COD 超標") == "水質異常"


def test_classify_msg_divert():
    assert classify_msg("改排水 pH 紀錄") == "改排水"


def test_classify_msg_priority():
    # 24H 優先於水質異常
    assert classify_msg("24H累積雨量 水質異常") == "雨水溝"
    # 水質異常優先於改排水
    assert classify_msg("水質異常 改排水") == "水質異常"


# ── ReasonUpdate schema ──────────────────────────────────────────────────────
def test_reason_update_valid():
    r = ReasonUpdate(logid=42, reason="設備暫停維修，已通報工務")
    assert r.logid == 42
    assert r.reason == "設備暫停維修，已通報工務"


def test_reason_update_trims_whitespace():
    r = ReasonUpdate(logid=1, reason="  原因說明  ")
    assert r.reason == "原因說明"


def test_reason_update_empty_raises():
    with pytest.raises(Exception):
        ReasonUpdate(logid=1, reason="")


def test_reason_update_whitespace_only_raises():
    with pytest.raises(Exception):
        ReasonUpdate(logid=1, reason="   ")
