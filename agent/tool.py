from langchain_community.tools.tavily_search import TavilySearchResults
import yfinance as yf
import pandas as pd
import os 
from dotenv import load_dotenv

load_dotenv()

#websearch tool

def web_search():
    """
    Search the web for the general news of the stocks related to indian markets
    """
    return TavilySearchResults(max_results=5, api_key=os.getenv("TAVILY_API_KEY"))

#money control scrapper

import requests
from bs4 import BeautifulSoup

def money_control_scrap(stock_name:str):
    """
    Scrape the money control website for the stock details
    return the stock details , price, change, market cap, PE ratio, etc.
    """
    money_control_url = f"https://www.moneycontrol.com/india/stockpricequote/{stock_name}"
    response = requests.get(money_control_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    return soup

#Financial tool

def get_financial_summary(stock_name:str):
    """
    Get the financial summary of the stock
    """
    stock = yf.Ticker(stock_name)
    info = stock.info

    # Get current price with fallback options
    current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')

    # Get market cap with formatting
    market_cap = info.get('marketCap')
    if market_cap:
        # Format market cap in crores for Indian stocks
        market_cap = f"{market_cap / 10000000:.2f} Cr"

    # Get PE ratio
    pe_ratio = info.get('trailingPE') or info.get('forwardPE')
    if pe_ratio:
        pe_ratio = f"{pe_ratio:.2f}"

    # Get dividend yield
    dividend_yield = info.get('dividendYield')
    if dividend_yield:
        dividend_yield = f"{dividend_yield * 100:.2f}%"

    return {
        "stock_name": stock_name,
        "price": current_price,
        "market_cap": market_cap,
        "PE_ratio": pe_ratio,
        "dividend_yield": dividend_yield,
        "52_week_high": info.get('fiftyTwoWeekHigh'),
        "52_week_low": info.get('fiftyTwoWeekLow'),
    }

def get_historical_data(stock_name: str, period: str = "3mo"):
    """
    Get historical OHLC data for candlestick chart

    Args:
        stock_name: Stock symbol (e.g., "TCS.NS")
        period: Time period ("1mo", "3mo", "6mo", "1y")

    Returns:
        List of dicts with date, open, high, low, close, volume
    """
    stock = yf.Ticker(stock_name)

    # Fetch historical data with daily interval
    hist = stock.history(period=period, interval="1d")

    # Convert DataFrame to list of dictionaries
    candlestick_data = []
    for date, row in hist.iterrows():
        candlestick_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(row['Open'], 2),
            "high": round(row['High'], 2),
            "low": round(row['Low'], 2),
            "close": round(row['Close'], 2),
            "volume": int(row['Volume'])
        })

    return candlestick_data

def get_company_financials(stock_name: str):
    """
    Get comprehensive financial data including balance sheet, income statement, and cash flow.
    """
    stock = yf.Ticker(stock_name)
    
    def process_dataframe(df):
        if df is None or df.empty:
            return {}
        
        # Replace NaN with None for JSON compatibility
        df = df.astype(object).where(pd.notnull(df), None)
        
        # Convert to dict with string dates as keys
        return {k.strftime('%Y-%m-%d') if hasattr(k, 'strftime') else str(k): v for k, v in df.to_dict().items()}

    return {
        "income_statement": process_dataframe(stock.financials),
        "balance_sheet": process_dataframe(stock.balance_sheet),
        "cash_flow": process_dataframe(stock.cashflow)
    }