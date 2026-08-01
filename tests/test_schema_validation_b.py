"""
tests/test_schema_validation_b.py — B 棧 4 頁寫入端點的請求模型驗證（純邏輯，不需 DB）

對應 docs/標準化與待調整清單.md 的 **D5「4 頁 schema 驗證未接線」**：
派送名單／部門權限／ACL／異常回覆四頁的寫入端點原本吃裸的 BaseModel（只有型別、
沒有任何欄位驗證），本次改接 schemas/ 的 B 棧模型。

本檔分三段：
  1. B 棧新模型的「合法輸入通過 / 非法輸入被擋且訊息是繁體中文」。
  2. schemas/field_rules.py 共用小工具的行為。
  3. **A 棧回歸保護**：schemas/ 是兩棧共用檔，本次只「新增」B 棧類別、
     A 棧既有類別一行未改，這裡逐一驗證 A 棧模型行為與改版前完全相同。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pydantic import ValidationError

from schemas.acl_schema import (
    AclUserBase, AclUserCreate, AclUserCreateB, AclUserDeleteB, AclUserUpdate, AclUserUpdateB,
)
from schemas.dept_schema import (
    DeptAdd, DeptAddB, DeptDelete, DeptDeleteB, DeptUpdate, DeptUpdateB,
)
from schemas.field_rules import optional_text, require_choice, require_text
from schemas.history_schema import ReasonUpdate, ReasonUpdateB
from schemas.maillist_schema import (
    MailListAdd, MailListAddB, MailListDelete, MailListDeleteB, MailListUpdate, MailListUpdateB,
)


def _msgs(exc_info) -> str:
    """把 pydantic ValidationError 的所有訊息串起來，方便斷言中文字樣。"""
    return " | ".join(e["msg"] for e in exc_info.value.errors())


# ══════════════════════════════════════════════════════════════════════════
# 1. 派送名單（POST /maillist/add|update|delete）
# ══════════════════════════════════════════════════════════════════════════

def test_maillist_b_valid():
    d = MailListAddB(plantno=" K7 ", rpttype="水質異常", empno=" E001 ",
                     empname="王小明", notesid="Ming Wang", mailtype="TO",
                     mail=True, signgrp=False)
    assert (d.plantno, d.rpttype, d.empno) == ("K7", "水質異常", "E001")   # 已去頭尾空白
    assert d.mail is True and d.signgrp is False


def test_maillist_b_blank_required_fields_rejected():
    for kwargs, expect in (
        ({"plantno": "  "}, "廠區代碼不可為空白"),
        ({"rpttype": ""}, "報表類型不可為空白"),
        ({"empno": "   "}, "工號不可為空白"),
    ):
        base = {"plantno": "K7", "rpttype": "水質異常", "empno": "E001"}
        base.update(kwargs)
        with pytest.raises(ValidationError) as ei:
            MailListAddB(**base)
        assert expect in _msgs(ei)


def test_maillist_b_invalid_mailtype_rejected():
    with pytest.raises(ValidationError) as ei:
        MailListAddB(plantno="K7", rpttype="水質異常", empno="E001", mailtype="BCC")
    assert "派送方式只能是 TO（正本）或 CC（副本）" in _msgs(ei)


def test_maillist_b_over_length_rejected():
    with pytest.raises(ValidationError) as ei:
        MailListAddB(plantno="K" * 51, rpttype="水質異常", empno="E001")
    assert "廠區代碼長度不可超過 50 個字元" in _msgs(ei)

    with pytest.raises(ValidationError) as ei:
        MailListAddB(plantno="K7", rpttype="水質異常", empno="E001", empname="王" * 101)
    assert "姓名長度不可超過 100 個字元" in _msgs(ei)


def test_maillist_b_mail_flag_must_be_boolean():
    """mail/signgrp 在 B 棧是 bool（models_b.MailList.mail_on/sign_grp 是 Boolean）。"""
    d = MailListAddB(plantno="K7", rpttype="水質異常", empno="E001", mail=0, signgrp=1)
    assert d.mail is False and d.signgrp is True
    with pytest.raises(ValidationError):
        MailListAddB(plantno="K7", rpttype="水質異常", empno="E001", mail="要")


def test_maillist_b_mail_on_without_notesid_allowed():
    """★ 刻意維持寬鬆：B 棧新增表單沒有 Notes ID 輸入框（只靠工號自動帶出），
    群組／值班工號查不到 notesid 是正常情況，照搬 A 棧「發信必填 NotesID」會讓這類
    人員完全加不進名單。詳見 schemas/maillist_schema.py 的 B 棧區塊註解。"""
    d = MailListAddB(plantno="K7", rpttype="水質異常", empno="環安群組", mail=True, notesid="")
    assert d.notesid == ""


def test_maillist_b_update_requires_old_empno():
    d = MailListUpdateB(plantno="K7", rpttype="水質異常", empno="E002", old_empno="E001")
    assert d.old_empno == "E001"
    with pytest.raises(ValidationError) as ei:
        MailListUpdateB(plantno="K7", rpttype="水質異常", empno="E002", old_empno="  ")
    assert "原工號" in _msgs(ei)


def test_maillist_b_delete_validates_key_fields():
    d = MailListDeleteB(plantno="K7", rpttype="水質異常", empno="E001")
    assert d.empno == "E001"
    with pytest.raises(ValidationError) as ei:
        MailListDeleteB(plantno="", rpttype="水質異常", empno="E001")
    assert "廠區代碼不可為空白" in _msgs(ei)


# ══════════════════════════════════════════════════════════════════════════
# 2. 部門權限（POST /dept/add|update|delete）
# ══════════════════════════════════════════════════════════════════════════

def test_dept_b_valid():
    d = DeptAddB(plantid=990, deptno="  TESTDEPT  ", remark="備註")
    assert d.deptno == "TESTDEPT"


def test_dept_b_inherits_a_stack_rules():
    """B 版直接繼承 A 棧 DeptAdd，父類別的規則（廠區必選／部門代碼必填）照樣生效。"""
    with pytest.raises(ValidationError) as ei:
        DeptAddB(plantid=0, deptno="TESTDEPT")
    assert "請選擇廠區" in _msgs(ei)

    with pytest.raises(ValidationError) as ei:
        DeptAddB(plantid=990, deptno="   ")
    assert "部門代碼不可為空" in _msgs(ei)


def test_dept_b_adds_length_limit():
    with pytest.raises(ValidationError) as ei:
        DeptAddB(plantid=990, deptno="D" * 51)
    assert "部門代碼長度不可超過 50 個字元" in _msgs(ei)


def test_dept_b_update_and_delete():
    d = DeptUpdateB(plantid=990, old_deptno="OLD", deptno="NEW")
    assert (d.old_deptno, d.deptno) == ("OLD", "NEW")
    with pytest.raises(ValidationError) as ei:
        DeptUpdateB(plantid=990, old_deptno="O" * 51, deptno="NEW")
    assert "原部門代碼" in _msgs(ei)

    assert DeptDeleteB(plantid=990, deptno="TESTDEPT").deptno == "TESTDEPT"
    with pytest.raises(ValidationError) as ei:
        DeptDeleteB(plantid=990, deptno="")
    assert "部門代碼不可為空" in _msgs(ei)


# ══════════════════════════════════════════════════════════════════════════
# 3. ACL 隔離權限（POST /acl/create|update|delete）
# ══════════════════════════════════════════════════════════════════════════

def test_acl_b_valid_and_default_stype():
    d = AclUserCreateB(plantno="TEST1", role_id=3, empno="E001")
    assert d.stype == "3"          # 未帶 stype 時預設全區（與 B 棧前端一致）


@pytest.mark.parametrize("bad_role", [0, 1, 5, 12, 99])
def test_acl_b_rejects_roles_outside_3_and_7(bad_role):
    """D4 記載的缺口：舊 B 棧端點任何 role_id 都寫得進 acl_user_role（DB 也沒 FK 擋）。"""
    with pytest.raises(ValidationError) as ei:
        AclUserCreateB(plantno="TEST1", role_id=bad_role, empno="E001", stype="3")
    assert "roleid 只能是" in _msgs(ei)


def test_acl_b_rejects_bad_stype_and_blank_fields():
    with pytest.raises(ValidationError) as ei:
        AclUserCreateB(plantno="TEST1", role_id=3, empno="E001", stype="9")
    assert "stype 只能是" in _msgs(ei)

    with pytest.raises(ValidationError) as ei:
        AclUserCreateB(plantno="   ", role_id=3, empno="E001")
    assert "廠區不可為空" in _msgs(ei)      # 父類別 AclUserBase 的既有訊息

    with pytest.raises(ValidationError) as ei:
        AclUserCreateB(plantno="TEST1", role_id=3, empno="E" * 51)
    assert "工號長度不可超過 50 個字元" in _msgs(ei)


def test_acl_b_update_old_stype_optional():
    """B 棧前端不一定帶得出 old_stype（僅供 tranlog 記錄），故放寬為選填。"""
    d = AclUserUpdateB(plantno="TEST1", role_id=3, empno="E002", old_empno="E001", stype="1")
    assert d.old_stype == ""
    with pytest.raises(ValidationError) as ei:
        AclUserUpdateB(plantno="TEST1", role_id=3, empno="E002", old_empno="  ", stype="1")
    assert "原工號" in _msgs(ei)


def test_acl_b_delete_needs_no_stype():
    d = AclUserDeleteB(plantno="TEST1", role_id=7, empno="E001")
    assert d.role_id == 7
    with pytest.raises(ValidationError) as ei:
        AclUserDeleteB(plantno="TEST1", role_id=99, empno="E001")
    assert "roleid 只能是" in _msgs(ei)
    with pytest.raises(ValidationError) as ei:
        AclUserDeleteB(plantno="TEST1", role_id=3, empno="")
    assert "工號不可為空白" in _msgs(ei)


# ══════════════════════════════════════════════════════════════════════════
# 4. 異常回覆（POST /history/reply）
# ══════════════════════════════════════════════════════════════════════════

def test_reason_b_valid():
    d = ReasonUpdateB(item_id="12||Cu||OOS", reason="  設備校正誤差，已處理  ")
    assert d.item_id == "12||Cu||OOS"
    assert d.reason == "設備校正誤差，已處理"      # 去頭尾空白


def test_reason_b_blank_reason_rejected():
    with pytest.raises(ValidationError) as ei:
        ReasonUpdateB(item_id="12||Cu||OOS", reason="   ")
    assert "原因說明不可為空白" in _msgs(ei)


def test_reason_b_blank_item_id_rejected():
    with pytest.raises(ValidationError) as ei:
        ReasonUpdateB(item_id="", reason="有填原因")
    assert "回覆對象（item_id）不可為空白" in _msgs(ei)


def test_reason_b_long_reason_allowed():
    """原因說明刻意不設長度上限（reply_reason 是 Text，業務上也沒有字數約定）。"""
    d = ReasonUpdateB(item_id="12||Cu||OOS", reason="長" * 5000)
    assert len(d.reason) == 5000


# ══════════════════════════════════════════════════════════════════════════
# 5. schemas/field_rules.py 共用小工具
# ══════════════════════════════════════════════════════════════════════════

def test_require_text_rules():
    assert require_text("  abc ", "測試欄位", 10) == "abc"
    with pytest.raises(ValueError, match="測試欄位不可為空白"):
        require_text("   ", "測試欄位", 10)
    with pytest.raises(ValueError, match="測試欄位長度不可超過 3 個字元"):
        require_text("abcd", "測試欄位", 3)


def test_optional_text_rules():
    assert optional_text(None, "備註", 10) == ""
    assert optional_text("  ok ", "備註", 10) == "ok"
    with pytest.raises(ValueError, match="備註長度不可超過 2 個字元"):
        optional_text("abc", "備註", 2)


def test_require_choice_rules():
    assert require_choice(" TO ", "派送方式", ("TO", "CC")) == "TO"
    with pytest.raises(ValueError, match="派送方式只能是 TO、CC"):
        require_choice("BCC", "派送方式", ("TO", "CC"))
    with pytest.raises(ValueError, match="派送方式只能是 正本或副本"):
        require_choice("BCC", "派送方式", ("TO", "CC"), "正本或副本")


# ══════════════════════════════════════════════════════════════════════════
# 6. ★ A 棧回歸保護：schemas/ 是兩棧共用，A 棧既有模型行為必須逐字元不變
# ══════════════════════════════════════════════════════════════════════════

def test_a_stack_maillist_unchanged():
    # A 棧仍是 int 旗標 + SM/cellphone 欄位
    d = MailListAdd(plantno="K7", rpttype="水質異常", empno="E001",
                    notesid="Ming_Wang", mailtype="TO", mail=1, SM=0)
    assert d.mail == 1 and d.SM == 0 and d.cellphone == ""

    # A 棧「發信必填 NotesID」規則仍在（B 棧刻意不套用，兩者互不影響）
    with pytest.raises(ValidationError) as ei:
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001", mail=1, notesid="")
    assert "勾選發送 Email 時，Notes ID 不可為空!" in _msgs(ei)

    # A 棧的 mailtype 錯誤訊息未被改寫
    with pytest.raises(ValidationError) as ei:
        MailListAdd(plantno="K7", rpttype="水質異常", empno="E001", notesid="A_B", mailtype="BCC")
    assert "派送方式只能是 TO 或 CC" in _msgs(ei)

    # A 棧沒有長度上限（超長字串照舊放行，不因本次改動開始 422）
    long_ok = MailListAdd(plantno="K" * 200, rpttype="水質異常", empno="E001", notesid="A_B")
    assert len(long_ok.plantno) == 200

    # A 棧 MailListUpdate/Delete 形狀不變
    assert MailListUpdate(plantno="K7", rpttype="水質異常", empno="E002",
                          old_empno="E001", notesid="A_B", mail=1).old_empno == "E001"
    assert MailListDelete(plantno="K7", rpttype="水質異常", empno="E001").empno == "E001"


def test_a_stack_dept_unchanged():
    assert DeptAdd(plantid=5, deptno="  1234  ").deptno == "1234"
    with pytest.raises(ValidationError) as ei:
        DeptAdd(plantid=0, deptno="1234")
    assert "請選擇廠區!" in _msgs(ei)
    # A 棧沒有長度上限
    assert len(DeptAdd(plantid=5, deptno="D" * 200).deptno) == 200
    assert DeptUpdate(plantid=5, old_deptno="1234", deptno="5678").deptno == "5678"
    assert DeptDelete(plantid=5, deptno="1234").deptno == "1234"


def test_a_stack_acl_unchanged():
    d = AclUserCreate(role_id=3, plantno="K1", empno="E001", stype="1")
    assert d.stype == "1"
    # A 棧 AclUserCreate 的 stype 仍是**必填**（B 棧才有預設值 '3'）
    with pytest.raises(ValidationError):
        AclUserCreate(role_id=3, plantno="K1", empno="E001")
    # A 棧 AclUserUpdate 的 old_stype 仍是必填（B 棧才放寬為選填）
    with pytest.raises(ValidationError):
        AclUserUpdate(role_id=3, plantno="K1", empno="E002", stype="1", old_empno="E001")
    # A 棧 /acl/delete 用的 AclUserBase 形狀不變（含 stype）
    assert AclUserBase(role_id=3, plantno="K1", empno="E001", stype="2").stype == "2"
    # A 棧沒有長度上限
    assert len(AclUserCreate(role_id=3, plantno="K" * 200, empno="E001", stype="1").plantno) == 200


def test_a_stack_reason_update_unchanged():
    r = ReasonUpdate(logid=42, reason="  設備暫停維修  ")
    assert r.logid == 42 and r.reason == "設備暫停維修"
    with pytest.raises(ValidationError) as ei:
        ReasonUpdate(logid=1, reason="   ")
    assert "原因說明不可為空白" in _msgs(ei)
