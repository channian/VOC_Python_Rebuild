# 廠務法規許可標準化管理平台 (VOC) - Python 現代化重構版

本專案為廠務法規許可標準化管理平台之重構專案，捨棄傳統 ASP.NET Web Forms，全面擁抱輕量、好維護且可測試的 Python 現代化與解耦架構。

## 技術架構
* **API 與路由核心**: FastAPI
* **前端與視圖**: Jinja2 Template + HTMX (實現無 JS 的動態網頁體驗)
* **資料庫存取**: SQLAlchemy + Pydantic
* **身分驗證**: Web 型 JWT Token (後端與 LDAP 串接)
* **背景任務**: FastAPI BackgroundTasks (信件與簡訊通報)
* **測試框架**: Pytest (針對核心商業邏輯進行全覆蓋測試)

## 開發核心準則
1. **S.O.L.I.D. 原則**: 每一個 Service 與 Repository 必須維持單一職責，絕不允許出現上帝類別。
2. **完整註解說明**: 每一支 API 路由與商轉函數皆需要有函式級別註解，並詳細說明重要變數與 Pydantic 物件的功能。
3. **測試驅動開發**: 任何小任務或單一路由開發完成前，必須撰寫並且通過單元測試。
