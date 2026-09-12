from pydantic import BaseModel, ConfigDict, Field


class TanneryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sno: int
    name: str
    pump_house: str
    internal_id: str | None
    factory_id: str | None
    tnpcb_user_id: str | None
    gps: str | None
    gstin: str | None
    consent: str | None
    original_capacity: str | None
    additional_capacity: str | None
    original_shares: int | None
    additional_shares: int | None
    phone: str | None
    email: str | None


class TanneryFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    pump_house: str = Field(min_length=1, max_length=20)
    internal_id: str | None = Field(default=None, max_length=100)
    factory_id: str | None = Field(default=None, max_length=100)
    tnpcb_user_id: str | None = Field(default=None, max_length=100)
    gps: str | None = Field(default=None, max_length=2000)
    gstin: str | None = Field(default=None, max_length=20)
    consent: str | None = Field(default=None, max_length=255)
    original_capacity: str | None = Field(default=None, max_length=100)
    additional_capacity: str | None = Field(default=None, max_length=100)
    original_shares: int | None = Field(default=None, ge=0, le=2147483647)
    additional_shares: int | None = Field(default=None, ge=0, le=2147483647)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)


class TanneryCreate(TanneryFields):
    pass


class TanneryUpdate(TanneryFields):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    pump_house: str | None = Field(default=None, min_length=1, max_length=20)


class QualityIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tannery_id: int
    tannery_sno: int
    tannery_name: str
    code: str
    detail: str

