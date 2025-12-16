# test_agent.py
from agent import app

def test_agent(stock_name):
    initial_state = {
        "stock_name": stock_name,
        "messages": []
    }
    
    result = app.invoke(initial_state)
    print(result.get('financial_analysis', 'No analysis found'))

# test_agent("ANGELONE")

# Test
# if __name__ == "__main__":
#     # test_agent("Reliance Industries")
#     test_agent("TCS.NS")
    # test_agent("Infosys")