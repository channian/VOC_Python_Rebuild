from pydantic import BaseModel, field_validator


class ReasonUpdate(BaseModel):
    logid: int
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("原因說明不可為空白")
        return v.strip()
