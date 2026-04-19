import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.dashboard_service import get_dashboard_data

def test_dashboard_light_logic():
    """
    測試: Dashboard 紅綠燈號邏輯運算 (Mock Date)
    確保防呆邏輯沒問題，判斷規則：
    R (紅燈) = 值 >= oos
    O (橘燈) = ooc <= 值 < oos
    Y (黃燈) = alert < 值 < ooc
    G (綠燈) = 值未達警戒
    """
    # 當沒有真的連接 DB 時，我們現在的邏輯預期會回傳 3 筆用來開發防呆的 Mock 資料
    result = get_dashboard_data(db=None)  
    
    assert len(result) == 3
    
    # K1 廠 VOC, RValue=75, Alert(50), OOC(60), OOS(80) 
    # 因為 60 <= 75 < 80，預期應亮橘燈 O
    assert result[0].plantno == "K1"
    assert result[0].light_status == "O"
    
    # K2 廠 pH, RValue=9.1, Alert(7.5), OOC(8.0), OOS(8.5)
    # 因為 9.1 >= 8.5，預期應亮紅燈 R
    assert result[1].plantno == "K2"
    assert result[1].light_status == "R"
    
    # K3 廠 溫度, RValue=31, Alert(32), OOC(35), OOS(38)
    # 因為 31 < 32，為達警戒，預期正常綠燈 G
    assert result[2].plantno == "K3"
    assert result[2].light_status == "G"
