"""
main_b.py — Schema B（PostgreSQL）版 FastAPI 應用程式組裝

啟動方式（比照 main.py）：
    python main_b.py            # http://localhost:8000/home
    python -m uvicorn main_b:app --reload

★ 與 main.py（A/MSSQL 棧）的關鍵差異與取捨（詳見 docs/PhaseA執行規格書.md 第四節）：

  最初設想的組裝方式是「現有 routers/ 原樣掛進來，靠 app.dependency_overrides 把
  get_voc_db 換成 get_b_db，讓同一批 router 直接對 PostgreSQL 生效」。實際檢視
  routers/*.py 所呼叫的 services/*.py 後，這條路徑行不通並予以放棄，原因：

    services/ 底下每一個查詢函式都是 `db.execute(text("SELECT ... FROM [VOC].[dbo].[VOC_xxx]"))`
    這種綁死 MSSQL 方括號方言與 A 棧表名/欄名的 raw SQL（例如 VOC_plant.plantno、
    VOC_SCADA_WEB.rvalue 這些 B 棧根本不存在的表/欄）。`dependency_overrides` 只能替換
    `Depends(get_voc_db)` 產生的 **Session 物件來源**（從 MSSQL engine 換成 PostgreSQL
    engine），並不能改寫已經寫死在函式內的 SQL 字串本身——所以只換 session、不換 SQL，
    對 B 棧（PostgreSQL、全新 schema）而言 100% 會在執行 SQL 那一刻報錯（表不存在 /
    語法錯誤，PostgreSQL 沒有方括號識別符語法）。

  因此 main_b.py 採取的務實作法：
    1. **完全不掛載 `routers/`（A 棧）**，改為新建 `routers_b/ui_router_b.py`，
       所有端點都改呼叫 `services_b/*`（B 棧資料層，SQLAlchemy 2.0 表達式操作 models_b.py）。
    2. `routers_b/ui_router_b.py` 的 URL 路徑刻意與 A 棧 routers/ 對齊（如 `/dept/ui`、
       `/acl/list`、`/maillist/add`…），這樣 `templates/` 既有的 Jinja2 partial 頁面
       （內含寫死路徑的 htmx/fetch JavaScript）**完全不用修改**就能對 B 棧生效。
    3. 首頁儀表板（GET /home）走 services_b.dashboard_service.get_dashboard_rows()，
       是本檔案 / Phase A 驗收的核心目標（見 docs/PhaseA執行規格書.md 第八節第 2 項）。

  **待整合清單**（非 WP5 範圍，services_b 對應資料層檔案多半已由其他 WP 完成，
  純粹是還沒有人寫對應的 routers_b 端點，main_b 尚未串接）：
    - 廠區隔離申請/簽核（對應 A 棧 /control、/flow）— services_b/control_service.py、
      services_b/flow_service.py 皆已就緒（WP3），可比照本檔案 ui_router_b.py 的作法
      直接建立 routers_b/control_router_b.py。
    - 規格維護/簽核（對應 A 棧 /spec）— services_b/spec_service.py 已就緒（WP4）。
    - QA 手測值（對應 A 棧 /qa）— services_b/qa_service.py 已就緒（WP4）。
    - 中水緊急通知按鈕頁面（/warning/water_urgent/ui 的下拉選單資料）與異常回覆 Modal
      （/ui/reason）— services_b/warning_service.py、history_service.py 函式已備妥，
      本檔案只是還沒把對應 GET .../ui 端點逐一補上（API 端點已有，見 ui_router_b.py）。
    - check_permission 尚未掛到任何 B 棧端點當守門（比照 CLAUDE.md「已知待辦」，現在
      current_user 全部寫死 "admin"，掛 ACL 守門沒有實益，等 Phase 3 LDAP 有真實
      current_user 後再一併接上）。
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from routers_b import auth_router_b, control_router_b, spec_router_b, trend_router_b, ui_router_b

app = FastAPI(
    title="VOC 廠務法規許可標準化管理平台（Schema B / PostgreSQL 版）",
    description="Phase A 重構版 — 資料層全面改用 SQLAlchemy 2.0 + PostgreSQL（models_b.py）",
    version="0.1.0-phaseA",
)

# 靜態資源（CSS / JS / 圖片）— 與 A 棧共用同一份 static/ 目錄，不用重複維護
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(ui_router_b.router)
# WP6 補完（2026-07-05）：待整合清單全數接通——
#   control_router_b：/ui/control(+items)、/control/*、/ui/flow、/flow/*
#   spec_router_b   ：/ui/spec、/spec/*、/ui/qa、/qa/update、/ui/reason、/warning/water_urgent/ui
app.include_router(control_router_b.router)
app.include_router(spec_router_b.router)
# 新版 UI（2026-07-11，依 design_handoff_voc_platform 高保真設計移植）——
#   auth_router_b ：/login（Phase A 門面登入，Phase 3 換 LDAP）
#   trend_router_b：/trend/*（歷史曲線頁，資料源 reading_history，補上舊系統缺原始碼的功能）
#   新儀表板在 ui_router_b 的 /home（舊版保留於 /home/classic 供對照）
app.include_router(auth_router_b.router)
app.include_router(trend_router_b.router)


@app.get("/", include_in_schema=False)
async def read_root():
    """重定向到首頁儀表板（與 main.py 行為一致）。"""
    return RedirectResponse(url="/home")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_b:app", host="0.0.0.0", port=8000, reload=True)
