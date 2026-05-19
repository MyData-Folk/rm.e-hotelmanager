from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Hotel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True, unique=True)
    name: str
    timezone: str = 'Europe/Paris'
    currency: str = 'EUR'
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class HotelConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True, unique=True)
    config_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    source: str = 'json_upload'
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class HotelRateSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True, unique=True)
    default_reference_plan_code: str = 'OTA-RO-FLEX'
    default_reference_room_name: str = 'Double Classique'
    travco_reference_plan_code: Optional[str] = 'TRAVCO-BB-FLEX-NET'
    default_source_mode: str = 'hybrid'
    default_rounding_mode: str = 'two_decimals'
    default_rounding_increment: Optional[float] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RatePlanCatalog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    plan_code: str = Field(index=True)
    display_name: Optional[str] = None
    status: str = 'pending_configuration'
    is_reference: bool = False
    reference_role: Optional[str] = None
    created_from: str = 'manual'
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RatePlanAlias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    plan_code: str = Field(index=True)
    canonical_role: str = 'custom'
    canonical_plan_code: Optional[str] = None


class RatePlanRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    plan_code: str = Field(index=True)
    base_source: str = 'OTA'
    enabled: bool = True
    rounding_mode: str = 'two_decimals'
    rounding_increment: Optional[float] = None
    rounding_scope: str = 'final'
    priority: int = 100
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RatePlanRuleStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rule_id: int = Field(index=True, foreign_key='rateplanrule.id')
    step_order: int
    operation: str
    value: float
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Partner(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    name: str
    external_id: Optional[str] = None
    commission: float = 0
    default_discount_percentage: Optional[float] = None
    config_source: str = 'json_upload'
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PartnerRatePlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    partner_id: int = Field(index=True, foreign_key='partner.id')
    plan_code: str = Field(index=True)


class BaseRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    date: str = Field(index=True)
    room_name: str = Field(index=True)
    plan_code: str = Field(index=True)
    price: float
    source: str = 'manual_ui'
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DerivedRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    date: str = Field(index=True)
    room_name: str = Field(index=True)
    plan_code: str = Field(index=True)
    price: float
    raw_price: Optional[float] = None
    source: str = 'calculated_from_base_rate'
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ImportedRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    import_id: str = Field(index=True)
    date: str = Field(index=True)
    room_name: str = Field(index=True)
    plan_code: str = Field(index=True)
    price: Optional[float] = None
    raw_value: Optional[str] = None
    source: str = 'excel_upload'
    created_at: datetime = Field(default_factory=utc_now)


class AvailabilityCell(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    import_id: str = Field(index=True)
    date: str = Field(index=True)
    room_name: str = Field(index=True)
    raw_value: Optional[str] = None
    available_quantity: Optional[int] = None
    status: str = Field(index=True)
    label: str


class ImportMetadata(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    import_id: str = Field(index=True, unique=True)
    import_type: str
    filename: Optional[str] = None
    rows_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))


class RateChangeLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hotel_id: str = Field(index=True)
    date: Optional[str] = Field(default=None, index=True)
    room_name: Optional[str] = None
    plan_code: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    source: str = 'manual'
    created_at: datetime = Field(default_factory=utc_now)
