from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from backend_files.services.chatbot import ChatGPT
from backend_files.schemas import ChatRequest, PortfolioAnalysisRequest, MarketAnalysisRequest, StockAnalysisRequest
from pydantic import BaseModel
import logging as logger

router = APIRouter()
chatgpt = ChatGPT()


@router.post("/chat")
async def chatgpt_post(chat_data: ChatRequest):
    try:
        logger.info(f"Received chat request with message length: {len(chat_data.message)}")
        
        if not chat_data.message:
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
            
        logger.info("Calling ChatGPT service...")
        response = await chatgpt._get_response(
            user_message=chat_data.message,
            chat_history=chat_data.chat_history
        )
        
        if not response:
            logger.error("Empty response from ChatGPT service")
            raise HTTPException(
                status_code=500,
                detail="No response generated"
            )
            
        logger.info(f"Successfully generated response of length: {len(response)}")
        return {"response": response}
        
    except HTTPException as he:
        logger.error(f"HTTP Exception in chat endpoint: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat service error: {str(e)}"
        )

@router.post("/analyze/stock")
async def analyze_stock(data: StockAnalysisRequest):
    try:
        prompt = f"""
        Provide a comprehensive analysis of {data.symbol} stock with the following data:
        Current Price: ${data.price}
        Daily Change: ${data.change} ({data.percentChange}%)
        
        Please include:
        1. Technical Analysis: Current price action and trend analysis
        2. Key Levels: Support and resistance levels
        3. Market Sentiment: Based on price action and volatility
        4. Trading Opportunities: Potential entry and exit points
        5. Risk Assessment: Key risk factors to consider
        
        Additional metrics: {data.metrics if data.metrics else 'Not provided'}
        Timeframe: {data.timeframe}
        """
        
        response = await chatgpt._get_response(user_message=prompt, chat_history=[])
        return {"analysis": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/market")
async def analyze_market(data: MarketAnalysisRequest):
    try:
        prompt = f"""
        Provide a comprehensive market analysis based on the following data:
        
        Market Indices:
        {'\n'.join([f'{k}: {v}' for k, v in data.indices.items()])}
        
        Current Market Trends:
        {'\n'.join(data.trends)}
        
        Please include:
        1. Overall Market Sentiment
        2. Sector Analysis
        3. Risk Factors
        4. Market Opportunities
        5. {data.timeframe} Outlook
        """
        
        response = await chatgpt._get_response(user_message=prompt, chat_history=[])
        return {"analysis": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/portfolio")
async def analyze_portfolio(data: PortfolioAnalysisRequest):
    try:
        prompt = f"""
        Provide a comprehensive portfolio analysis based on the following data:
        
        Portfolio Holdings:
        {'\n'.join([f'{h["symbol"]}: ${h["value"]}' for h in data.holdings])}
        
        Total Portfolio Value: ${data.total_value}
        Cash Position: ${data.cash_position}
        Risk Profile: {data.risk_profile}
        
        Please include:
        1. Portfolio Composition Analysis
        2. Diversification Assessment
        3. Risk Analysis
        4. Rebalancing Recommendations
        5. Optimization Suggestions
        """
        
        response = await chatgpt._get_response(user_message=prompt, chat_history=[])
        return {"analysis": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/options")
async def analyze_options(symbol: str, current_price: float, calls: List[Dict], puts: List[Dict]):
    try:
        prompt = f"""
        Provide an options analysis for {symbol} based on the following data:
        
        Current Stock Price: ${current_price}
        
        Call Options:
        {'\n'.join([f'Strike: ${c["strike"]}, Premium: ${c["premium"]}, Exp: {c["expiration"]}' for c in calls])}
        
        Put Options:
        {'\n'.join([f'Strike: ${p["strike"]}, Premium: ${p["premium"]}, Exp: {p["expiration"]}' for p in puts])}
        
        Please include:
        1. Options Strategy Recommendations
        2. Key Strike Levels Analysis
        3. Implied Volatility Assessment
        4. Risk/Reward Scenarios
        5. Hedge Opportunities
        """
        
        response = await chatgpt._get_response(user_message=prompt, chat_history=[])
        return {"analysis": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trading/suggestion")
async def get_trading_suggestion(
    symbol: str,
    current_price: float,
    indicators: Dict[str, float],
    timeframe: str = "short-term"
):
    try:
        prompt = f"""
        Provide a trading suggestion for {symbol} based on the following data:
        
        Current Price: ${current_price}
        Timeframe: {timeframe}
        
        Technical Indicators:
        {'\n'.join([f'{k}: {v}' for k, v in indicators.items()])}
        
        Please include:
        1. Trading Recommendation (Buy/Sell/Hold)
        2. Entry Points
        3. Stop Loss Levels
        4. Take Profit Targets
        5. Risk Management Suggestions
        """
        
        response = await chatgpt._get_response(user_message=prompt, chat_history=[])
        return {"suggestion": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
