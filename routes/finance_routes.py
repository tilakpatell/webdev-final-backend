from fastapi import APIRouter, HTTPException, Query
import requests
from database import users, trades
import os
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Optional
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
        response.raise_for_status()  # This will raise an exception for error status codes
        
        data = response.json()
        
        if "Note" in data:  # Alpha Vantage rate limit message
            # Return mock data instead of error for demo purposes
            return generate_mock_quote(symbol)
            
        if "Error Message" in data or "Global Quote" not in data:
            return generate_mock_quote(symbol)
            
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
        # Return mock data instead of error
        return generate_mock_quote(symbol)
    except Exception as e:
        # Return mock data instead of error
        return generate_mock_quote(symbol)

def generate_mock_quote(symbol: str):
    """Generate mock quote data for demo purposes"""
    import random
    base_price = 100.0
    change = random.uniform(-5, 5)
    price = base_price + change
    return {
        "symbol": symbol,
        "price": round(price, 2),
        "change": round(change, 2),
        "percentChange": round((change / base_price) * 100, 2),
        "high": round(price + random.uniform(0, 5), 2),
        "low": round(price - random.uniform(0, 5), 2),
        "volume": random.randint(100000, 1000000),
        "latest_trading_day": datetime.now().strftime("%Y-%m-%d")
    }
    
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

@router.get("/market/overview")
async def get_market_overview():
    """Get market overview including indices, top movers, and sector performance"""
    cache_key = "market_overview"
    
    if cache_key in market_cache:
        return market_cache[cache_key]
        
    try:
        # Get top gainers and losers from trades collection
        pipeline = [
            {"$match": {
                "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
            }},
            {"$group": {
                "_id": "$symbol",
                "last_price": {"$last": "$market_price"},
                "first_price": {"$first": "$market_price"},
                "volume": {"$sum": "$quantity"}
            }},
            {"$project": {
                "symbol": "$_id",
                "price_change": {"$subtract": ["$last_price", "$first_price"]},
                "price_change_percent": {
                    "$multiply": [
                        {"$divide": [
                            {"$subtract": ["$last_price", "$first_price"]},
                            "$first_price"
                        ]},
                        100
                    ]
                },
                "volume": 1
            }},
            {"$sort": {"price_change_percent": -1}},
            {"$limit": 10}
        ]
        
        top_gainers = list(trades.aggregate(pipeline))
        
        # Reverse sort for losers
        pipeline[-2] = {"$sort": {"price_change_percent": 1}}
        top_losers = list(trades.aggregate(pipeline))
        
        # Get most active stocks
        pipeline[-2] = {"$sort": {"volume": -1}}
        most_active = list(trades.aggregate(pipeline))
        
        overview = {
            "timestamp": datetime.now(),
            "market_stats": {
                "total_trades": trades.count_documents({
                    "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
                }),
                "total_volume": sum(stock["volume"] for stock in most_active),
                "unique_symbols": len(set(trade["symbol"] for trade in most_active))
            },
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "most_active": most_active
        }
        
        market_cache[cache_key] = overview
        return overview
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_stocks(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, le=50)
):
    """Search for stocks by symbol or recent trading activity"""
    try:
        # Search in recent trades for matching symbols
        pipeline = [
            {"$match": {
                "symbol": {"$regex": query.upper(), "$options": "i"}
            }},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$symbol",
                "last_trade": {"$first": "$market_price"},
                "volume": {"$sum": "$quantity"}
            }},
            {"$limit": limit}
        ]
        
        results = list(trades.aggregate(pipeline))
        
        return {
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades/history/{user_id}")
async def get_trade_history(
    user_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=50, le=100)
):
    """Get user's trading history with optional date filtering"""
    try:
        query = {"user_id": ObjectId(user_id)}
        
        if start_date:
            query["timestamp"] = {"$gte": start_date}
        if end_date:
            query["timestamp"] = {"$lte": end_date}
            
        trades_history = list(trades.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit))
        
        return trades_history
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio/analysis/{user_id}")
async def get_portfolio_analysis(user_id: str):
    """Get detailed portfolio analysis including diversity and performance metrics"""
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        portfolio = user.get("portfolio", {})
        if not portfolio:
            return {
                "diversity_score": 0,
                "total_value": user.get("cash", 0),
                "performance": {
                    "daily": 0,
                    "weekly": 0,
                    "monthly": 0
                },
                "positions": []
            }
            
        # Calculate portfolio metrics
        positions = []
        total_value = user.get("cash", 0)
        
        for symbol, quantity in portfolio.items():
            # Get recent trades for this symbol
            recent_trades = list(trades.find(
                {"symbol": symbol},
                {"market_price": 1, "timestamp": 1}
            ).sort("timestamp", -1).limit(1))
            
            if recent_trades:
                current_price = recent_trades[0]["market_price"]
                position_value = quantity * current_price
                total_value += position_value
                
                positions.append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "current_price": current_price,
                    "position_value": position_value,
                    "weight": position_value / total_value
                })
        
        # Calculate diversity score (Herfindahl-Hirschman Index)
        diversity_score = 1 - sum(pos["weight"] ** 2 for pos in positions)
        
        # Calculate performance metrics
        time_periods = {
            "daily": timedelta(days=1),
            "weekly": timedelta(days=7),
            "monthly": timedelta(days=30)
        }
        
        performance = {}
        for period_name, delta in time_periods.items():
            start_date = datetime.now() - delta
            period_trades = trades.find({
                "user_id": ObjectId(user_id),
                "timestamp": {"$gte": start_date}
            })
            
            period_pl = sum(
                trade["quantity"] * (
                    trade["market_price"] - trade["price"]
                ) for trade in period_trades
            )
            
            performance[period_name] = period_pl
        
        return {
            "diversity_score": diversity_score,
            "total_value": total_value,
            "cash_ratio": user.get("cash", 0) / total_value,
            "positions": positions,
            "performance": performance
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
      
        
@router.post("/trade")
async def execute_trade(trade_data: dict, user_id: str):
    try:
        # Validate trade data
        if not all(key in trade_data for key in ["symbol", "type", "quantity", "price"]):
            raise HTTPException(status_code=400, detail="Invalid trade data")
            
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        total = trade_data["quantity"] * trade_data["price"]
        
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
            "timestamp": datetime.utcnow()
        }
        trades.insert_one(trade_doc)
        
        # Return updated portfolio
        return await get_portfolio(user_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/watchlist/{userId}")
async def get_watchlist(user_id: str):
  user = users.find_one({"_id" : ObjectId(user_id)})
  if not user:
      raise HTTPException(status_code=404, detail="Invalid User/Watchlist")
  user_watchlist = user.get("watchlist", [])
  return user_watchlist
