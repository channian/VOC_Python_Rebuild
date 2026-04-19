from pydantic import BaseModel
from typing import Optional

class DashboardRow(BaseModel):
    """ 對應首頁儀表板的一筆紀錄 """
    plantno: str
    item: str
    unit: Optional[str] = ""
    law_spec: Optional[str] = ""
    oos: Optional[str] = ""
    ooc: Optional[str] = ""
    alert: Optional[str] = ""
    recv: Optional[str] = ""
    
    # 讀值與狀態
    rvalue: Optional[str] = ""
    scada_oos: Optional[str] = ""
    scada_ooc: Optional[str] = ""
    scada_alert: Optional[str] = ""
    cwms_oos: Optional[str] = ""
    cwms_ooc: Optional[str] = ""
    
    # 計算後之變數
    light_status: str  # 狀態燈號 ('G', 'Y', 'O', 'R')
    remark: Optional[str] = ""
    url: Optional[str] = "" 
    
    # 決定顏色渲染的來源與例外
    source: Optional[int] = 1 # 1: SCADA, 2: CWMS, 3: QA
    is_anomaly: bool = False  # 是否斷訊/異常
