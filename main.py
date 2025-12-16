from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import traceback

from agent.agent import app as agent_app
from agent.tool import get_financial_summary, get_historical_data, get_company_financials


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
    structured_analysis: dict | None = None
    data: dict
    historical_data: list = []
    financials: dict = {}

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
            market_data = {
                "current_price": financial_data.get('price') or 'N/A',
                "market_cap": financial_data.get('market_cap') or 'N/A',
                "pe_ratio": financial_data.get('PE_ratio') or 'N/A',
                "52_week_high": financial_data.get('52_week_high') or 'N/A',
                "52_week_low": financial_data.get('52_week_low') or 'N/A',
                "dividend_yield": financial_data.get('dividend_yield') or 'N/A',
            }
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
            financials=financials
        )
    except Exception as e:
        print(f"Error analyzing stock: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint to verify API is running"""
    return {"message": "Stock Analysis API is running", "docs": "/docs"}

# Include router for both root and /api prefix to handle Vercel routing
app.include_router(router)
app.include_router(router, prefix="/api")