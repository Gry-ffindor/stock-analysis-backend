from langgraph.graph import START, StateGraph,END
from langchain_ollama import ChatOllama
from typing import TypedDict, Annotated
import operator
from .tool import web_search, money_control_scrap, get_financial_summary, get_market_indices, get_balance_sheet
from langgraph.prebuilt import ToolNode, tools_condition
import os
from dotenv import load_dotenv
from .technicals import get_technical_indicators
import json


load_dotenv()

class AgentState(TypedDict):
    stock_name: str
    stock_symbol: str
    messages: Annotated[list, operator.add]
    web_search_results: str
    money_control_data:str
    financial_analysis: str


# Initialize LLM based on environment variable
# Set LLM_PROVIDER in .env to either "ollama" or "gemini"
llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()

if llm_provider == "gemini":
    from langchain_google_genai import ChatGoogleGenerativeAI
    google_api_key = os.getenv("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-lite", 
        temperature=0, 
        google_api_key=google_api_key
    )
    print("Using Google Gemini LLM")
else:  # Default to Ollama
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
    llm = ChatOllama(
        model=ollama_model,
        temperature=0,
        base_url="http://localhost:11434"
    )
    print(f"Using Ollama LLM with model: {ollama_model}")

tools = [web_search, money_control_scrap, get_financial_summary,get_market_indices]


workflow = StateGraph(AgentState)

#Prepare a node

#Node1

def identify_stock(state: AgentState):
    """
    convert the stock name to stock symbol
    """
    stock_name = state['stock_name']
    
    # If it already has .NS or .BO suffix, return as is
    if '.NS' in stock_name.upper() or '.BO' in stock_name.upper():
        return {"stock_symbol": stock_name.upper()}
    
    # Create a strict prompt for Ollama
    prompt = f"""You are a stock symbol converter. Convert the Indian stock name to NSE symbol.

Rules:
1. Return ONLY the stock symbol with .NS suffix
2. No explanations, no code, no examples - just the symbol
3. Common symbols: TCS -> TCS.NS, RELIANCE -> RELIANCE.NS, INFY -> INFY.NS

Stock name: {stock_name}
Stock symbol:"""

    response = llm.invoke(prompt)
    symbol = response.content.strip()
    
    # Clean up the response - remove any extra text
    # Take only the first word/line that looks like a symbol
    lines = symbol.split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('def'):
            symbol = line
            break
    
    # Ensure it has .NS suffix if not already present
    if '.NS' not in symbol.upper() and '.BO' not in symbol.upper():
        symbol = symbol.upper() + '.NS'
    
    return {
        "stock_symbol": symbol
    }

#node2 news serach

def news_search(state: AgentState):
    """
    Search the web for the general news of the stocks related to indian markets
    """
    tools = [web_search(), money_control_scrap, get_financial_summary]
    llm_with_tools = llm.bind_tools(tools)

    prompt = f"Search for news about {state['stock_symbol']} stock in indian markets and get money control data"
    result = llm_with_tools.invoke(prompt)

    return {
        "messages": [result]
    }


#node3 money control scrapper

def money_control_scrapper(state: AgentState):
    """
    Scrape the money control website for the stock details
    return the stock details , price, change, market cap, PE ratio, etc.
    """
    money_control_tool = money_control_scrap()
    result = money_control_tool.invoke(state["stock_symbol"])
    return {
        "money_control_data": result
        }    

def analyze_news_sentiments(title: str, content: str):
    """
    Use LLM to analyze the news sentiment of the stock
    """
    llm = ChatOllama(model="llama3.2")

    prompt = f"""You are a financial sentiment analyzer. Analyze the following news article about a stock and determine if it's POSITIVE, NEGATIVE, or NEUTRAL for investors.

Rules:
- POSITIVE: Good news for stock price (earnings beat, new partnerships, growth, upgrades)
- NEGATIVE: Bad news for stock price (losses, scandals, downgrades, regulatory issues)  
- NEUTRAL: Factual news with no clear impact

Return ONLY ONE WORD: positive, negative, or neutral

Title: {title}
Content: {content[:300]}

Sentiment:"""
    
    try:
        response = llm.invoke(prompt)
        sentiment = response.content.strip().lower()  # Convert to lowercase
        
        # Debug logging
        print(f"📰 Analyzing: {title[:50]}...")
        print(f"🎯 LLM Response: '{sentiment}'")
        
        # Check if response contains the sentiment word
        if "positive" in sentiment:
            return "positive"
        elif "negative" in sentiment:
            return "negative"
        elif "neutral" in sentiment:
            return "neutral"
        else:
            print(f"⚠️ Unexpected sentiment response: '{sentiment}', defaulting to neutral")
            return "neutral"
    except Exception as e:
        print(f"❌ Sentiment analysis error: {str(e)}")
        return "neutral"

#node4 process tool results
def process_tools(state: AgentState):
    """
    Process the tool results and extract data
    """
    messages = state.get("messages", [])
    search_results = []

    # Extract tool results from messages
    for msg in messages:
        if hasattr(msg, 'content') and isinstance(msg.content, str) and msg.content:
            # Don't truncate here - keep full message to preserve JSON structure
            search_results.append(msg.content)

    # Join all results
    web_search_results = "\n".join(search_results)
    
    # If the result is too long, try to parse as JSON and truncate individual articles
    if len(web_search_results) > 5000:
        try:
            import json
            # Try to parse as JSON array
            json_match = web_search_results.find('[')
            if json_match != -1:
                json_str = web_search_results[json_match:]
                news_array = json.loads(json_str.split('\n')[0])  # Get first line with JSON
                # Structure news with sentiment analysis
                structured_news = []
                for item in news_array:
                    structured_news.append({
                        "title": item.get('title', 'News Update'),
                        "summary": item.get('content', '')[:200],  # Limit to 200 chars
                        "source": item.get('url', '').split('/')[2] if item.get('url') else 'Unknown',
                        "publishedAt": "Today",  # Or parse from item if available
                        "sentiment": analyze_news_sentiments(item.get('title', ''), item.get('content', '')),
                        "url": item.get('url', '#')
                    })
        
                return {
                    "web_search_results": json.dumps(structured_news)
                }
        except:
            # If parsing fails, just truncate the whole thing
            web_search_results = web_search_results[:5000]
    
    print(f"📰 Collected web_search_results: {len(web_search_results)} characters")
    print(f"📰 First 200 chars: {web_search_results[:200]}")
    
    return {"web_search_results": web_search_results}



#node5 financial analysis

def financial_analysis(state: AgentState):
    """
    Genrate trade setup and Analysis for the stock
    """
    stock_symbol = state['stock_symbol']
    tech_data = get_technical_indicators(stock_symbol)
    tech_context ={
        f"""
            Current Price: {tech_data.get('current_price')}
            Over all Signal : {tech_data.get('overall_signal')}
            Volatility (ATR) : {tech_data.get('volatility')}
            Support Levels : {tech_data.get('support_levels')}
            Resistance Levels : {tech_data.get('resistance_levels')}    
            Key Signals: {json.dumps(tech_data.get('key_signals'))}
        """
    }
    # Limit the search results to avoid token limits
    search_data = state.get('web_search_results', '')[:5000]

    prompt = f"""You are professinal Trading AI. Analyse the news related to {state['stock_symbol']} based on the Technical data and news below.

    Techincal Data: {tech_context}

    Recent News: {search_data}
    Task: Create a precise Trade setup


    Rules:
    1. If Volatility (ATR) is high, suggest wider Stop Loss.
    2. Entry price MUST be near a Support level (for Buy).
    3. Stop Loss MUST be below Support (Buy) or above Resistance (Sell).
    4. Targets should be at Resistance levels.
    
    Return pure JSON format:
        {{
        "summary": "Detailed strategic analysis (30-40 sentences) covering market context, key drivers, and forward-looking outlook.",
        "bullish_factors": [{{ "factor": "Detailed explanation of point 1", "confidence": 95 }}, {{ "factor": "Point 2", "confidence": 85 }}],  # Request exactly 10 points
        "bearish_factors": [{{ "factor": "Detailed explanation of point 1", "confidence": 90 }}, {{ "factor": "Point 2", "confidence": 80 }}],  # Request exactly 10 points
        "recommendation": "BUY" | "SELL" | "HOLD",
        "trade_setup": {{
            "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
            "entry_zone": "e.g. 1500 - 1520",
            "target_1": "e.g. 1580",
            "target_2": "e.g. 1650",
            "stop_loss": "e.g. 1480",
            "timeframe": "Swing (1-3 weeks)" | "Intraday" | "Investment",
            "reasoning": "Price is bouncing off 1500 support with RSI crossed up. Stop loss set 1x ATR below support.",
            "target_logic": "Concise explanation of why targets were chosen (e.g. 'Target 1 aligns with 200 EMA resistance')"
        }},
        "risk_analysis": {{
            "risk_percentage": "e.g., 2.5%",
            "risk_reward_t1": "e.g., 1:2",
            "risk_reward_t2": "e.g., 1:3",
            "volatility_assessment": "e.g., High Volatility - Wide stops recommended due to high ATR rank",
            "key_risks": ["Detailed 2-3 sentence explanation of risk 1 (e.g., why sector headwinds specifically affect this stock)", "Detailed 2-3 sentence explanation of risk 2"],
            "risk_mitigation": ["Specific Stop Loss advice with reasoning (e.g., 'Strict SL at 1480 because...')", "Detailed 2-3 sentence hedging or position sizing strategy"]
        }}
    }}
"""

    analysis = llm.invoke(prompt)

        # Parse JSON from response
    try:
        import re

        # Extract JSON from markdown code blocks if present
        content = analysis.content
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            json_str = json_match.group(0) if json_match else content

        structured_analysis = json.loads(json_str)

        # Validate structure - check for the fields we actually requested in the prompt
        required_keys = ['summary', 'recommendation', 'trade_setup', 'bullish_factors', 'bearish_factors']
        if not all(key in structured_analysis for key in required_keys):
            raise ValueError(f"Missing required keys in analysis. Got: {list(structured_analysis.keys())}")

        return {"financial_analysis": json.dumps(structured_analysis)}

    except Exception as e:
        # Fallback to unstructured analysis
        print(f"Failed to parse structured analysis: {e}")
        
        # Try to extract trade_setup from the raw content if it exists
        trade_setup_data = None
        try:
            content = analysis.content
            # Try to find trade_setup object in the response
            import re
            trade_match = re.search(r'"trade_setup"\s*:\s*\{[^}]+\}', content, re.DOTALL)
            if trade_match:
                trade_setup_data = json.loads('{' + trade_match.group(0) + '}').get('trade_setup')
        except:
            pass
        
        fallback_analysis = {
            "summary": analysis.content[:50000] if len(analysis.content) > 50000 else analysis.content,
            "bullish_factors": [{"factor": "Analysis available in summary section", "confidence": 0}],
            "bearish_factors": [{"factor": "Analysis available in summary section", "confidence": 0}],
            "recommendation": "HOLD",
            "confidence_level": "LOW"
        }
        
        # Preserve trade_setup if we found it
        if trade_setup_data:
            fallback_analysis["trade_setup"] = trade_setup_data
            
        return {"financial_analysis": json.dumps(fallback_analysis)}


    

# Define tools for ToolNode
tools_list = [web_search(), money_control_scrap, get_financial_summary, get_balance_sheet]

workflow.add_node("identify_stock", identify_stock)
workflow.add_node("news_search", news_search)
workflow.add_node("tools", ToolNode(tools_list))
workflow.add_node("process_tools", process_tools)
workflow.add_node("financial_analysis", financial_analysis)

workflow.add_edge(START, "identify_stock")
workflow.add_edge("identify_stock", "news_search")
workflow.add_conditional_edges("news_search", tools_condition)
workflow.add_edge("tools", "process_tools")
workflow.add_edge("process_tools", "financial_analysis")
workflow.add_edge("financial_analysis", END)

app = workflow.compile()
