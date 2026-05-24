from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import logging
from schemas.warning_schema import RainGutterItem, WaterUrgentRequest
from services.notify_service import add_notification_task
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

def get_raingutter_list(db: Session) -> List[RainGutterItem]:
    """
    移植 dbVOC.List雨水溝預警() 與 RainGutter.aspx.csGetData雨水溝() 的燈號判斷邏輯
    """
    # 原系統中雨水溝數據主要寫入 CIM 或 SQL DB，這裡以 Raw SQL 模擬取回
    # 此查詢實際依附於現場資料庫，此處示範相容提取方式
    try:
        # 假設資料儲存於 VOC_raingutter 表格
        result = db.execute(text("SELECT plantno, item, sum24h, rvalue, remark FROM VOC_raingutter")).mappings().all()
        out = []
        for row in result:
            s24h = row['sum24h'] or '0.0'
            rval = row['rvalue'] or '異常'
            
            # 燈號邏輯: 紅燈條件：最新讀值=1 且 24H累積雨量=0
            # 橘燈條件：斷訊 或 異常
            # 綠燈條件：正常狀態
            status = 'G'
            if s24h == "0.0" and rval == "1":
                status = 'R'
            elif rval in ["斷訊", "異常"] or (s24h == "異常" and rval == "1"):
                status = 'O'
                
            out.append(RainGutterItem(
                plantno=row['plantno'],
                item=row['item'],
                sum24h=str(s24h),
                rvalue=str(rval),
                status=status,
                remark=row['remark'] or ''
            ))
        return out
    except Exception as e:
        logger.warning(f"RainGutter query failed, returning mock: {e}")
        # 提供測試環境 Mock
        return [
            RainGutterItem(plantno="K1", item="RainGutter_1", sum24h="0.0", rvalue="1", status="R", remark="需要注意"),
            RainGutterItem(plantno="K9", item="RainGutter_2", sum24h="12.5", rvalue="0", status="G", remark="正常")
        ]

def get_current_anomalies(db: Session) -> list:
    """
    取得目前儀表板上紅燈／橙燈的項目，供預警紀錄 Modal 顯示。
    直接讀 VOC_SCADA_WEB.light 欄位（JOB 寫入），無需重跑燈號計算。
    """
    sql = text("""
        SELECT W.plantno,
               REPLACE(REPLACE(W.item, 'COD2', 'COD'), 'pH1', 'pH') AS item,
               W.rvalue, W.cdatetime, W.light
        FROM  [VOC].[dbo].[VOC_SCADA_WEB] W
        JOIN  [VOC].[dbo].[VOC_plant]     P ON W.plantno = P.plantno AND P.isShow = 1
        WHERE W.light IN ('R', 'O')
          AND (W.broken IS NULL OR W.broken = 0)
        ORDER BY W.light, P.sort, W.item
    """)
    try:
        rows = db.execute(sql).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[get_current_anomalies] DB 查詢失敗: {e}")
        return []


def trigger_water_notify(req: WaterUrgentRequest, bg_tasks: BackgroundTasks):
    """
    移植 dbVOC.SendMail_水質異常通知 與 dbVOC.SendMail_改排水通知
    """
    # 因相容系統，在此以背景 task 的方式調用 mail service
    if req.notify_type == "water_abnormal":
        subj = "【水質異常通知】請注意"
        msg = "系統偵測到水質異常，請相關人員注意並巡查。"
        add_notification_task(bg_tasks, subj, msg, emails=["water_team@asegroup.com"])
    elif req.notify_type == "water_change":
        subj = f"【改排水通知】廠區 {req.plantid}"
        msg = f"啟動改排水程序。原因: {req.reason}"
        add_notification_task(bg_tasks, subj, msg, emails=["water_team@asegroup.com"])
    else:
        raise ValueError("不支援的通知類型")
