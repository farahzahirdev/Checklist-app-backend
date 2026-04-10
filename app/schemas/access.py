from datetime import datetime

from pydantic import BaseModel


class AccessWindowResponse(BaseModel):
    activated_at: datetime
    expires_at: datetime