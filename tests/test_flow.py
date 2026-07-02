import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.flow_service import (
    FlowStatus,
    Ttype,
    Utype,
    SIGN_ACTION_APPROVE,
    SIGN_ACTION_REJECT,
    FRULEID_ISOLATION,
    build_rtype_list,
    resolve_new_status,
)


# ── FlowStatus 數值正確性（legacy/MTFlowBase.cs FlowStatus enum 真實數值）───────

def test_flow_status_values():
    """
    對應 legacy/MTFlowBase.cs：
        待簽核=0, 簽核中=1, 核准=7, 否決=8, 取消=12
    修法前 Python 端把「核准」誤寫死成 3，是資料正確性 bug（見 docs/legacy_source_analysis.md）。
    """
    assert int(FlowStatus.待簽核) == 0
    assert int(FlowStatus.簽核中) == 1
    assert int(FlowStatus.核准) == 7
    assert int(FlowStatus.否決) == 8
    assert int(FlowStatus.取消) == 12

def test_sign_action_ids():
    """ MTFlowBase.SignAction enum：核准=1, 否決=9（取消=8 舊系統已停用不提供）"""
    assert SIGN_ACTION_APPROVE == 1
    assert SIGN_ACTION_REJECT == 9

def test_ttype_utype_values():
    """ dbVOC.cs Ttype / Utype enum """
    assert int(Ttype.新增) == 1
    assert int(Ttype.修改隔離區間) == 2
    assert int(Utype.新增) == 1
    assert int(Utype.送簽) == 2
    assert int(Utype.修改隔離區間) == 3

def test_fruleid_isolation():
    """ dbVOC.cs 簽核流程 enum：法遵平台_隔離廠區項目維護 = 8 """
    assert FRULEID_ISOLATION == 8


# ── rtype 組字（build_rtype_list）───────────────────────────────────────────

def test_build_rtype_list_pure_water_items():
    """ 純水項目一律歸類「水保養中」 """
    assert build_rtype_list(["pH", "COD", "SS"]) == ["水保養中"]

def test_build_rtype_list_pure_voc_items():
    """ 含 VOC 字樣的項目歸類「空保養中」 """
    assert build_rtype_list(["VOC", "VOC2"]) == ["空保養中"]

def test_build_rtype_list_mixed_items():
    """ 混合水/VOC 項目，依出現順序去重，各出現一次 """
    assert build_rtype_list(["pH", "VOC", "COD"]) == ["水保養中", "空保養中"]

def test_build_rtype_list_voc_first():
    """ 混合但 VOC 先出現時，順序應為 空保養中 -> 水保養中 """
    assert build_rtype_list(["VOC", "pH"]) == ["空保養中", "水保養中"]

def test_build_rtype_list_empty():
    assert build_rtype_list([]) == []


# ── 簽核結案的狀態轉移（resolve_new_status）──────────────────────────────────

def test_resolve_new_status_approve():
    """ actionid=1（核准）-> FlowStatus.核准(7) """
    assert resolve_new_status(SIGN_ACTION_APPROVE) == FlowStatus.核准
    assert int(resolve_new_status(SIGN_ACTION_APPROVE)) == 7

def test_resolve_new_status_reject():
    """ actionid=9（否決）-> FlowStatus.否決(8) """
    assert resolve_new_status(SIGN_ACTION_REJECT) == FlowStatus.否決
    assert int(resolve_new_status(SIGN_ACTION_REJECT)) == 8

def test_resolve_new_status_unknown_defaults_to_reject():
    """
    VOC 只有核准(1)/否決(9) 兩種動作；任何非核准的 actionid 一律視為否決，
    避免未知動作意外被當成核准通過（安全預設）。
    """
    assert resolve_new_status(999) == FlowStatus.否決
