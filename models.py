from datetime import datetime
from typing import Dict, List
from pydantic import BaseModel

class User(BaseModel):
  username: str
  email: str
  password: str
  firstName: str
  lastName: str
  socialsecurity: str
  role: str = "USER"
  membership: str = "REGULAR"  # "REGULAR" or "GOLD"
  watchlist: List[str] = []
  cash: float = 25000.0
  portfolio: Dict[str, float] = {}
  dob: str
  created_at: datetime = datetime.now()
