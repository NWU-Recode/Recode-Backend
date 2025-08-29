from __future__ import annotations

from pydantic import BaseModel
from datetime import datetime


class WeekSchema(BaseModel):
    start_date: datetime
    end_date: datetime

