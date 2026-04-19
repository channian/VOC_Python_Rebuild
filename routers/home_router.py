from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_voc_db
from services.dashboard_service import get_dashboard_data

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/home", name="home_dashboard")
def read_home(request: Request, db: Session = Depends(get_voc_db)):
    """
    首頁儀表板入口 (完全取代舊有 Home.aspx 頁面載入邏輯)
    會經由 dashboard_service 獲取資料與狀態燈號運算結果，
    再使用 Jinja2 + HTMX 組合將畫面回傳。
    """
    dashboard_data = get_dashboard_data(db)
    
    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request, 
            "voc_list": dashboard_data
        }
    )
