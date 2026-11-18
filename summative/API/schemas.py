"""Request and response models for the API."""

import difflib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from model_manager import MAX_GROUP, MAX_TERM, MODEL


def _known(field: str, value: str) -> str:
    spelled = MODEL.exact_spelling(field, value)
    if spelled is not None:
        return spelled
    close = difflib.get_close_matches(value.title(), MODEL.choices(field), n=3, cutoff=0.6)
    tip = f" Closest matches: {', '.join(close)}." if close else " See GET /choices for the full list."
    raise ValueError(f"'{value}' is not a {field} the model knows.{tip}")


class LoanApplication(BaseModel):
    """What we know about a woman-led business before the loan is posted."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={"examples": [{
            "country": "Kenya",
            "activity": "Retail",
            "repayment_interval": "monthly",
            "term_in_months": 12,
            "borrower_count": 1,
            "repeat_borrower": False,
        }]},
    )

    country: str = Field(..., min_length=3, max_length=40, description="African country of the business, e.g. Kenya, Rwanda, Ghana.")
    activity: str = Field(..., min_length=3, max_length=40, description="Kiva business activity, e.g. Retail, Farming, Tailoring.")
    repayment_interval: Literal["bullet", "irregular", "monthly", "weekly"] = Field(
        ..., description="How the loan is paid back.")
    term_in_months: int = Field(..., strict=True, ge=1, le=MAX_TERM, description=f"Loan length, 1 to {MAX_TERM} months.")
    borrower_count: int = Field(..., strict=True, ge=1, le=MAX_GROUP,
                                description=f"Number of women borrowing together, 1 to {MAX_GROUP}.")
    repeat_borrower: bool = Field(..., strict=True, description="true if she has borrowed on Kiva before.")

    @field_validator("country")
    @classmethod
    def country_is_known(cls, value: str) -> str:
        return _known("country", value)

    @field_validator("activity")
    @classmethod
    def activity_is_known(cls, value: str) -> str:
        return _known("activity", value)

    @field_validator("repayment_interval", mode="before")
    @classmethod
    def lower_case_schedule(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class LoanEstimate(BaseModel):
    estimated_loan_usd: float = Field(description="Most likely loan size in US dollars.")
    likely_range_usd: list[float] = Field(description="Half of similar test loans fell inside this range.")
    sector: str
    model: str
    model_version: int
