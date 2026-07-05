"""
tests/test_sync_pure.py — services_b.sync_service.classify_reading 純邏輯測試（不依賴 DB）

涵蓋 docs/PhaseA執行規格書.md 第三節「讀值分類規則」全部分支，
以及使用者要求的容錯情境：全形字元、前後空白、'<' 各種變體、負數、非數字防呆。
"""

from decimal import Decimal

from services_b.sync_service import classify_reading


# ── quality=good 且合法數字 → normal ──────────────────────────────────────

def test_normal_integer():
    assert classify_reading("7", "good") == (Decimal("7"), "normal")


def test_normal_decimal():
    assert classify_reading("7.20", "good") == (Decimal("7.20"), "normal")


def test_normal_negative_number():
    """負數防呆：負值本身是合法讀值（例如溫度校正值），不應被誤判為錯誤。"""
    assert classify_reading("-1.5", "good") == (Decimal("-1.5"), "normal")


def test_normal_zero():
    assert classify_reading("0", "good") == (Decimal("0"), "normal")


def test_normal_with_whitespace():
    assert classify_reading("  7.20  ", "good") == (Decimal("7.20"), "normal")


def test_normal_fullwidth_digits_and_period():
    """全形數字＋全形句點容錯：'５．００' → 5.00。"""
    value, status = classify_reading("５．００", "good")
    assert status == "normal"
    assert value == Decimal("5.00")


# ── quality=good 且 value='N.D' → nd ──────────────────────────────────────

def test_nd_basic():
    assert classify_reading("N.D", "good") == (None, "nd")


def test_nd_lowercase():
    assert classify_reading("n.d", "good") == (None, "nd")


def test_nd_fullwidth():
    """全形 'Ｎ．Ｄ' 容錯後應等同 'N.D'。"""
    assert classify_reading("Ｎ．Ｄ", "good") == (None, "nd")


def test_nd_with_whitespace():
    assert classify_reading("  N.D  ", "good") == (None, "nd")


# ── quality=good 且 value='<X' → below_lod ────────────────────────────────

def test_below_lod_basic():
    assert classify_reading("<0.05", "good") == (Decimal("0.05"), "below_lod")


def test_below_lod_other_thresholds():
    assert classify_reading("<0.02", "good") == (Decimal("0.02"), "below_lod")
    assert classify_reading("<0.01", "good") == (Decimal("0.01"), "below_lod")


def test_below_lod_fullwidth_lessthan():
    """全形 '＜' 容錯：＜０．０５ → below_lod, 0.05。"""
    value, status = classify_reading("＜０．０５", "good")
    assert status == "below_lod"
    assert value == Decimal("0.05")


def test_below_lod_with_space_after_lt():
    assert classify_reading("< 0.05", "good") == (Decimal("0.05"), "below_lod")


def test_below_lod_invalid_number_is_error():
    """'<' 後面接非數字：無法解析為門檻值，視為 error 而非硬解析成 0。"""
    assert classify_reading("<abc", "good") == (None, "error")


# ── quality=good 但 value 空/無法解析 → error（使用者已知陷阱）───────────

def test_error_empty_string():
    assert classify_reading("", "good") == (None, "error")


def test_error_none_value():
    assert classify_reading(None, "good") == (None, "error")


def test_error_whitespace_only():
    assert classify_reading("   ", "good") == (None, "error")


def test_error_fullwidth_whitespace_only():
    """全形空白（U+3000）視同空值。"""
    assert classify_reading("　　", "good") == (None, "error")


def test_error_non_numeric_text():
    """非數字防呆：既非 N.D、也非 '<X'、也不是合法數字 → error。"""
    assert classify_reading("abc", "good") == (None, "error")
    assert classify_reading("斷訊", "good") == (None, "error")  # quality=good 但 value 混入異常字串


# ── quality != good → broken（value 內容不重要）───────────────────────────

def test_broken_quality_bad():
    assert classify_reading("1.20", "bad") == (None, "broken")


def test_broken_quality_bad_even_with_nd_value():
    assert classify_reading("N.D", "bad") == (None, "broken")


def test_broken_quality_empty():
    assert classify_reading("7.2", "") == (None, "broken")


def test_broken_quality_none():
    assert classify_reading("7.2", None) == (None, "broken")


def test_broken_quality_case_insensitive_good_still_accepted():
    """quality 大小寫容錯：'Good'/'GOOD' 視同 good。"""
    assert classify_reading("7.2", "Good") == (Decimal("7.2"), "normal")
    assert classify_reading("7.2", "GOOD") == (Decimal("7.2"), "normal")
