from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from schemas.dashboard_schema import DashboardRow

def get_dashboard_data(db: Session, plant_permissions: str = "29") -> List[DashboardRow]:
    """
    獲取首頁的廠區儀表板資料，並依據參數進行紅綠燈狀態運算。
    此方法重構並取代了原本 dbVOC.cs 最龐大且難以測試的 ListVOC() 以及 gvVOCList_RowCreated()。
    """
    
    # 這個 SQL 語句源自舊版 dbVOC.cs 中，改為 Raw SQL 以直通未來轉換的資料庫，以保持與舊有 DBA 連接高度相容。
    sql_query = """
    Select S.plantno as plantno, Replace(Replace(S.item,'COD2','COD'),'pH1','pH') as item,
           S.LAW as law_spec, S.OOS as oos, S.OOC as ooc, S.alert as alert, S.recv as recv,
           I.unit as unit, W.OOS_HH as scada_oos_hh, W.OOC_H as scada_ooc_h, W.alert as scada_alert, 
           W.OOS_HH1 as cwms_oos_hh, W.OOC_H1 as cwms_ooc_h, 
           Replace(Replace(Replace(Replace(W.rvalue,'N.D',0),'<0.05',0),'<0.02',0),'<0.01',0) as rvalue,
           C.URL as url, S.source as source
    From [VOC].[dbo].[VOC_SPEC] S 
    Join [VOC].[dbo].[VOC_item] I On S.item=I.item 
    Join [VOC].[dbo].[VOC_plant] P On S.plantno=P.plantno And isShow=1 
    Left Join [VOC].[dbo].[VOC_SCADA_WEB] W On S.plantno=W.plantno And S.item=W.item 
    Left Join [VOC].[dbo].[VOC_Curve] C On S.plantno=C.plantno And S.item=C.item 
    """
    
    # 🚧 開發階段：如果無法連接正式機 DB，預設提供 Mock Data 展示 🚧
    try:
        # result = db.execute(text(sql_query)).mappings().all()
        # 由於現階段尚處於開發無實體資料庫的狀態，直接給予開發用範例列表
        result = [
            {"plantno": "K1", "item": "VOC", "unit": "ppm", "law_spec": "100", "oos": "80", "ooc": "60", "alert": "50", "recv": "40", "rvalue": "75", "source": 1, "scada_oos_hh": "80", "scada_ooc_h": "60", "scada_alert": "50", "cwms_oos_hh": "80", "cwms_ooc_h": "60"},
            {"plantno": "K2", "item": "pH", "unit": "pH", "law_spec": "6-9", "oos": "8.5", "ooc": "8", "alert": "7.5", "recv": "7", "rvalue": "9.1", "source": 2, "scada_oos_hh": "8.5", "scada_ooc_h": "8", "scada_alert": "7.5", "cwms_oos_hh": "8.5", "cwms_ooc_h": "8"},
            {"plantno": "K3", "item": "溫度", "unit": "°C", "law_spec": "40", "oos": "38", "ooc": "35", "alert": "32", "recv": "30", "rvalue": "31", "source": 3, "scada_oos_hh": "38", "scada_ooc_h": "35", "scada_alert": "32", "cwms_oos_hh": "38", "cwms_ooc_h": "35"}
        ]
    except Exception as e:
        print(f"SQL Error: {e}")
        return []

    processed_rows = []
    
    for row in result:
        # 將字串安全轉換數字防呆
        try:
            rvalue = float(row.get('rvalue', 0)) if row.get('rvalue') else 0
            oos = float(row.get('oos', 9999)) if row.get('oos') else 9999
            ooc = float(row.get('ooc', 9999)) if row.get('ooc') else 9999
            alert = float(row.get('alert', 9999)) if row.get('alert') else 9999
        except ValueError:
            rvalue, oos, ooc, alert = 0, 9999, 9999, 9999
        
        light_status = "G" # 預設綠燈 (正常狀態)
        is_anomaly = False
        
        # 異常狀態如斷訊直接判紅燈
        if str(row.get('rvalue')) in ["斷訊", "異常", "保養中", ""]:
            light_status = "R" 
            is_anomaly = True
        else:
            # 演算法的核心：比對規格值發出警告
            if rvalue >= oos:
                light_status = "R"
            elif rvalue >= ooc and rvalue < oos:
                light_status = "O"
            elif rvalue > alert and rvalue < ooc:
                light_status = "Y"
                
        processed_rows.append(DashboardRow(
            plantno=str(row.get('plantno')),
            item=str(row.get('item')),
            unit=str(row.get('unit')),
            law_spec=str(row.get('law_spec')),
            oos=str(row.get('oos')),
            ooc=str(row.get('ooc')),
            alert=str(row.get('alert')),
            recv=str(row.get('recv')),
            rvalue=str(row.get('rvalue')),
            light_status=light_status,
            source=int(str(row.get('source', '1'))),
            is_anomaly=is_anomaly
        ))
        
    return processed_rows
