# test_agent.py
from agent import app

def test_agent(stock_name):
    """Test stock analysis using the agent"""
    initial_state = {
        "stock_name": stock_name,
        "messages": []
    }
    
    result = app.invoke(initial_state)
    print("\n" + "="*70)
    print("STOCK ANALYSIS RESULT")
    print("="*70)
    print(result.get('financial_analysis', 'No analysis found'))
    print("="*70 + "\n")


def test_market_indices_with_agent():
    """
    Test market indices using the agent workflow
    The agent will automatically decide to call get_market_indices tool
    """
    # This is similar to test_agent but for market indices
    # We provide a "stock_name" that hints the agent to fetch market data
    initial_state = {
        "stock_name": "NIFTY",  # This tells the agent we want market indices
        "messages": []
    }
    
    print("\n" + "="*70)
    print("FETCHING MARKET INDICES VIA AGENT")
    print("="*70 + "\n")
    
    # Invoke the agent - it will automatically call get_market_indices
    result = app.invoke(initial_state)
    
    # Print the full result to see what the agent returns
    print("Agent Result:")
    for key, value in result.items():
        print(f"\n{key}:")
        print(f"  {value}")
    
    print("\n" + "="*70 + "\n")


# ===== CHOOSE WHICH TEST TO RUN =====

# Option 1: Test stock analysis
# test_agent("TCS")

# Option 2: Test market indices through agent
test_market_indices_with_agent()

# Option 3: Test both
# test_agent("RELIANCE")
# test_market_indices_with_agent()