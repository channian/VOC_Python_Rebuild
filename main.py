from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from routers import home_router, acl_router, spec_router, control_router

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

async def read_root():
    """
    提供基礎的根目錄路由測試。
    未來此處將透過 Jinja2 渲染 HTML 模板搭配 HTMX 做首頁。
    """
    return """
    <html>
        <head>
            <title>VOC 管理平台</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>🏭 VOC 系統 Python 版 - 建置中</h1>
            <p>FastAPI Server 運作正常！</p>
        </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    # 提供本地開發的熱重載運行設定
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
