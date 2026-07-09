"""
migration/normalize/personnel.py — A→B 搬遷「人員綁定」：A 棧真人完全不搬，
改由 ctx.personnel（migration_personnel.json 讀入）產生 B 端 employee/sign_emp/
mail_list/acl_user_role，讓使用者用自己部門同事測簽核與派報。

契約（見 migration/normalize/__init__.py）：
    build_personnel(ctx, plant_nos) -> dict[str, list]
        {"employee": [...], "sign_emp": [...], "mail_list": [...], "acl_user_role": [...]}
    皆為未 save 的 ORM 物件 list，純函式、不連 DB。

產生規則：
    - employee：ctx.personnel.all_people()（申請人 + 簽核人）每人一列。
    - sign_emp：同上每人一列；emp_id 用確定性顯式值 900001+index
      （index 為 all_people() 序位，從 0 起算）——sign_emp.emp_id 雖是 Identity()
      自增主鍵，但這裡刻意手動指定固定值，讓多次搬遷 merge 冪等、不會重複插入。
    - mail_list：只有簽核人（signers）進，對每個 plant_no 各：
        * ctx.isolation_sign_rpttypes（水保養中／空保養中）各一列，sign_grp=True
          （隔離簽核名單，這個旗標是 flow_service 找簽核人的關鍵）。
        * ctx.water_dispatch_rpttype（水質異常）一列，sign_grp=False
          （派報收件人，不是簽核群組）。
      mail_type 一律 'TO'、mail_on 一律 True。
    - acl_user_role：只有簽核人進，每人 × 每個 plant_no 一列，
      role_id=ctx.signer_role_id、stype='user'。
    - 申請人（applicants）只進 employee + sign_emp，不進 mail_list / acl_user_role
      （他們是隔離申請人，不是簽核人／收件人）。
"""

from typing import Dict, List

from migration.context import MigrationContext, Person
from models_b import AclUserRole, Employee, MailList, SignEmp

__all__ = ["build_personnel"]

# sign_emp.emp_id 確定性起始值：刻意避開真實/種子資料可能用到的低位數字
# （seed_test_data.py 用 SignEmp 是靠 Identity() 自增，未手動指定 emp_id）。
_SIGN_EMP_ID_BASE = 900001


def build_personnel(ctx: MigrationContext, plant_nos: List[str]) -> Dict[str, list]:
    """依 ctx.personnel 產生 B 端人員綁定四表（employee/sign_emp/mail_list/acl_user_role）。

    plant_nos 為要掛名單/權限的廠區編號清單（runner 會傳搬入的廠區）。
    """
    all_people: List[Person] = ctx.personnel.all_people()
    signers: List[Person] = ctx.personnel.signers

    employee: List[Employee] = []
    sign_emp: List[SignEmp] = []
    for index, person in enumerate(all_people):
        employee.append(
            Employee(
                emp_no=person.empno,
                emp_name=person.name,
                notes_id=person.notes_id,
                dept_no=None,
                is_leave=False,
            )
        )
        sign_emp.append(
            SignEmp(
                emp_id=_SIGN_EMP_ID_BASE + index,
                emp_no=person.empno,
                emp_name=person.name,
                email=person.email,
                pos_id=None,
                dep_no=None,
            )
        )

    mail_list: List[MailList] = []
    acl_user_role: List[AclUserRole] = []
    for signer in signers:
        for plant_no in plant_nos:
            for rpttype in ctx.isolation_sign_rpttypes:
                mail_list.append(
                    MailList(
                        plant_no=plant_no,
                        rpttype=rpttype,
                        emp_no=signer.empno,
                        emp_name=signer.name,
                        notes_id=signer.notes_id,
                        mail_type="TO",
                        mail_on=True,
                        sign_grp=True,
                    )
                )
            mail_list.append(
                MailList(
                    plant_no=plant_no,
                    rpttype=ctx.water_dispatch_rpttype,
                    emp_no=signer.empno,
                    emp_name=signer.name,
                    notes_id=signer.notes_id,
                    mail_type="TO",
                    mail_on=True,
                    sign_grp=False,
                )
            )
            acl_user_role.append(
                AclUserRole(
                    role_id=ctx.signer_role_id,
                    emp_no=signer.empno,
                    plant_no=plant_no,
                    dept_no=None,
                    stype="user",
                )
            )

    return {
        "employee": employee,
        "sign_emp": sign_emp,
        "mail_list": mail_list,
        "acl_user_role": acl_user_role,
    }
