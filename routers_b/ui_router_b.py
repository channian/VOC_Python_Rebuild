"""
routers_b/ui_router_b.py — Schema B（PostgreSQL）版 FastAPI router 組裝

main_b.py 的實際掛載點。現有 `routers/`（A/MSSQL 版）全部改用 raw text() SQL 綁死
`[VOC].[dbo].[VOC_xxx]` 表名/方言，光靠 `app.dependency_overrides` 換掉 `get_voc_db` 的
session 來源並不能讓它們對 PostgreSQL 生效（SQL 語法本身就綁死 MSSQL 方言與 A 棧表結構）。
main_b.py 的排除清單與本檔案的取捨說明詳見該檔頂端註解與任務回報。

本檔重建的路由（皆改走 services_b/*，router URL 路徑刻意與 A 棧 routers/ 對齊，
現有 templates/partials/*.html 的 JS fetch 路徑不必修改即可直接運作）：

  GET  /home                     — 首頁儀表板（services_b.dashboard_service）
  GET  /ui/maillist               POST /maillist/add|update|delete|toggle  GET /maillist/employee/{empno}
  GET  /ui/history  GET /history/plants|items|logs  POST /history/reply
  GET  /report/ui   GET /report/logs
  GET  /dept/ui     GET /dept/name/{deptno}         POST /dept/add|update|delete
  GET  /ui/acl      GET /acl/list|roles|plants|employee/{empno}  POST /acl/create|update|delete
  GET  /ui/warning  GET /warning/anomalies

未重建（超出 WP5 範圍，main_b 待整合清單，見任務回報）：
  /ui/control /ui/spec /ui/qa /ui/flow /ui/reason /warning/water_urgent/ui —
  分別對應 WP3（control/flow）/WP4（spec/qa）/WP5 warning 進階功能，services_b 對應檔案
  若已存在（control_service.py/flow_service.py/spec_service.py/qa_service.py 皆已就緒），
  純粹是本檔案未逐一補齊 router，不是資料層缺功能。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database_b import get_b_db
from schemas.warning_schema import WaterUrgentRequest

# 2026-08-01 D5「4 頁 schema 驗證未接線」：派送名單／部門／ACL／異常回覆四頁的寫入端點
# 原本各自在本檔宣告裸的 BaseModel（只有型別、沒有任何欄位驗證），空白廠區、非法 TO/CC、
# 未開放的 role_id 都照單全收。改為統一使用 schemas/ 的模型（B 棧專用類別皆與 A 棧同檔，
# 盡量繼承既有 A 棧模型重用規則；形狀不同才另建，理由見各 schema 檔內註解）。
from schemas.acl_schema import AclUserCreateB, AclUserDeleteB, AclUserUpdateB
from schemas.dept_schema import DeptAddB, DeptDeleteB, DeptUpdateB
from schemas.history_schema import ReasonUpdateB
from schemas.maillist_schema import MailListAddB, MailListDeleteB, MailListUpdateB

from services_b.dashboard_service import get_dashboard_rows
from services_b.control_service import is_item_isolated
from services_b import dashboard_page_service
from services_b import maillist_service, dept_service, acl_service, history_service, report_service, warning_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _user_no() -> str:
    """目前操作者工號（session 登入身分；AUTH_MOCK=True 未登入時回退 MOCK 身分）。
    2026-07-31 AD 串接：本檔原本寫死 "admin" 的操作者參數全部改走這裡。"""
    from services_b.session_auth import get_current_user
    return get_current_user()[0]


def _isolation_checker(db: Session):
    return lambda plant_no, item: is_item_isolated(db, plant_no, item)


# ══════════════════════════════════════════════════════════════════════════
# 首頁儀表板
# ══════════════════════════════════════════════════════════════════════════

@router.get("/home", name="home_dashboard_b")
def read_home_b(request: Request, db: Session = Depends(get_b_db)):
    """
    B 棧首頁儀表板 —— 新版深色 SCADA 風格儀表板
    （design_handoff_voc_platform/VOC Dashboard.dc.html 高保真還原，見 templates/b/dashboard.html）。
    資料來源 spec + reading_current（取代 VOC_SPEC + VOC_SCADA_WEB），
    純轉換（燈號分類/分組/摘要）交給 services_b.dashboard_page_service。
    """
    ctx = dashboard_page_service.get_dashboard_page_data(db, _isolation_checker(db))
    from services_b.session_auth import get_current_user
    empno, name = get_current_user()
    return templates.TemplateResponse(
        request=request, name="b/dashboard.html",
        context={"ctx": ctx, "current_user_empno": empno, "current_user_name": name},
    )


@router.get("/home/classic", name="home_dashboard_b_classic")
def read_home_b_classic(request: Request, db: Session = Depends(get_b_db)):
    """B 棧首頁儀表板（舊版樣式對照入口）：沿用 A 棧共用的 templates/home.html 版面，資料仍走 B 棧。"""
    dashboard_data = get_dashboard_rows(db, isolation_checker=_isolation_checker(db))
    return templates.TemplateResponse(
        request=request, name="home.html", context={"voc_list": dashboard_data}
    )


# ══════════════════════════════════════════════════════════════════════════
# 派送名單維護
# ══════════════════════════════════════════════════════════════════════════

# 請求模型：schemas.maillist_schema 的 MailListAddB / MailListUpdateB / MailListDeleteB（見檔頭說明）


@router.get("/ui/maillist")
def render_maillist_modal_b(request: Request, db: Session = Depends(get_b_db)):
    return templates.TemplateResponse(
        request=request, name="b/partials/maillist.html",
        context={
            "maillist": maillist_service.list_maillist(db),
            "plants": maillist_service.get_plant_list(db),
            "rpttypes": maillist_service.get_rpttype_list(db),
            "disabled": maillist_service.is_mail_paused(db),
        },
    )


@router.get("/maillist/employee/{empno}")
def api_lookup_employee_b(empno: str, db: Session = Depends(get_b_db)):
    return maillist_service.lookup_employee(db, empno)


@router.post("/maillist/add")
def api_add_maillist_b(data: MailListAddB, db: Session = Depends(get_b_db)):
    try:
        maillist_service.add_maillist(
            db, current_user_empno=_user_no(), plant_no=data.plantno, rpttype=data.rpttype,
            emp_no=data.empno, emp_name=data.empname, notes_id=data.notesid,
            mail_type=data.mailtype, mail_on=bool(data.mail), sign_grp=bool(data.signgrp),
            remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="新增失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.rpttype}/{data.empno} 已新增"}


@router.post("/maillist/update")
def api_update_maillist_b(data: MailListUpdateB, db: Session = Depends(get_b_db)):
    try:
        maillist_service.update_maillist(
            db, current_user_empno=_user_no(), plant_no=data.plantno, rpttype=data.rpttype,
            old_emp_no=data.old_empno, emp_no=data.empno, emp_name=data.empname,
            notes_id=data.notesid, mail_type=data.mailtype, mail_on=bool(data.mail),
            sign_grp=bool(data.signgrp), remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="修改失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.rpttype}/{data.empno} 已修改"}


@router.post("/maillist/delete")
def api_delete_maillist_b(data: MailListDeleteB, db: Session = Depends(get_b_db)):
    try:
        maillist_service.delete_maillist(db, current_user_empno=_user_no(), plant_no=data.plantno,
                                          rpttype=data.rpttype, emp_no=data.empno)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="刪除失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.rpttype}/{data.empno} 已刪除"}


@router.post("/maillist/toggle")
def api_toggle_mail_b(enable: bool, db: Session = Depends(get_b_db)):
    """全域暫停/恢復寄信（POST /maillist/toggle?enable=true|false）。

    沒有 request body，唯一參數 `enable` 是查詢字串的布林值，FastAPI 本身就會做型別驗證
    （非布林值 → 422），故不需要額外的 Pydantic 請求模型（2026-08-01 D5 盤點結論）。
    """
    maillist_service.set_mail_paused(db, paused=not enable)
    return {"status": "success", "disabled": maillist_service.is_mail_paused(db)}


# ══════════════════════════════════════════════════════════════════════════
# 異常記錄查詢 / 原因回覆
# ══════════════════════════════════════════════════════════════════════════

# 請求模型：schemas.history_schema.ReasonUpdateB
#   2026-07-31 C8：回覆改成逐項目層級，item_id 是 history_service._make_item_id()
#   組出的複合鍵字串（對應 mail_log_item 的 (mail_log_id, item, condition_code) 複合主鍵），
#   由 /history/logs、/ui/history、/ui/reason 回傳的每一列帶出，前端原樣送回即可。


@router.get("/history/plants")
def api_history_plants_b(db: Session = Depends(get_b_db)):
    return history_service.list_plants(db)


@router.get("/history/items")
def api_history_items_b(plant: str = "", db: Session = Depends(get_b_db)):
    return history_service.list_items(db, plant)


@router.get("/history/logs")
def api_history_logs_b(plant: str = "", item: str = "", sdate: str = "", edate: str = "",
                        mt: bool = False, db: Session = Depends(get_b_db)):
    if not sdate or not edate:
        sdate, edate = history_service.default_date_range()
    history_service.validate_date_range(sdate, edate)
    return history_service.list_voclog(db, plant, item, sdate, edate, mt)


@router.post("/history/reply")
def api_reason_reply_b(data: ReasonUpdateB, db: Session = Depends(get_b_db)):
    """URL 沿用舊路徑（避免斷鏈），但 body 形狀已改成逐項目（item_id 取代 logid）。"""
    try:
        history_service.update_reason(db, data.item_id, data.reason, current_user_empno=_user_no())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": "原因已儲存"}


@router.get("/ui/history")
def render_history_modal_b(request: Request, plant: str = "", item: str = "", sdate: str = "",
                            edate: str = "", mt: bool = False, db: Session = Depends(get_b_db)):
    if not sdate or not edate:
        sdate, edate = history_service.default_date_range()
    logs, error = [], ""
    try:
        history_service.validate_date_range(sdate, edate)
        logs = history_service.list_voclog(db, plant, item, sdate, edate, mt)
    except ValueError as e:
        error = str(e)
    except Exception as e:
        error = f"查詢失敗：{e}"
    return templates.TemplateResponse(
        request=request, name="b/partials/history.html",
        context={
            "mode": "history",  # 合併版模板：history=唯讀查詢、reason=可行內回覆
            "plants": history_service.list_plants(db), "items": history_service.list_items(db, plant),
            "plant": plant, "item": item, "sdate": sdate, "edate": edate, "mt": mt,
            "logs": logs, "error": error,
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# 異常報表
# ══════════════════════════════════════════════════════════════════════════

@router.get("/report/logs")
def api_report_logs_b(plant: str = "", item: str = "", sdate: str = "", edate: str = "",
                       mt: bool = False, db: Session = Depends(get_b_db)):
    if not sdate or not edate:
        sdate, edate = report_service.default_date_range()
    report_service.validate_date_range(sdate, edate)
    rows = report_service.query_report_data(db, plant, item, sdate, edate, mt)
    return {
        "sdate": sdate, "edate": edate, "rows": rows,
        "summary": report_service.build_summary(rows),
        "pivot": report_service.build_pivot(rows),
        "ranking": report_service.build_ranking(rows),
    }


@router.get("/report/ui")
def render_report_page_b(request: Request):
    """異常報表（V2 起為獨立頁 b/report.html；資料全由前端 fetch /history/plants、
    /history/items、/report/logs，本 handler 不再預跑統計——舊 partial 版的伺服端統計
    邏輯保留在 /report/logs API，無流失）。"""
    return templates.TemplateResponse(request=request, name="b/report.html", context={})


# ══════════════════════════════════════════════════════════════════════════
# 部門權限維護
# ══════════════════════════════════════════════════════════════════════════

# 請求模型：schemas.dept_schema 的 DeptAddB / DeptUpdateB / DeptDeleteB
# （直接繼承 A 棧 DeptAdd/DeptUpdate/DeptDelete，多加長度上限，見該檔註解）


@router.get("/dept/ui")
def render_dept_modal_b(request: Request, plantid: str = "", deptno: str = "", db: Session = Depends(get_b_db)):
    try:
        plantid_int = int(plantid) if plantid else None
        rows = dept_service.list_dept_data(db, plantid_int, deptno)
        plants = dept_service.list_plants(db)
        error = ""
    except Exception:
        rows, plants, error = [], [], "查詢失敗，資料庫連線異常"
    return templates.TemplateResponse(
        request=request, name="b/partials/dept.html",
        context={"depts": rows, "plants": plants, "plantid": plantid, "deptno": deptno,
                 "error": error, "is_all_plant": dept_service.is_all_plant},
    )


@router.get("/dept/name/{deptno}")
def api_get_dept_name_b(deptno: str, db: Session = Depends(get_b_db)):
    deptname = dept_service.get_dept_name(db, deptno)
    if not deptname:
        raise HTTPException(status_code=404, detail="部門代碼錯誤!")
    return {"deptno": deptno, "deptname": deptname}


@router.post("/dept/add")
def api_add_dept_b(data: DeptAddB, db: Session = Depends(get_b_db)):
    try:
        dept_service.add_dept(db, current_user_empno=_user_no(), plant_id=data.plantid,
                               dept_no=data.deptno, remark=data.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"{data.plantid}/{data.deptno} 已新增"}


@router.post("/dept/update")
def api_update_dept_b(data: DeptUpdateB, db: Session = Depends(get_b_db)):
    try:
        dept_service.update_dept(db, current_user_empno=_user_no(), plant_id=data.plantid,
                                  old_dept_no=data.old_deptno, new_dept_no=data.deptno,
                                  remark=data.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"{data.plantid}/{data.deptno} 已修改"}


@router.post("/dept/delete")
def api_delete_dept_b(data: DeptDeleteB, db: Session = Depends(get_b_db)):
    try:
        dept_service.delete_dept(db, current_user_empno=_user_no(), plant_id=data.plantid, dept_no=data.deptno)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"{data.plantid}/{data.deptno} 已刪除"}


# ══════════════════════════════════════════════════════════════════════════
# 系統管理 — ACL 隔離權限名單
# ══════════════════════════════════════════════════════════════════════════

# 請求模型：schemas.acl_schema 的 AclUserCreateB / AclUserUpdateB / AclUserDeleteB
# （繼承 A 棧 AclUserCreate/AclUserUpdate，沿用「角色只能 3/7、stype 只能 1/2/3」等既有規則）


@router.get("/ui/acl")
def render_acl_modal_b(request: Request):
    return templates.TemplateResponse(request=request, name="b/partials/acl.html", context={})


@router.get("/acl/list")
def get_acl_list_b(plantno: str = "", roletype: str = "", empno: str = "", db: Session = Depends(get_b_db)):
    try:
        return acl_service.list_acl_users(db, plantno, roletype, empno)
    except Exception:
        raise HTTPException(status_code=500, detail="查詢失敗，資料庫連線異常")


@router.get("/acl/roles")
def get_acl_roles_b(db: Session = Depends(get_b_db)):
    return acl_service.get_role_list(db)


@router.get("/acl/plants")
def get_acl_plants_b(db: Session = Depends(get_b_db)):
    return acl_service.get_plant_list(db)


@router.get("/acl/employee/{empno}")
def api_lookup_acl_employee_b(empno: str, db: Session = Depends(get_b_db)):
    return acl_service.lookup_employee(db, empno)


@router.post("/acl/create")
def add_acl_b(data: AclUserCreateB, db: Session = Depends(get_b_db)):
    try:
        acl_service.create_acl_user(db, current_user_empno=_user_no(), plantno=data.plantno,
                                     role_id=data.role_id, empno=data.empno, stype=data.stype,
                                     remark=data.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"{data.plantno}/{data.role_id}/{data.empno} 已新增"}


@router.post("/acl/update")
def update_acl_b(data: AclUserUpdateB, db: Session = Depends(get_b_db)):
    try:
        acl_service.update_acl_user(db, current_user_empno=_user_no(), plantno=data.plantno, role_id=data.role_id,
                                     old_empno=data.old_empno, empno=data.empno, stype=data.stype,
                                     old_stype=data.old_stype, remark=data.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"{data.plantno}/{data.role_id}/{data.empno} 已修改"}


@router.post("/acl/delete")
def remove_acl_b(data: AclUserDeleteB, db: Session = Depends(get_b_db)):
    try:
        acl_service.delete_acl_user(db, current_user_empno=_user_no(), plantno=data.plantno,
                                     role_id=data.role_id, empno=data.empno)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"{data.plantno}/{data.role_id}/{data.empno} 已刪除"}


# ══════════════════════════════════════════════════════════════════════════
# 預警 / 中水緊急通知（基本查詢，進階通知按鈕見檔頭「未重建」清單）
# ══════════════════════════════════════════════════════════════════════════

@router.get("/warning/anomalies")
def fetch_anomalies_b(db: Session = Depends(get_b_db)):
    try:
        return warning_service.get_current_anomalies(db, isolation_checker=_isolation_checker(db))
    except Exception:
        raise HTTPException(status_code=500, detail="異常清單查詢失敗，資料庫連線異常")


@router.get("/warning/raingutter")
def fetch_raingutter_b(db: Session = Depends(get_b_db)):
    try:
        return warning_service.get_raingutter_list(db)
    except Exception:
        raise HTTPException(status_code=500, detail="雨水溝資料查詢失敗，資料庫連線異常")


@router.get("/ui/warning")
def render_warning_modal_b(request: Request, db: Session = Depends(get_b_db)):
    try:
        anomalies = warning_service.get_current_anomalies(db, isolation_checker=_isolation_checker(db))
    except Exception:
        anomalies = []
    return templates.TemplateResponse(
        request=request, name="partials/warning_modal.html", context={"anomalies": anomalies},
    )


@router.post("/warning/water_urgent")
def post_water_urgent_b(req: WaterUrgentRequest, bg_tasks: BackgroundTasks, db: Session = Depends(get_b_db)):
    try:
        sent = warning_service.trigger_water_notify(db, req, bg_tasks)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    if not sent:
        return {"status": "empty", "message": "沒有符合條件的收件人或資料，未寄出通知"}
    return {"status": "success", "message": "通知已排入背景發送程序"}
