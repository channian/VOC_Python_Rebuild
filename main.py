from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from routers import home_router, acl_router, spec_router, control_router, flow_router, warning_router, ui_router

# 初始化 FastAPI 應用程式模組
app = FastAPI(
    title="VOC 廠務法規許可標準化管理平台",
    description="現代化 Python 重構專案",
    version="1.0.0"
)

# 註冊儀表板與其他路由
app.include_router(home_router.router)
app.include_router(acl_router.router)
app.include_router(spec_router.router)
app.include_router(control_router.router)
app.include_router(flow_router.router)
app.include_router(warning_router.router)
app.include_router(ui_router.router)

@app.get("/", include_in_schema=False)
async def read_root():
    """
    重定向到首頁儀表板。
    """
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/home")

if __name__ == "__main__":
    import uvicorn
    # 提供本地開發的熱重載運行設定
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
