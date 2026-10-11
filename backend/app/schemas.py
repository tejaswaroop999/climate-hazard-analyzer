from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_year: int = Field(ge=1940)
    end_year: int = Field(ge=1940)
    hazard: Literal["heatwave"] = "heatwave"

    @model_validator(mode="after")
    def valid_period(self):
        if self.end_year < self.start_year:
            raise ValueError("end_year must be on or after start_year")
        if self.end_year >= datetime.now(timezone.utc).year:
            raise ValueError("Only completed calendar years are supported")
        if self.end_year - self.start_year + 1 > 60:
            raise ValueError("Choose at most 60 years")
        return self
