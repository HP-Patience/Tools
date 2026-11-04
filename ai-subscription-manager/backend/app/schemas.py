from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Contact(Input):
    kind: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=200)


class CustomerInput(Input):
    name: str = Field(min_length=1, max_length=200)
    contacts: list[Contact] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=10000)


class SupplierInput(Input):
    name: str = Field(min_length=1, max_length=200)
    url: str = ""
    contact_name: str = ""
    contact_details: str = ""
    notes: str = ""
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def valid_url(cls, v):
        from urllib.parse import urlparse

        if v and (urlparse(v).scheme not in ("http", "https") or not urlparse(v).netloc):
            raise ValueError("网址只支持 http 或 https")
        return v


Unit = Literal["day", "week", "month", "year"]


def validate_quota(amount, unit):
    if (amount is not None) != bool(unit):
        raise ValueError("额度和单位应同时填写")
    if amount is not None:
        try:
            value = Decimal(amount)
            if (
                not value.is_finite()
                or value < 0
                or value >= Decimal("1e14")
                or value.as_tuple().exponent < -4
            ):
                raise ValueError("额度最多四位小数且应为非负数")
        except InvalidOperation:
            raise ValueError("额度无效")


class ProductInput(Input):
    name: str = Field(min_length=1, max_length=200)
    supplier_id: int = Field(gt=0)
    platform: str = ""
    plan: str = ""
    delivery: str = ""
    source_name: str = ""
    source_url: str = ""
    tags: list[str] = Field(default_factory=list)
    cost_fen: int = Field(default=0, ge=0, le=999999999999, strict=True)
    price_fen: int = Field(default=0, ge=0, le=999999999999, strict=True)
    quoted_on: date | None = None
    term_count: int | None = Field(default=None, ge=1, le=10000)
    term_unit: Unit | None = None
    quota_amount: str | None = None
    quota_unit: str | None = None
    warranty_notes: str = ""
    is_active: bool = True

    @field_validator("source_url")
    @classmethod
    def valid_url(cls, v):
        return SupplierInput.valid_url(v)

    @model_validator(mode="after")
    def pairs(self):
        if bool(self.term_count) != bool(self.term_unit):
            raise ValueError("期限数量和单位应同时填写")
        validate_quota(self.quota_amount, self.quota_unit)
        return self


class SaleInput(Input):
    customer_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    sold_on: date
    cost_fen: int = Field(ge=0, le=999999999999, strict=True)
    price_fen: int = Field(ge=0, le=999999999999, strict=True)
    submission_id: UUID
    started_on: date | None = None
    expires_on: date | None = None
    term_count: int | None = Field(default=None, ge=1, le=10000)
    term_unit: Unit | None = None
    quota_amount: str | None = None
    quota_unit: str | None = None
    identifier: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=10000)
    expected_revision: int | None = None

    @model_validator(mode="after")
    def pairs(self):
        if bool(self.term_count) != bool(self.term_unit):
            raise ValueError("期限数量和单位应同时填写")
        validate_quota(self.quota_amount, self.quota_unit)
        return self


class ServiceState(Input):
    expires_on: date | None
    ended: bool
    purchased_quota: str

    @field_validator("purchased_quota")
    @classmethod
    def quota(cls, v):
        validate_quota(v, "unit")
        return v


class VoidInput(Input):
    reason: str = Field(min_length=1, max_length=1000)
    expected_revision: int
    service_state: ServiceState


class CorrectionInput(VoidInput):
    cost_fen: int = Field(ge=0, le=999999999999, strict=True)
    price_fen: int = Field(ge=0, le=999999999999, strict=True)
    sold_on: date
