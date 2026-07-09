"""
migration/context.py — 搬遷共用 context 與人員綁定。

MigrationContext 由 runner 建好後傳給需要它的 normalize 模組（isolation 的申請人改綁、
personnel 的名單產生都需要）。人員一律來自 migration_personnel.json，A 棧真人不進 B。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set

# notesid_to_email 規則寫死 @aseglobal.com（見 services/maillist_service.notesid_to_email）。
EMAIL_DOMAIN = "@aseglobal.com"


@dataclass
class Person:
    """一位可當申請人或簽核人的同事（使用者在 migration_personnel.json 直接填 email）。"""
    empno: str
    name: str
    email: str

    @property
    def notes_id(self) -> str:
        """email 反推 notes_id：讓 notesid_to_email(notes_id) 能還原回本 email。

        notesid_to_email 規則為 notesid.replace(' ','_')+'@aseglobal.com'，因此反推規則為
        取 local part、底線還原空白。前提是同事 email 均為 @aseglobal.com（使用者已確認）。
        """
        local = (self.email or "").strip()
        if local.lower().endswith(EMAIL_DOMAIN):
            local = local[: -len(EMAIL_DOMAIN)]
        return local.replace("_", " ")


@dataclass
class PersonnelBinding:
    """人員綁定：仿舊系統角色分工——廠棟工程師=申請人、環工負責人=簽核人。"""
    applicants: List[Person] = field(default_factory=list)  # 廠棟工程師（隔離申請人）
    signers: List[Person] = field(default_factory=list)     # 環工負責人（簽核人）

    def all_people(self) -> List[Person]:
        return list(self.applicants) + list(self.signers)


@dataclass
class MigrationContext:
    """一次搬遷所需的共用參數。"""
    personnel: PersonnelBinding
    now: datetime                              # 用於「有效隔離」判定（active-only）
    plant_filter: Optional[Set[str]] = None    # 只搬這些 plant_no（None=不過濾）
    # 隔離簽核用的報表類型（mail_list.rpttype），與 seed_test_data.py 一致
    isolation_sign_rpttypes: tuple = ("水保養中", "空保養中")
    water_dispatch_rpttype: str = "水質異常"
    signer_role_id: int = 3                    # 簽核人在 acl_user_role 掛的角色（沿用 seed 慣例 roleid=3）
    # 派報收件人用的報表類型：services/dispatch_service.evaluate_row 產生的代碼（去掉 -廠區 後綴）。
    # sType='水'/'空' × {Alert, OOS, OOS15, OOS30, OOC, OOC15, OOC30}（ArrOOCS=['','15','30']）。
    # 全部種進 mail_list（TO），確保搬遷後任何派報情境都找得到收件人，不必像 demo 那樣臨時補。
    dispatch_rpttypes: tuple = (
        "水Alert", "水OOS", "水OOS15", "水OOS30", "水OOC", "水OOC15", "水OOC30",
        "空Alert", "空OOS", "空OOS15", "空OOS30", "空OOC", "空OOC15", "空OOC30",
    )


def load_personnel(path: str) -> PersonnelBinding:
    """讀 migration_personnel.json → PersonnelBinding。

    格式（見 scripts/migration_personnel.json.example）：
      {
        "廠棟工程師_申請人": [{"empno": "...", "name": "...", "email": "...@aseglobal.com"}],
        "環工負責人_簽核人": [{"empno": "...", "name": "...", "email": "...@aseglobal.com"}]
      }
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    def _people(key: str) -> List[Person]:
        out = []
        for row in data.get(key, []):
            out.append(Person(empno=row["empno"], name=row.get("name", ""), email=row["email"]))
        return out

    binding = PersonnelBinding(
        applicants=_people("廠棟工程師_申請人"),
        signers=_people("環工負責人_簽核人"),
    )
    if not binding.applicants or not binding.signers:
        raise ValueError(
            "migration_personnel.json 需至少各有一位『廠棟工程師_申請人』與『環工負責人_簽核人』"
        )
    return binding
