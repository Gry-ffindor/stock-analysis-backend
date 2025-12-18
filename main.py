from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import traceback

from agent.agent import app as agent_app
from agent.tool import get_financial_summary, get_historical_data, get_quarterly_financials, get_company_financials, get_balance_sheet
from agent.technicals import get_technical_indicators


app = FastAPI(title="Stock Analysis API")

# Enable CORS for frontend
# Get allowed origins from environment variable or use defaults
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")

# Handle wildcard for all origins or specific origins
if allowed_origins_str.strip() == "*":
    allowed_origins = ["*"]
    allow_credentials = False  # Cannot use credentials with wildcard origin
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",")]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockRequest(BaseModel):
    stock_name: str

class StockResponse(BaseModel):
    stock_name: str
    stock_symbol: str
    analysis: str
    structured_analysis: Optional[dict] = None
    data: dict
    historical_data: list = []
    financials: dict = {}
    quarterly_financials: list = []
    technical_indicators: dict = {}

router = APIRouter()

@router.post("/analyze", response_model=StockResponse)
async def analyze_stock(request: StockRequest):
    """Analyze a stock using AI agent"""
    try:
        initial_state = {
            "stock_name": request.stock_name,
            "messages": []
        }

        result = agent_app.invoke(initial_state)

        # Get the stock symbol from agent result
        stock_symbol = result.get('stock_symbol', request.stock_name)

        # Get financial data using yfinance
        try:
            financial_data = get_financial_summary(stock_symbol)
            
            # Fetch balance sheet data
            try:
                balance_sheet_data = get_balance_sheet(stock_symbol)
            except Exception as e:
                print(f"Error fetching balance sheet: {str(e)}")
                balance_sheet_data = {}
            
            market_data = {
                "current_price": financial_data.get('price') or 'N/A',
                "market_cap": financial_data.get('market_cap') or 'N/A',
                "pe_ratio": financial_data.get('PE_ratio') or 'N/A',
                "52_week_high": financial_data.get('52_week_high') or 'N/A',
                "52_week_low": financial_data.get('52_week_low') or 'N/A',
                "dividend_yield": financial_data.get('dividend_yield') or 'N/A',
                "web_search_results": result.get('web_search_results', ''),
                "volume": financial_data.get('volume') or 'N/A',
                "avg_volume": financial_data.get('avg_volume') or 'N/A',
                "enterprise_value": financial_data.get('enterprise_value') or 'N/A',
                "price_to_book": financial_data.get('price_to_book') or 'N/A',
                # New fields for 4-column layout
                "beta": financial_data.get('beta') or 'N/A',
                "short_interest": financial_data.get('short_interest') or 'N/A',
                "peg_ratio": financial_data.get('peg_ratio') or 'N/A',
                "ev_to_ebitda": financial_data.get('ev_to_ebitda') or 'N/A',
                "gross_margins": financial_data.get('gross_margins') or 'N/A',
                "operating_margins": financial_data.get('operating_margins') or 'N/A',
                "roa": financial_data.get('roa') or 'N/A',
                "roe": financial_data.get('roe') or 'N/A',
                "debt_to_equity": financial_data.get('debt_to_equity') or 'N/A',
                "current_ratio": financial_data.get('current_ratio') or 'N/A',
                "quick_ratio": financial_data.get('quick_ratio') or 'N/A',
                "institutional_holdings": financial_data.get('institutional_holdings') or 'N/A',
                "insider_holdings": financial_data.get('insider_holdings') or 'N/A',
                "sector": financial_data.get('sector') or 'N/A',
                "industry": financial_data.get('industry') or 'N/A',
                "earnings_date": financial_data.get('earnings_date') or 'N/A',
                "balance_sheet": balance_sheet_data,
            }
            print(f"📤 Sending web_search_results to frontend: {len(market_data['web_search_results'])} characters")

        except Exception as e:
            print(f"Error fetching financial data: {str(e)}")
            traceback.print_exc()
            market_data = {
                "current_price": 'N/A',
                "market_cap": 'N/A',
                "pe_ratio": 'N/A',
                "52_week_high": 'N/A',
                "52_week_low": 'N/A',
                "dividend_yield": 'N/A',
                "web_search_results": result.get('web_search_results', ''),
            }

        # Fetch historical data for candlestick chart (1 year for all filter options)
        try:
            historical_data = get_historical_data(stock_symbol, period="1y")
        except Exception as e:
            print(f"Error fetching historical data: {str(e)}")
            historical_data = []

        # Fetch company financials
        try:
            financials = get_company_financials(stock_symbol)
        except Exception as e:
            print(f"Error fetching financials: {str(e)}")
            financials = {}

        # Fetch quarterly financials for performance chart
        try:
            quarterly_financials = get_quarterly_financials(stock_symbol)
        except Exception as e:
            print(f"Error fetching quarterly financials: {str(e)}")
            quarterly_financials = []

        # Fetch technical indicators
        try:
            technical_indicators = get_technical_indicators(stock_symbol)
        except Exception as e:
            print(f"Error fetching technical indicators: {str(e)}")
            technical_indicators = {}

        # Parse structured analysis from JSON string
        structured_analysis = None
        analysis_text = 'No analysis available'
        try:
            import json
            financial_analysis_str = result.get('financial_analysis', '{}')
            structured_analysis = json.loads(financial_analysis_str)
            # Use summary as the main analysis text
            analysis_text = structured_analysis.get('summary', financial_analysis_str)
        except Exception as e:
            print(f"Error parsing structured analysis: {str(e)}")
            analysis_text = result.get('financial_analysis', 'No analysis available')
            structured_analysis = None

        return StockResponse(
            stock_name=result.get('stock_name', request.stock_name),
            stock_symbol=stock_symbol,
            analysis=analysis_text,
            structured_analysis=structured_analysis,
            data=market_data,
            historical_data=historical_data,
            financials=financials,
            quarterly_financials=quarterly_financials,
            technical_indicators=technical_indicators
        )
    except Exception as e:
        print(f"Error analyzing stock: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/market-indices")
async def get_indices():
    """Get current Indian market indices (NIFTY, SENSEX, BANK NIFTY, etc.)"""
    try:
        from agent.tool import get_market_indices
        indices_data = get_market_indices()
        return {"indices": indices_data}
    except Exception as e:
        print(f"Error fetching market indices: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"message": "Stock Analysis API is running", "docs": "/docs"}

# Include router for both root and /api prefix to handle Vercel routing
app.include_router(router)
app.include_router(router, prefix="/api")