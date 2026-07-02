"""
test_dept.py — 部門權限維護（EditDeptList）純邏輯測試

只 import services/schemas（不 import routers/database，環境無 ODBC 連不上真實 DB）。
涵蓋：schema 驗證、plantid=29 ALL 語意、VOC_tranlog 斜線串格式。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.dept_schema import DeptAdd, DeptUpdate, DeptDelete
from services.dept_service import is_all_plant, _tranlog_str, ALL_PLANT_ID


# ── plantid=29 ALL 全廠語意 ────────────────────────────────────────────────
def test_all_plant_id_is_29():
    assert ALL_PLANT_ID == 29


def test_is_all_plant_true_for_29():
    assert is_all_plant(29) is True
    assert is_all_plant("29") is True   # 表單傳字串也要能判斷


def test_is_all_plant_false_for_specific_plant():
    assert is_all_plant(5) is False
    assert is_all_plant("K7") is False  # 非數字（誤傳 plantno 字串）不可誤判


def test_is_all_plant_handles_invalid_input():
    assert is_all_plant(None) is False
    assert is_all_plant("") is False


# ── VOC_tranlog 斜線串格式（databefore/dataafter = plantno/deptno/deptname）─
def test_tranlog_str_format():
    assert _tranlog_str("K7", "1234", "品保部") == "K7/1234/品保部"


def test_tranlog_str_handles_missing_fields():
    # 舊版刪除時 dataafter="" 整串為空，新增時 databefore="" 整串為空
    assert _tranlog_str("", "", "") == "//"
    assert _tranlog_str("K7", "1234", None) == "K7/1234/"


# ── schema 驗證：DeptAdd ─────────────────────────────────────────────────
def test_dept_add_valid():
    d = DeptAdd(plantid=5, deptno="1234")
    assert d.plantid == 5
    assert d.deptno == "1234"
    assert d.remark == ""


def test_dept_add_all_plant_valid():
    d = DeptAdd(plantid=29, deptno="1234")
    assert d.plantid == 29


def test_dept_add_requires_plantid():
    with pytest.raises(Exception):
        DeptAdd(plantid=0, deptno="1234")


def test_dept_add_requires_deptno():
    with pytest.raises(Exception):
        DeptAdd(plantid=5, deptno="")
    with pytest.raises(Exception):
        DeptAdd(plantid=5, deptno="   ")


def test_dept_add_trims_deptno():
    d = DeptAdd(plantid=5, deptno="  1234  ")
    assert d.deptno == "1234"


# ── schema 驗證：DeptUpdate ──────────────────────────────────────────────
def test_dept_update_requires_old_deptno():
    d = DeptUpdate(plantid=5, old_deptno="1234", deptno="5678")
    assert d.old_deptno == "1234"
    assert d.deptno == "5678"
    with pytest.raises(Exception):
        DeptUpdate(plantid=5, old_deptno="  ", deptno="5678")


def test_dept_update_requires_plantid():
    with pytest.raises(Exception):
        DeptUpdate(plantid=0, old_deptno="1234", deptno="5678")


def test_dept_update_requires_new_deptno():
    with pytest.raises(Exception):
        DeptUpdate(plantid=5, old_deptno="1234", deptno="")


# ── schema 驗證：DeptDelete ──────────────────────────────────────────────
def test_dept_delete_valid():
    d = DeptDelete(plantid=5, deptno="1234")
    assert d.deptno == "1234"


def test_dept_delete_requires_plantid():
    with pytest.raises(Exception):
        DeptDelete(plantid=0, deptno="1234")
