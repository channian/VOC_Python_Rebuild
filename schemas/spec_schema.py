from pydantic import BaseModel, model_validator
from typing import Optional
import re

class SpecBase(BaseModel):
    """ 提供 EditSPEC 建立或更新時的通用資料模型 """
    plantno: str
    item: str
    LAW: str
    OOS: str
    OOC: str
    alert: str
    source_id: int
    remark: Optional[str] = ""

    @model_validator(mode='after')
    def validate_limits(self) -> 'SpecBase':
        """ 完美移植舊版 C# 的範圍防呆邏輯 """
        def parse_str_val(val: str, field_name: str, is_ph: bool):
            if not val or val == "N/A":
                return None
            
            val = val.strip()
            parts = val.split('-')
            
            if is_ph and len(parts) == 1:
                raise ValueError(f"{field_name} 值錯誤, pH 必須為雙邊規格 (如: 6-9)!")
            if not is_ph and len(parts) == 2:
                raise ValueError(f"{field_name} 值錯誤, {self.item} 必須為單邊規格 (如: 6)!")
                
            for part in parts:
                if not re.match(r'^\d+(\.\d{1,2})?$', part):
                    raise ValueError(f"{field_name} 值({part})錯誤, 請確保皆為數字且最多包含兩位小數!")
                    
            if len(parts) == 2:
                if float(parts[0]) >= float(parts[1]):
                    raise ValueError(f"{field_name} 格式錯誤: 下限規格不能大於或等於上限規格!")
            return [float(p) for p in parts]

        is_ph = (self.item.lower() == 'ph' or self.item == 'pH1')
        
        # 1. 基礎數字與格式驗證
        law_vals = parse_str_val(self.LAW, "LAW", is_ph)
        oos_vals = parse_str_val(self.OOS, "OOS", is_ph)
        ooc_vals = parse_str_val(self.OOC, "OOC", is_ph)
        alert_vals = parse_str_val(self.alert, "Alert", is_ph)

        # 2. 邏輯層遞約束驗證 (Alert 必須 < OOC < OOS)
        # 單雙邊的比對邏輯：
        if ooc_vals and alert_vals:
            if is_ph:
                # 雙邊：下限 Alert 應該要 > OOC，上限 Alert 應該要 < OOC （往內縮）
                # 舊版邏輯：OOC需大於Alert, MTDBbase.ToDecimal(OOC[0]) <= MTDBbase.ToDecimal(alert[0]) -> ERROR
                if ooc_vals[0] >= alert_vals[0] or ooc_vals[1] <= alert_vals[1]:
                    raise ValueError("對於 pH 值：OOC 的範圍必須比 Alert 更寬入！(例如 OOC 5-10, Alert 6-9)")
            else:
                # 單邊：上限值
                if ooc_vals[0] <= alert_vals[0]:
                    raise ValueError("單邊規格中，OOC 上限值必須大於 Alert！")

        return self

class SpecCreate(SpecBase):
    pass

class SpecUpdate(SpecBase):
    pass

class SpecResponse(BaseModel):
    plantno: str
    item: str
    LAW: str
    OOS: str
    OOC: str
    alert: str
    source: str # 對應來源名稱
    tagname: Optional[str] = None
    
    class Config:
        from_attributes = True
