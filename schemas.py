from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Literal, Optional

class UserLogin(BaseModel):
    username: str
    password: str

class UserSignup(BaseModel):
    username: str
    email: str
    password: str
    firstName: str
    lastName: str
    dob: str
    socialsecurity: str

class StockQuote(BaseModel):
    symbol: str
    price: float
    change: float
    percentChange: float

class TradeRequest(BaseModel):
    symbol: str
    type: str
    quantity: float
    price: float

class ChatRequest(BaseModel):
    message: str
    chat_history: List[Dict] = []
    
class OptionTradeRequest(BaseModel):
    user_id: str
    symbol: str
    option_type: Literal["CALL", "PUT"]
    strike: float
    premium: float
    expiration: str
    trade_type: Literal["BUY", "SELL"]
    quantity: int

class Position(BaseModel):
    symbol: str
    quantity: float
    current_price: float
    current_value: float
    change: float = 0
    percentChange: float = 0

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

class SectorAllocation(BaseModel):
    sector: str
    value: float
    percentage: float
    color: str

class PortfolioSummary(BaseModel):
    total_value: float = 25000.0
    total_gain_loss: float = 0
    total_gain_loss_percentage: float = 0
    sector_allocation: List[SectorAllocation]
    positions: List[Position] = []

class PerformanceHistory(BaseModel):
    dates: List[str]
    values: List[float]
