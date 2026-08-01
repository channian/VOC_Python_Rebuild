"""
test_basedata_category.py — 基礎資料維護「項目類型」(item.category) 純邏輯測試

只 import services_b.basedata_service（該檔僅相依 models_b，不會連 DB），
涵蓋 normalize_item_category() 的驗證/正規化行為，以及與一次性載入器
scripts/load_user_data.py 的 ITEM_TYPES 常數是否同步。

背景：category 取代舊的「靠項目名稱字串猜類型」（`"VOC" in item` 當空汙），
新廠若有不叫 VOC 的空汙項目會被誤判成水質，見 models_b.Item.category。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services_b.basedata_service import ITEM_CATEGORY_CHOICES, normalize_item_category


# ── 合法值 ────────────────────────────────────────────────────────────────
def test_choices_are_the_three_known_types():
    assert ITEM_CATEGORY_CHOICES == ["水質", "空汙", "雨水溝"]


def test_choices_reuse_category_util_single_source():
    """寫入端（本頁）能存的值，必須與讀取端 services/category_util.py 認得的值同源，
    否則會出現「網頁存得進去、判斷邏輯卻不認得」的死角。"""
    from services.category_util import VALID_CATEGORIES
    assert ITEM_CATEGORY_CHOICES == list(VALID_CATEGORIES)


def test_choices_match_loader_item_types():
    """網頁能存的類型必須與載入器 scripts/load_user_data.py 的 ITEM_TYPES 完全一致，
    否則同一個欄位會出現「網頁存得進、載入器擋下來」（或反之）的分岔。"""
    from scripts.load_user_data import ITEM_TYPES
    assert list(ITEM_TYPES) == ITEM_CATEGORY_CHOICES


@pytest.mark.parametrize("value", ["水質", "空汙", "雨水溝"])
def test_valid_categories_pass_through(value):
    assert normalize_item_category(value) == value


def test_whitespace_is_stripped():
    assert normalize_item_category("  空汙 ") == "空汙"


# ── 未指定（允許留空，與 category 欄位加入前的既有資料相容）──────────────────
def test_none_stays_none():
    assert normalize_item_category(None) is None


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_becomes_none(blank):
    assert normalize_item_category(blank) is None


# ── 非法值要擋下並給清楚訊息 ───────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["空氣污染", "廢水", "VOC", "water", "雨水"])
def test_invalid_category_rejected(bad):
    with pytest.raises(ValueError) as e:
        normalize_item_category(bad)
    msg = str(e.value)
    assert "項目類型錯誤" in msg
    assert "水質/空汙/雨水溝" in msg   # 訊息要把合法值列給使用者看
    assert bad in msg                  # 也要回報使用者實際填了什麼


def test_invalid_category_is_case_and_space_sensitive_inside():
    """字串中間有空白不算合法值（避免「空 汙」這種看起來對、比對卻不同的值悄悄寫進 DB）。"""
    with pytest.raises(ValueError):
        normalize_item_category("空 汙")
