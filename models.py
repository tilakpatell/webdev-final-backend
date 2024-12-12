from datetime import datetime
from typing import Dict, List, Optional
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
  goals: List[Dict] = []
  
class Goal(BaseModel):
    id: str
    name: str
    current: float
    target: float
    percentage: float
    category: str
    targetDate: str

class Position(BaseModel):
    symbol: str
    quantity: float
    current_price: float
    current_value: float
    change: Optional[float] = None
    percentChange: Optional[float] = None

class PortfolioData(BaseModel):
    cash: float
    positions: List[Position]
    total_value: float
    initial_investment: Optional[float] = None
    sectors: Optional[Dict[str, Dict[str, float]]] = None

class SectorData(BaseModel):
    sector: str
    value: float
    percentage: float
    color: str

class PortfolioSummary(BaseModel):
    total_value: float
    total_gain_loss: float
    total_gain_loss_percentage: float
    sector_allocation: List[SectorData]
