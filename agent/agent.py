from langgraph.graph import START, StateGraph,END
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import TypedDict, Annotated
import operator
from .tool import web_search, money_control_scrap, get_financial_summary
from langgraph.prebuilt import ToolNode, tools_condition
import os
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    stock_name: str
    stock_symobol: str
    messages: Annotated[list, operator.add]
    web_search_results: str
    money_control_data:str
    financial_analysis: str


google_api_key = os.getenv("GOOGLE_API_KEY")
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, google_api_key=google_api_key)
tools = [web_search, money_control_scrap, get_financial_summary]


workflow = StateGraph(AgentState)

#Prepare a node

#Node1

def identify_stock(state: AgentState):
    """
    convert the stock name to stock symbol
    """
    prompt = f"""Convert the stock name '{state['stock_name']}' to its NSE (National Stock Exchange) stock symbol.
    Return only the stock symbol with .NS suffix (e.g., TCS.NS, RELIANCE.NS).
    If the input is already a symbol, return it as is.

    Stock name: {state['stock_name']}
    Stock symbol:"""

    response = llm.invoke(prompt)
    symbol = response.content.strip()

    return {
        "stock_symobol": symbol
    }

#node2 news serach

def news_search(state: AgentState):
    """
    Search the web for the general news of the stocks related to indian markets
    """
    tools = [web_search(), money_control_scrap, get_financial_summary]
    llm_with_tools = llm.bind_tools(tools)

    prompt = f"Search for news about {state['stock_symobol']} stock in indian markets and get money control data"
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
    result = money_control_tool.invoke(state["stock_symobol"])
    return {
        "money_control_data": result
        }    

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
            # Limit to first 2000 characters to avoid token limits
            search_results.append(msg.content[:2000])

    return {"web_search_results": "\n".join(search_results)}

#node5 financial analysis

def financial_analysis(state: AgentState):
    """
    Get the financial summary of the stock and draft a final report
    """
    # Limit the search results to avoid token limits
    search_data = state.get('web_search_results', '')[:5000]

    prompt = f"""Analyze the following information about {state['stock_symobol']} stock and return your analysis in JSON format.

Search Results: {search_data}

Return your analysis in the following JSON format:
{{
  "summary": "2-3 sentence overview of the stock's current position and recent performance",
  "bullish_factors": [
    "Specific positive factor 1 with data/reasoning",
    "Specific positive factor 2 with data/reasoning",
    "Specific positive factor 3 with data/reasoning"
  ],
  "bearish_factors": [
    "Specific negative factor 1 with data/reasoning",
    "Specific negative factor 2 with data/reasoning",
    "Specific negative factor 3 with data/reasoning"
  ],
  "recommendation": "BUY or HOLD or SELL",
  "confidence_level": "HIGH or MEDIUM or LOW"
}}

Ensure each factor is:
- Specific and data-driven based on the search results
- Concise (1-2 sentences maximum)
- Focused on actionable insights
- Based on recent news, financial metrics, or market trends

Return ONLY the JSON object, no additional text.
"""

    analysis = llm.invoke(prompt)

    # Parse JSON from response
    try:
        import json
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

        # Validate structure
        required_keys = ['summary', 'bullish_factors', 'bearish_factors', 'recommendation']
        if not all(key in structured_analysis for key in required_keys):
            raise ValueError("Missing required keys in analysis")

        return {"financial_analysis": json.dumps(structured_analysis)}

    except Exception as e:
        # Fallback to unstructured analysis
        print(f"Failed to parse structured analysis: {e}")
        fallback_analysis = {
            "summary": analysis.content[:500] if len(analysis.content) > 500 else analysis.content,
            "bullish_factors": ["Analysis available in summary section"],
            "bearish_factors": ["Analysis available in summary section"],
            "recommendation": "HOLD",
            "confidence_level": "LOW"
        }
        return {"financial_analysis": json.dumps(fallback_analysis)}

# Define tools for ToolNode
tools_list = [web_search(), money_control_scrap, get_financial_summary]

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
