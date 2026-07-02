from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class RainGutterItem(BaseModel):
    plantno: str
    item: str
    sum24h: str
    rvalue: str
    status: str # G: 正常, R: 預警, O: 斷訊/異常
    remark: str

class WaterUrgentRequest(BaseModel):
    """
    人工觸發中水緊急通知（對應舊版 WaterUrgent.aspx 兩個按鈕）。
    notify_type='water_abnormal' → SendMail_水質異常通知：不需額外參數。
    notify_type='water_change'   → SendMail_改排水通知：需勾選 plantnos + 填 reason。
      reason 為前端已解析好的原因文字（舊版 __others.Text != "" ? __others.Text : 下拉選項文字）。
    """
    notify_type: str  # 'water_abnormal' (水質異常) or 'water_change' (改排水)
    plantnos: List[str] = []   # 改排水通知：勾選要通知的廠區清單（舊版 CheckBoxList plantlist）
    reason: str = ""            # 改排水原因文字（舊版「其他異常」時取自訂文字，否則取下拉選項文字）
