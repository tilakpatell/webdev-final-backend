from fastapi import APIRouter, HTTPException
import requests
from backend_files.database import users, trades
import os
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict
from time import sleep
from cachetools import TTLCache

load_dotenv()
router = APIRouter()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

# Cache for stock quotes (5 minutes TTL)
quote_cache = TTLCache(maxsize=100, ttl=300)

# Rate limiting
last_request_time = datetime.now()
MIN_REQUEST_INTERVAL = 12  

async def get_portfolio(user_id: str):
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    portfolio_data = {
        "cash": user.get("cash", 0),
        "positions": [],
        "total_value": user.get("cash", 0)
    }
    for symbol, quantity in user.get("portfolio", {}).items():
        if quantity > 0:
            try:
                quote = await get_stock_quote(symbol)
                position_value = quantity * quote["price"]
                portfolio_data["positions"].append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "current_price": quote["price"],
                    "current_value": position_value,
                    "change": quote["change"],
                    "percentChange": quote["percentChange"]
                })
                portfolio_data["total_value"] += position_value
            except:
                continue
                
    return portfolio_data
  
@router.get("/portfolio/{user_id}")
async def get_portfolio_route(user_id: str):
  return await get_portfolio(user_id)

def check_rate_limit():
    global last_request_time
    current_time = datetime.now()
    time_since_last_request = (current_time - last_request_time).total_seconds()
    
    if time_since_last_request < MIN_REQUEST_INTERVAL:
        sleep(MIN_REQUEST_INTERVAL - time_since_last_request)
    
    last_request_time = current_time

async def validate_trade(trade_data: Dict, user_id: str):
    """Validate trade data and check user permissions"""
    if not all(key in trade_data for key in ["symbol", "type", "quantity", "price"]):
        raise HTTPException(status_code=400, detail="Invalid trade data")
        
    if trade_data["quantity"] <= 0:
        raise HTTPException(status_code=400, detail="Invalid quantity")
        
    if trade_data["price"] <= 0:
        raise HTTPException(status_code=400, detail="Invalid price")
        
    if trade_data["type"] not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Invalid trade type")
    
    # Verify stock exists
    try:
        await get_stock_quote(trade_data["symbol"])
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid stock symbol")

@router.get("/quote/{symbol}")
async def get_stock_quote(symbol: str):
    try:
        # Check cache first
        if symbol in quote_cache:
            return quote_cache[symbol]
        
        check_rate_limit()
        
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_API_KEY
        }
        
        response = requests.get(BASE_URL, params=params)
        
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="API rate limit exceeded")
            
        data = response.json()
        
        if "Note" in data:  # Alpha Vantage rate limit message
            raise HTTPException(status_code=429, detail="API rate limit exceeded")
            
        if "Error Message" in data:
            raise HTTPException(status_code=404, detail="Stock not found")
            
        if "Global Quote" not in data or not data["Global Quote"]:
            raise HTTPException(status_code=404, detail="Stock not found")
            
        quote = data["Global Quote"]
        result = {
            "symbol": symbol,
            "price": float(quote["05. price"]),
            "change": float(quote["09. change"]),
            "percentChange": float(quote["10. change percent"].strip('%')),
            "high": float(quote["03. high"]),
            "low": float(quote["04. low"]),
            "volume": int(quote["06. volume"]),
            "latest_trading_day": quote["07. latest trading day"]
        }
        
        # Cache the result
        quote_cache[symbol] = result
        return result
        
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trade")
async def execute_trade(trade_data: dict, user_id: str):
    await validate_trade(trade_data, user_id)
    
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get current price to verify trade price is reasonable
    current_quote = await get_stock_quote(trade_data["symbol"])
    price_difference = abs(current_quote["price"] - trade_data["price"]) / current_quote["price"]
    if price_difference > 0.05:  # 5% difference
        raise HTTPException(status_code=400, detail="Trade price too far from market price")

    total = trade_data["quantity"] * trade_data["price"]

    try:
        if trade_data["type"] == "BUY":
            if user["cash"] < total:
                raise HTTPException(status_code=400, detail="Insufficient funds")
            
            users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "cash": -total,
                        f"portfolio.{trade_data['symbol']}": trade_data["quantity"]
                    }
                }
            )
        else:  # SELL
            current_quantity = user["portfolio"].get(trade_data["symbol"], 0)
            if current_quantity < trade_data["quantity"]:
                raise HTTPException(status_code=400, detail="Insufficient shares")
            
            users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "cash": total,
                        f"portfolio.{trade_data['symbol']}": -trade_data["quantity"]
                    }
                }
            )

        # Record the trade
        trade_doc = {
            "user_id": ObjectId(user_id),
            **trade_data,
            "total": total,
            "market_price": current_quote["price"],
            "timestamp": datetime.utcnow()
        }
        trades.insert_one(trade_doc)
        
        # Return updated portfolio
        return await get_portfolio(user_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trade failed: {str(e)}")

@router.get("/performance/{user_id}")
async def get_performance_metrics(user_id: str, timeframe: str = "1M"):
    user = users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_trades = list(trades.find({"user_id": ObjectId(user_id)}))
    
    total_invested = sum(trade["total"] for trade in user_trades if trade["type"] == "BUY")
    total_sold = sum(trade["total"] for trade in user_trades if trade["type"] == "SELL")
    
    portfolio_value = user["cash"]
    for symbol, quantity in user.get("portfolio", {}).items():
        if quantity > 0:
            try:
                quote = await get_stock_quote(symbol)
                portfolio_value += quantity * quote["price"]
            except:
                continue
    
    return {
        "portfolio": [portfolio_value],  
        "benchmark": [total_invested],   
        "labels": ["Current"],
        "metrics": {
            "total_invested": total_invested,
            "total_sold": total_sold,
            "current_value": portfolio_value,
            "profit_loss": portfolio_value - total_invested,
            "return_percentage": ((portfolio_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
        }
    }

@router.get("/watchlist/${userId}")
async def get_watchlist(user_id: str):
  user = users.find_one({"_id" : ObjectId(user_id)})
  if not user:
      raise HTTPException(status_code=404, detail="Invalid User/Watchlist")
  user_watchlist = user.get("watchlist", [])
  return user_watchlist
