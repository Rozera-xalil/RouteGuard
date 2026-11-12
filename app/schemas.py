from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from routeguard.config import BR_STATES


class OrderInput(BaseModel):
    """Everything below is known when the customer places the order."""

    order_id: str | None = Field(None, examples=["ORD-1001"])
    seller_id: str | None = Field(
        None, description="Optional. Lets the model use this seller's delivery track record."
    )
    order_purchase_timestamp: datetime = Field(..., examples=["2018-05-14T10:23:00"])
    order_estimated_delivery_date: datetime = Field(
        ..., description="The delivery date promised to the customer.", examples=["2018-05-28T00:00:00"]
    )

    customer_state: str = Field(..., examples=["RJ"])
    seller_state: str = Field(..., examples=["SP"])
    customer_zip_code_prefix: int = Field(..., ge=1000, le=99999, examples=[27277])
    seller_zip_code_prefix: int = Field(..., ge=1000, le=99999, examples=[14409])

    total_items: int = Field(..., ge=1, le=100, examples=[2])
    num_sellers: int = Field(1, ge=1, le=20)
    total_item_price: float = Field(..., ge=0, le=100000, examples=[150.0])
    total_freight: float = Field(..., ge=0, le=10000, examples=[25.5])
    avg_item_price: float = Field(..., ge=0, le=100000, examples=[75.0])
    num_categories: int = Field(1, ge=1, le=50)
    avg_product_weight_g: float | None = Field(None, ge=0, le=500000, examples=[800.0])
    avg_volume_cm3: float | None = Field(None, ge=0, le=5000000, examples=[6000.0])

    max_installments: int = Field(1, ge=0, le=36)
    total_payment_value: float = Field(..., ge=0, le=200000, examples=[175.5])
    payment_types_used: str = Field("credit_card", examples=["credit_card"])

    @field_validator("customer_state", "seller_state")
    @classmethod
    def _state(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in BR_STATES:
            raise ValueError(f"unknown Brazilian state code '{v}'")
        return v

    @model_validator(mode="after")
    def _dates(self):
        if self.order_estimated_delivery_date <= self.order_purchase_timestamp:
            raise ValueError("order_estimated_delivery_date must be after order_purchase_timestamp")
        return self


class Reason(BaseModel):
    feature: str
    label: str
    value: str | None
    impact: float
    direction: Literal["raises", "lowers"]


class PredictionResult(BaseModel):
    prediction_id: str
    order_id: str | None = None
    probability: float
    predicted_late: bool
    risk_level: Literal["low", "medium", "high"]
    threshold: float
    reasons: list[Reason]
    model_version: str


class BatchRequest(BaseModel):
    orders: list[OrderInput] = Field(..., min_length=1, max_length=500)


class BatchResponse(BaseModel):
    predictions: list[PredictionResult]
    total_count: int
    model_version: str


class FeedbackRequest(BaseModel):
    prediction_id: str
    actual_late: bool


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    model_loaded: bool
    model_version: str | None = None
