from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Literal

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
