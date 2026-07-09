import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.context import MigrationContext, PersonnelBinding, Person
from migration.normalize.personnel import build_personnel
from models_b import Employee, SignEmp, MailList, AclUserRole


def _make_ctx() -> MigrationContext:
    """1 位申請人 + 2 位簽核人。"""
    applicant = Person(empno="A001", name="王小明", email="Wang_Xiao_Ming@aseglobal.com")
    signer1 = Person(empno="S001", name="陳大明", email="Da_Ming_Chen@aseglobal.com")
    signer2 = Person(empno="S002", name="李小華", email="Xiao_Hua_Li@aseglobal.com")
    binding = PersonnelBinding(applicants=[applicant], signers=[signer1, signer2])
    return MigrationContext(personnel=binding, now=datetime.now(timezone.utc))


PLANT_NOS = ["K7", "K8"]


def test_employee_has_all_people_with_notes_id_reversed_from_email():
    ctx = _make_ctx()
    result = build_personnel(ctx, PLANT_NOS)
    employees = result["employee"]

    assert len(employees) == 3
    for emp in employees:
        assert isinstance(emp, Employee)

    by_empno = {e.emp_no: e for e in employees}
    assert by_empno["A001"].emp_name == "王小明"
    assert by_empno["S001"].notes_id == "Da Ming Chen"
    assert by_empno["S002"].notes_id == "Xiao Hua Li"
    # dept_no/is_leave 依規則固定
    for emp in employees:
        assert emp.dept_no is None
        assert emp.is_leave is False


def test_sign_emp_has_deterministic_emp_id():
    ctx = _make_ctx()
    result = build_personnel(ctx, PLANT_NOS)
    sign_emps = result["sign_emp"]

    assert len(sign_emps) == 3
    for se in sign_emps:
        assert isinstance(se, SignEmp)

    emp_ids = [se.emp_id for se in sign_emps]
    assert emp_ids == [900001, 900002, 900003]

    by_emp_id = {se.emp_id: se for se in sign_emps}
    assert by_emp_id[900001].emp_no == "A001"
    assert by_emp_id[900002].emp_no == "S001"
    assert by_emp_id[900003].emp_no == "S002"
    assert by_emp_id[900002].email == "Da_Ming_Chen@aseglobal.com"


def test_sign_emp_id_is_stable_across_reruns():
    """merge 冪等：同樣的 ctx/plant_nos 重跑一次，emp_id 應完全相同（不重複插入）。"""
    ctx = _make_ctx()
    result1 = build_personnel(ctx, PLANT_NOS)
    result2 = build_personnel(ctx, PLANT_NOS)

    ids1 = [se.emp_id for se in result1["sign_emp"]]
    ids2 = [se.emp_id for se in result2["sign_emp"]]
    assert ids1 == ids2


def test_mail_list_count_and_sign_grp_flags():
    ctx = _make_ctx()
    result = build_personnel(ctx, PLANT_NOS)
    mail_list = result["mail_list"]

    n_signers = len(ctx.personnel.signers)         # 2
    n_iso = len(ctx.isolation_sign_rpttypes)       # 2（水保養中/空保養中）
    n_dispatch = len(ctx.dispatch_rpttypes)        # 14（派報收件人）
    per_plant = n_iso + 1 + n_dispatch             # + 1 水質異常
    # 2 簽核人 × 2 廠 × (2 隔離 + 1 水質異常 + 14 派報)
    assert len(mail_list) == n_signers * len(PLANT_NOS) * per_plant
    for ml in mail_list:
        assert isinstance(ml, MailList)
        assert ml.mail_type == "TO"
        assert ml.mail_on is True

    isolation_rows = [ml for ml in mail_list if ml.rpttype in ctx.isolation_sign_rpttypes]
    water_rows = [ml for ml in mail_list if ml.rpttype == ctx.water_dispatch_rpttype]
    dispatch_rows = [ml for ml in mail_list if ml.rpttype in ctx.dispatch_rpttypes]

    # 只有隔離簽核名單 sign_grp=True，其餘（水質異常/派報）皆 False
    assert len(isolation_rows) == n_signers * len(PLANT_NOS) * n_iso
    assert all(ml.sign_grp is True for ml in isolation_rows)
    assert len(water_rows) == n_signers * len(PLANT_NOS)
    assert all(ml.sign_grp is False for ml in water_rows)
    assert len(dispatch_rows) == n_signers * len(PLANT_NOS) * n_dispatch
    assert all(ml.sign_grp is False for ml in dispatch_rows)

    # 每個簽核人在每個廠都齊全所有 rpttype
    expected_rpttypes = set(ctx.isolation_sign_rpttypes) | {ctx.water_dispatch_rpttype} | set(ctx.dispatch_rpttypes)
    for plant_no in PLANT_NOS:
        for empno in {"S001", "S002"}:
            rpttypes = {
                ml.rpttype for ml in mail_list
                if ml.plant_no == plant_no and ml.emp_no == empno
            }
            assert rpttypes == expected_rpttypes


def test_acl_user_role_count_and_fields():
    ctx = _make_ctx()
    result = build_personnel(ctx, PLANT_NOS)
    acl_rows = result["acl_user_role"]

    # 2 簽核人 × 2 廠 = 4
    assert len(acl_rows) == 4
    for row in acl_rows:
        assert isinstance(row, AclUserRole)
        assert row.role_id == 3
        assert row.stype == "user"
        assert row.dept_no is None

    empno_plant_pairs = {(row.emp_no, row.plant_no) for row in acl_rows}
    assert empno_plant_pairs == {
        ("S001", "K7"), ("S001", "K8"),
        ("S002", "K7"), ("S002", "K8"),
    }


def test_applicants_excluded_from_mail_list_and_acl_user_role():
    ctx = _make_ctx()
    result = build_personnel(ctx, PLANT_NOS)

    applicant_empnos = {p.empno for p in ctx.personnel.applicants}
    assert applicant_empnos == {"A001"}

    mail_list_empnos = {ml.emp_no for ml in result["mail_list"]}
    acl_empnos = {row.emp_no for row in result["acl_user_role"]}

    assert applicant_empnos.isdisjoint(mail_list_empnos)
    assert applicant_empnos.isdisjoint(acl_empnos)

    # 但申請人仍要出現在 employee / sign_emp
    employee_empnos = {e.emp_no for e in result["employee"]}
    sign_emp_empnos = {se.emp_no for se in result["sign_emp"]}
    assert applicant_empnos.issubset(employee_empnos)
    assert applicant_empnos.issubset(sign_emp_empnos)
