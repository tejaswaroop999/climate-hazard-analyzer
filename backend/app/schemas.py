from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_year: int = Field(ge=1940)
    end_year: int = Field(ge=1940)
    hazard: Literal["heatwave"] = "heatwave"

    @field_validator("latitude", "longitude")
    @classmethod
    def round_coordinates(cls, value):
        # 0.01 degrees (~1 km) is far finer than the ~0.25 degree ERA5 grid, so
        # rounding only matters right on a cell boundary, and it stops
        # near-identical points fragmenting the cache or forcing new downloads.
        return round(value, 2)

    @model_validator(mode="after")
    def valid_period(self):
        if self.end_year < self.start_year:
            raise ValueError("end_year must be on or after start_year")
        if self.end_year >= datetime.now(UTC).year:
            raise ValueError("Only completed calendar years are supported")
        if self.end_year - self.start_year + 1 > 60:
            raise ValueError("Choose at most 60 years")
        return self
