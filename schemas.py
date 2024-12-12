from pydantic import BaseModel, HttpUrl
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
    profile_picture: Optional[str] = "https://img.daisyui.com/images/stock/photo-1534528741775-53994a69daeb.webp"

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


class StockAnalysisRequest(BaseModel):
    symbol: str
    price: float
    change: float
    percentChange: float
    metrics: Optional[Dict[str, float]] = None
    timeframe: Optional[str] = "short-term"

class MarketAnalysisRequest(BaseModel):
    indices: Dict[str, float]
    trends: List[str]
    timeframe: Optional[str] = "short-term"

class PortfolioAnalysisRequest(BaseModel):
    holdings: List[Dict[str, float]]
    total_value: float
    cash_position: float
    risk_profile: Optional[str] = "moderate"

class StockTrade(BaseModel):
    symbol: str
    type: str  
    quantity: int
    price: float

class ProfilePictureUpdate(BaseModel):
    profile_picture: HttpUrl
