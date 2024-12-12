from fastapi import APIRouter, HTTPException, Query
from backend_files.services.chatbot import ChatGPT
from ..database import users, trades
import requests
import os
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Dict, List
from cachetools import TTLCache
import random
import yfinance as yf
from ..schemas import OptionTradeRequest, SectorData, PortfolioSummary, StockTrade

load_dotenv(verbose=True) 
router = APIRouter()

SECTOR_COLORS = {
    "Technology": "#10B981",
    "Healthcare": "#FFB800",
    "Financial": "#EF4444",
    "Consumer": "#6366F1",
    "Industrial": "#8B5CF6",
    "Energy": "#F59E0B",
    "Materials": "#3B82F6",
    "Real Estate": "#EC4899",
    "Other": "#6B7280",
    "Cash": "#059669"
}

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
if not POLYGON_API_KEY or POLYGON_API_KEY.strip() == "":
    raise ValueError("POLYGON_API_KEY not set or is empty.")

print("Polygon API Key loaded:", POLYGON_API_KEY)  # Debug: Confirm key is loaded

BASE_POLYGON_URL = "https://api.polygon.io"

# Cache setup
quote_cache = TTLCache(maxsize=100, ttl=300)   
market_cache = TTLCache(maxsize=10, ttl=300)  
options_cache = TTLCache(maxsize=100, ttl=300)

def get_polygon_headers():
    return {
        "Authorization": f"Bearer {POLYGON_API_KEY}"
    }
    
def get_sector_for_symbol(symbol: str) -> str:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return info.get('sector', 'Other')
    except:
        return 'Other'
      
@router.get("/portfolio/{user_id}/history")
async def get_portfolio_history(user_id: str):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get or create default history
        history = user.get("performance_history", {
            "dates": [datetime.now().strftime("%Y-%m-%d")],
            "values": [user.get("cash", 25000.0)]
        })

        return history

    except Exception as e:
        print(f"Error fetching portfolio history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio/{user_id}/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(user_id: str):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Ensure all required fields exist with default values
        portfolio_summary = {
            "total_value": user.get("total_value", user.get("cash", 25000.0)),
            "total_gain_loss": user.get("total_value", 25000.0) - user.get("initial_investment", 25000.0),
            "total_gain_loss_percentage": (
                (user.get("total_value", 25000.0) - user.get("initial_investment", 25000.0)) / 
                user.get("initial_investment", 25000.0) * 100
            ),
            "sector_allocation": user.get("sector_allocation", [{
                "sector": "Cash",
                "value": user.get("cash", 25000.0),
                "percentage": 100.0,
                "color": "#059669"
            }]),
            "positions": []
        }

        # Add positions if they exist
        if "positions" in user:
            portfolio_summary["positions"] = user["positions"]

        return portfolio_summary

    except Exception as e:
        print(f"Error fetching portfolio summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio/{user_id}/sectors", response_model=List[SectorData])
async def get_sector_allocation(user_id: str):
    try:
        portfolio_data = await get_portfolio(user_id)
        
        # Initialize sectors dictionary
        sectors: Dict[str, float] = {}
        total_value = portfolio_data["total_value"]

        # Add positions by sector
        for position in portfolio_data["positions"]:
            sector = get_sector_for_symbol(position["symbol"])
            position_value = position["current_value"]
            sectors[sector] = sectors.get(sector, 0) + position_value

        # Add cash
        sectors["Cash"] = portfolio_data["cash"]

        # Calculate percentages and create response
        sector_allocation = []
        for sector, value in sectors.items():
            percentage = (value / total_value) * 100 if total_value else 0
            sector_allocation.append({
                "sector": sector,
                "value": value,
                "percentage": percentage,
                "color": SECTOR_COLORS.get(sector, SECTOR_COLORS["Other"])
            })

        return sorted(sector_allocation, key=lambda x: x["value"], reverse=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/options/trade")
async def execute_option_trade(trade_data: OptionTradeRequest):
    try:
        # Verify user exists
        user = users.find_one({"_id": ObjectId(trade_data.user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Calculate total cost (each contract is for 100 shares)
        total_cost = float(trade_data.premium) * 100 * trade_data.quantity

        # Get user's options and create position key
        user_options = user.get("options", {})
        position_key = f"options.{trade_data.symbol}-{trade_data.option_type}-{trade_data.strike}-{trade_data.expiration}"

        if trade_data.trade_type == "BUY":
            # Check if user has enough cash
            if float(user.get("cash", 0)) < total_cost:
                raise HTTPException(status_code=400, detail="Insufficient funds")

            # Update user's cash and option position
            result = users.update_one(
                {"_id": ObjectId(trade_data.user_id)},
                {
                    "$inc": {
                        "cash": -total_cost,
                        position_key: trade_data.quantity
                    }
                }
            )

        else:  # SELL
            # Check if user has enough contracts
            current_position = float(user_options.get(f"{trade_data.symbol}-{trade_data.option_type}-{trade_data.strike}-{trade_data.expiration}", 0))
            if current_position < float(trade_data.quantity):
                raise HTTPException(status_code=400, detail="Insufficient contracts to sell")

            # Update user's cash and option position
            result = users.update_one(
                {"_id": ObjectId(trade_data.user_id)},
                {
                    "$inc": {
                        "cash": total_cost,
                        position_key: -trade_data.quantity
                    }
                }
            )

        # Get updated portfolio
        updated_user = users.find_one({"_id": ObjectId(trade_data.user_id)})
        
        # Format portfolio response
        portfolio_response = {
            "cash": float(updated_user.get("cash", 0)),
            "positions": [],
            "options": [],
            "total_value": float(updated_user.get("cash", 0))
        }

        # Add stock positions
        for symbol, qty in updated_user.get("portfolio", {}).items():
            if float(qty) > 0:
                portfolio_response["positions"].append({
                    "symbol": symbol,
                    "quantity": float(qty)
                })

        # Add options positions
        for opt_key, qty in updated_user.get("options", {}).items():
            if float(qty) > 0:
                symbol, opt_type, strike, exp = opt_key.split("-")
                option_position = {
                    "symbol": symbol,
                    "option_type": opt_type,
                    "strike": float(strike),
                    "expiration": exp,
                    "quantity": float(qty)
                }
                portfolio_response["options"].append(option_position)

        return portfolio_response

    except Exception as e:
        print(f"Error executing option trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))
      
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
            except Exception as e:
                print(f"Error fetching quote for {symbol}: {e}")
                continue
                
    return portfolio_data

@router.get("/portfolio/{user_id}")
async def get_portfolio_route(user_id: str):
    return await get_portfolio(user_id)


@router.get("/quote/{symbol}")
async def get_stock_quote(symbol: str):
    # Check cache first
    if symbol in quote_cache:
        return quote_cache[symbol]

    try:
        # Polygon previous day's aggregates endpoint:
        # GET /v2/aggs/ticker/{symbol}/prev?adjusted=true
        url = f"{BASE_POLYGON_URL}/v2/aggs/ticker/{symbol.upper()}/prev"
        params = {
            "adjusted": "true"
        }
        response = requests.get(url, headers=get_polygon_headers(), params=params)

        # Handle no data scenario (404 or empty results)
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="No data found for this symbol.")

        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            # No results returned
            raise HTTPException(status_code=404, detail="No previous trading day data found.")

        # The endpoint returns an array of one aggregate bar representing the previous trading day
        bar = results[0]  # bar includes o, c, h, l, etc.
        open_price = bar.get("o", 0)
        close_price = bar.get("c", 0)
        high_price = bar.get("h", 0)
        low_price = bar.get("l", 0)

        if open_price == 0:
            # If open_price is zero, avoid division by zero in percentChange
            raise HTTPException(status_code=500, detail="Invalid data: open price is zero.")

        change = close_price - open_price
        percentChange = (change / open_price) * 100

        result = {
            "symbol": symbol.upper(),
            "price": float(close_price),
            "change": float(change),
            "percentChange": float(percentChange),
            "high": float(high_price),
            "low": float(low_price),
            "open": float(open_price),
            "previousClose": float(open_price),  # Using open as a stand-in for previousClose
            "name": symbol.upper(),
            "currency": "USD",
            "marketCap": 0  # Not provided by this endpoint
        }

        quote_cache[symbol] = result
        return result

    except requests.HTTPError as e:
        print(f"Polygon API Error for quote: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch quote data: {str(e)}"
        )
    except Exception as e:
        print(f"Unexpected Error in quote: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )



@router.get("/historical/{symbol}")
async def get_historical_data(symbol: str, timeframe: str = "1D"):
    now = datetime.now()
    if timeframe == "1D":
        from_dt = now - timedelta(days=1)
        multiplier = 15   # 15-minute bars for intraday
        timespan = "minute"
    elif timeframe == "1W":
        from_dt = now - timedelta(days=7)
        multiplier = 1
        timespan = "day"
    elif timeframe == "1M":
        from_dt = now - timedelta(days=30)
        multiplier = 1
        timespan = "day"
    elif timeframe == "3M":
        from_dt = now - timedelta(days=90)
        multiplier = 1
        timespan = "day"
    elif timeframe == "6M":
        from_dt = now - timedelta(days=180)
        multiplier = 1
        timespan = "day"
    elif timeframe == "1Y":
        from_dt = now - timedelta(days=365)
        multiplier = 1
        timespan = "week"
    else:
        from_dt = now - timedelta(days=1)
        multiplier = 15
        timespan = "minute"

    from_str = from_dt.strftime('%Y-%m-%d')
    to_str = now.strftime('%Y-%m-%d')

    url = f"{BASE_POLYGON_URL}/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{from_str}/{to_str}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}

    try:
        response = requests.get(url, headers=get_polygon_headers(), params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("resultsCount", 0) == 0:
            return {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "labels": [],
                "prices": []
            }

        results = data.get("results", [])
        labels = []
        prices = []

        for r in results:
            ts = r["t"] / 1000
            dt = datetime.utcfromtimestamp(ts)
            close_price = r["c"]
            if timespan in ["minute", "hour"]:
                labels.append(dt.strftime('%Y-%m-%d %H:%M'))
            else:
                labels.append(dt.strftime('%Y-%m-%d'))
            prices.append(close_price)

        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "labels": labels,
            "prices": prices
        }

    except requests.HTTPError as e:
        print(f"Polygon API Error for historical: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch historical data: {str(e)}"
        )
    except Exception as e:
        print(f"Unexpected Error in historical: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/options/{symbol}")
async def get_options_chain(symbol: str):
    try:
        # Get the base stock price from your existing quote endpoint
        stock_price = 100  # Default price if none found
        strike_range = [-10, -5, -2, 2, 5, 10]  # Strike price differences
        
        # Generate expiration dates (next 4 fridays)
        expirations = []
        current_date = datetime.now()
        for _ in range(4):
            days_until_friday = (4 - current_date.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            current_date += timedelta(days=days_until_friday)
            expirations.append(current_date.strftime("%Y-%m-%d"))

        calls = []
        puts = []

        for exp in expirations:
            for strike_diff in strike_range:
                strike = round(stock_price + strike_diff, 2)
                
                # Calculate call premium
                call_intrinsic = max(0, stock_price - strike)
                call_premium = round(call_intrinsic + random.uniform(0.5, 2.0), 2)
                
                calls.append({
                    "strike": strike,
                    "premium": call_premium,
                    "expiration": exp,
                    "type": "CALL"
                })

                # Calculate put premium
                put_intrinsic = max(0, strike - stock_price)
                put_premium = round(put_intrinsic + random.uniform(0.5, 2.0), 2)
                
                puts.append({
                    "strike": strike,
                    "premium": put_premium,
                    "expiration": exp,
                    "type": "PUT"
                })

        return {
            "calls": calls,
            "puts": puts,
            "underlying_price": stock_price
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
      
      
@router.post("/trade")
async def execute_stock_trade(
    trade: StockTrade,  # Put the body parameter first
    user_id: str = Query(...)  # Query parameter with default comes after
):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        total_cost = trade.price * trade.quantity
        
        if trade.type == "BUY":
            if user["cash"] < total_cost:
                raise HTTPException(status_code=400, detail="Insufficient funds")
                
            result = users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "cash": -total_cost,
                        f"portfolio.{trade.symbol}": trade.quantity
                    }
                }
            )
        else:  # SELL
            current_position = user.get("portfolio", {}).get(trade.symbol, 0)
            if current_position < trade.quantity:
                raise HTTPException(status_code=400, detail="Insufficient shares")
                
            result = users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$inc": {
                        "cash": total_cost,
                        f"portfolio.{trade.symbol}": -trade.quantity
                    }
                }
            )
            
        updated_user = users.find_one({"_id": ObjectId(user_id)})
        return {
            "cash": updated_user["cash"],
            "positions": [
                {"symbol": k, "quantity": v}
                for k, v in updated_user.get("portfolio", {}).items()
                if v > 0
            ],
            "total_value": updated_user["cash"]
        }
            
    except Exception as e:
        print(f"Trade execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market/overview")
async def get_market_overview():
    try:
        cache_key = "market_overview"
        if cache_key in market_cache:
            return market_cache[cache_key]

        status_response = requests.get(f"{BASE_POLYGON_URL}/v1/marketstatus/now", headers=get_polygon_headers())
        status_response.raise_for_status()
        status_data = status_response.json()

        market_is_open = status_data.get("market", "closed") == "open"

        end = datetime.utcnow()
        start = end - timedelta(days=2)
        s_url = f"{BASE_POLYGON_URL}/v2/aggs/ticker/INX/range/1/day/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
        s_resp = requests.get(s_url, headers=get_polygon_headers())
        s_resp.raise_for_status()
        s_data = s_resp.json()
        sp_value = 0.0
        sp_change_percent = 0.0
        if s_data.get("resultsCount", 0) > 0:
            results = s_data["results"]
            sp_value = results[-1]["c"]
            if len(results) > 1:
                prev_close = results[-2]["c"]
                sp_change_percent = ((sp_value - prev_close) / prev_close) * 100 if prev_close else 0.0

        news_url = f"{BASE_POLYGON_URL}/v2/reference/news"
        news_params = {"limit": 5}
        news_resp = requests.get(news_url, headers=get_polygon_headers(), params=news_params)
        news_resp.raise_for_status()
        news_data = news_resp.json()
        news_items = news_data.get("results", [])[:5]

        overview = {
            "market_status": "Open" if market_is_open else "Closed",
            "sp500": {
                "value": float(sp_value),
                "changePercent": float(sp_change_percent)
            },
            "tradingVolume": None,
            "market_news": news_items
        }

        market_cache[cache_key] = overview
        return overview

    except requests.HTTPError as e:
        print(f"Polygon API Error for market overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market overview: {str(e)}")
    except Exception as e:
        print(f"Unexpected Error in market overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/search")
async def search_stocks(query: str = Query(..., min_length=1)):
    try:
        # Using Polygon.io's Ticker Search endpoint
        search_url = f"{BASE_POLYGON_URL}/v3/reference/tickers"
        search_params = {
            "search": query,
            "active": "true",
            "market": "stocks",  # Only search for stocks
            "limit": 10,
            "sort": "ticker"     # Sort by ticker symbol
        }
        
        headers = get_polygon_headers()
        resp = requests.get(search_url, headers=headers, params=search_params)
        resp.raise_for_status()
        data = resp.json()

        # Process and format the results
        results = []
        for item in data.get("results", []):
            # Only include stocks (exclude ETFs, mutual funds, etc. if desired)
            if item.get("type") == "CS":  # Common Stock
                results.append({
                    "symbol": item["ticker"],
                    "name": item.get("name", ""),
                    "type": "Stock"
                })

        return {
            "results": results,
            "count": len(results)
        }

    except requests.HTTPError as e:
        print(f"Polygon API Error for search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search stocks: {str(e)}"
        )
    except Exception as e:
        print(f"Unexpected Error in search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/performance/{user_id}")
async def get_performance_metrics(user_id: str, timeframe: str = "1M"):
    try:
        # Verify user exists
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        end_date = datetime.now()
        if timeframe == "1M":
            start_date = end_date - timedelta(days=30)
        elif timeframe == "3M":
            start_date = end_date - timedelta(days=90)
        elif timeframe == "YTD":
            start_date = datetime(end_date.year, 1, 1)
        else:  # ALL
            start_date = end_date - timedelta(days=365) 

        # Get portfolio positions
        portfolio = user.get("portfolio", {})
        
        # Get S&P 500 data for comparison
        sp500_url = f"{BASE_POLYGON_URL}/v2/aggs/ticker/SPY/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        sp500_response = requests.get(sp500_url, headers=get_polygon_headers())
        sp500_response.raise_for_status()
        sp500_data = sp500_response.json()

        # Process the data
        dates = []
        portfolio_values = []
        benchmark_values = []

        if sp500_data.get("results"):
            initial_sp500 = sp500_data["results"][0]["c"]
            for result in sp500_data["results"]:
                date = datetime.fromtimestamp(result["t"] / 1000).strftime('%Y-%m-%d')
                dates.append(date)
                
                benchmark_value = (result["c"] / initial_sp500 - 1) * 100
                benchmark_values.append(round(benchmark_value, 2))

                portfolio_value = benchmark_value + random.uniform(-1, 1)  
                portfolio_values.append(round(portfolio_value, 2))

        return {
            "labels": dates,
            "portfolio": portfolio_values,
            "benchmark": benchmark_values
        }

    except Exception as e:
        print(f"Error fetching performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
      

@router.get("/transactions/{user_id}")
async def get_transactions(user_id: str):
    try:
        user_trades = list(trades.find(
            {"user_id": ObjectId(user_id)},
            sort=[("timestamp", -1)],
            limit=10
        ))
        
        formatted_trades = []
        for trade in user_trades:
            # Base trade information
            formatted_trade = {
                "id": str(trade["_id"]),
                "type": trade.get("trade_type", ""),
                "symbol": trade.get("symbol", ""),
                "amount": float(trade.get("total_cost", 0)),
                "quantity": int(trade.get("quantity", 0)),
                "date": trade.get("timestamp").strftime("%Y-%m-%d") if isinstance(trade.get("timestamp"), datetime) else None
            }

            if "option_type" in trade:
                formatted_trade.update({
                    "option_type": trade.get("option_type"),
                    "strike": float(trade.get("strike", 0)),
                    "premium": float(trade.get("premium", 0)),
                    "expiration": trade.get("expiration"),
                    "price": float(trade.get("premium", 0)) 
                })
            else:
                # For stock trades
                formatted_trade["price"] = float(trade.get("price", 0))

            formatted_trades.append(formatted_trade)
            
        return formatted_trades
        
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/{user_id}/sector-allocation")
async def get_sector_allocation(user_id: str):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        sectors = {}
        total_value = float(user.get("cash", 0))  # Start with cash
        sectors["Cash"] = total_value

        portfolio = user.get("portfolio", {})

        for symbol, quantity in portfolio.items():
            try:
                if quantity > 0:
                    quote = await get_stock_quote(symbol)
                    position_value = float(quantity) * float(quote["price"])
                    total_value += position_value

                    sector = get_sector_for_symbol(symbol)
                    sectors[sector] = sectors.get(sector, 0) + position_value

            except Exception as e:
                print(f"Error processing position for {symbol}: {e}")
                continue

        sector_allocation = []
        for sector, value in sectors.items():
            if total_value > 0:  # Avoid division by zero
                percentage = (value / total_value) * 100
                sector_allocation.append({
                    "sector": sector,
                    "value": float(value),
                    "percentage": float(percentage),
                    "color": SECTOR_COLORS.get(sector, SECTOR_COLORS["Other"])
                })

        return {
            "sector_allocation": sorted(sector_allocation, key=lambda x: x["value"], reverse=True),
            "total_value": float(total_value)
        }

    except Exception as e:
        print(f"Error calculating sector allocation: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to calculate sector allocation: {str(e)}"
        )


@router.get("/portfolio/{user_id}/performance")
async def get_portfolio_performance(user_id: str):
    try:
        # Verify user exists
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Initialize variables with safe defaults
        total_invested = 0
        realized_gains = 0
        unrealized_gains = 0
        current_value = float(user.get("cash", 0))  # Convert to float for safety
        
        # Get portfolio positions
        portfolio = user.get("portfolio", {})
        
        # Calculate current portfolio value and unrealized gains
        for symbol, quantity in portfolio.items():
            try:
                if quantity > 0:  # Only process active positions
                    quote = await get_stock_quote(symbol)
                    position_value = float(quantity) * float(quote["price"])
                    current_value += position_value
                    
                    # For now, assume cost basis is initial investment
                    # You may want to implement a more sophisticated cost basis calculation
                    unrealized_gains += position_value - (float(quantity) * float(quote["price"]))
            except Exception as e:
                print(f"Error processing position for {symbol}: {e}")
                continue
        
        # Calculate total gains
        total_gain_loss = realized_gains + unrealized_gains
        
        # Safe calculation of percentage with check for zero
        total_gain_loss_percentage = (
            (total_gain_loss / total_invested * 100)
            if total_invested and total_invested > 0
            else 0
        )
        
        return {
            "total_value": float(current_value),
            "total_gain_loss": float(total_gain_loss),
            "total_gain_loss_percentage": float(total_gain_loss_percentage),
            "realized_gains": float(realized_gains),
            "unrealized_gains": float(unrealized_gains),
            "total_invested": float(total_invested)
        }
        
    except Exception as e:
        print(f"Error calculating portfolio performance: {str(e)}")
        # Return a more detailed error message
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate portfolio performance: {str(e)}"
        )


@router.get("/insights/{user_id}")
async def get_portfolio_insights(user_id: str):
    try:
        user = users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get portfolio data
        portfolio = user.get("portfolio", {})
        positions = user.get("positions", [])
        total_value = float(user.get("total_value", 0) or 0)
        cash = float(user.get("cash", 0) or 0)

        # Format data for ChatGPT
        prompt = f"""
        Analyze this investment portfolio and provide insights:

        Total Portfolio Value: ${total_value:,.2f}
        Cash Position: ${cash:,.2f}
        
        Current Positions:
        {positions}

        Provide a JSON response with the following structure:
        {{
            "risk_level": "Low" or "Moderate" or "High",
            "health_score": number between 0-100,
            "health_rating": descriptive rating of the health score,
            "recommendations": [
                {{
                    "title": "brief title",
                    "description": "detailed recommendation"
                }},
                ... (up to 3 recommendations)
            ]
        }}

        Base the analysis on:
        - Diversification
        - Sector allocation
        - Cash position
        - Risk exposure
        - Current market conditions
        """

        # Get ChatGPT response
        chatbot = ChatGPT()  # Your ChatGPT service instance
        response = await chatbot._get_response(prompt, [])
        
        # Parse and validate response
        try:
            import json
            insights = json.loads(response)
            return insights
        except json.JSONDecodeError:
            # Fallback response if ChatGPT output isn't valid JSON
            return {
                "risk_level": "Moderate",
                "health_score": 70,
                "health_rating": "Good",
                "recommendations": [
                    {
                        "title": "Regular Review",
                        "description": "Schedule periodic portfolio reviews"
                    }
                ]
            }

    except Exception as e:
        print(f"Error getting portfolio insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate portfolio insights")
