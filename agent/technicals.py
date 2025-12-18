"""
Technical Analysis Indicators Module
Calculates all technical indicators matching frontend requirements
"""
import yfinance as yf
import pandas_ta as ta
import numpy as np

def calculate_atr(high,low,close, period =14):
    """
    Calculate the Average true Range (ATR) for volatiltiy
    """
    try:
        atr_df = ta.atr(high, low, close, length=period)
        return float(atr_df.iloc[-1]) if not atr_df.empty else 0
    except Exception as e:
        print(f"Error in calculate_atr: {str(e)}")
        return 0

def get_volatility_analysis(high , low, close, current_price):
    """
    Claculate the volatility metrics including the ATR rank and historical volatility
    """
    atr_value = calculate_atr(high, low, close)
    atr_percentage = (atr_value / current_price) * 100
    returns = close.pct_change().dropna()
    historical_volatility = returns.std() * np.sqrt(252 ** .5) * 100
    return {
        'atr': round(atr_value, 2),
        'atr_percentage': round(atr_percentage, 2),
        "volatility_rank": "High" if atr_percentage > 2.5 else "Low" if atr_percentage < 1.5 else "Medium",
        'historical_volatility': round(historical_volatility, 2)
    }   



def calculate_support_resistance(high, low, close, periods=14):
    """Calculate support and resistance levels using pivot points"""
    try:
        # Recent highs and lows
        recent_high = high.tail(periods).max()
        recent_low = low.tail(periods).min()
        current = close.iloc[-1]
        
        # Pivot point
        pivot = (recent_high + recent_low + current) / 3
        
        # Calculate resistance and support levels
        resistance1 = (2 * pivot) - recent_low
        resistance2 = pivot + (recent_high - recent_low)
        resistance3 = recent_high + 2 * (pivot - recent_low)
        
        support1 = (2 * pivot) - recent_high
        support2 = pivot - (recent_high - recent_low)
        support3 = recent_low - 2 * (recent_high - pivot)
        
        return {
            'support': [support1, support2, support3],
            'resistance': [resistance1, resistance2, resistance3]
        }
    except:
        return {'support': [0, 0, 0], 'resistance': [0, 0, 0]}


def map_to_rating(buy_count, sell_count, neutral_count):
    """Map signal counts to Strong Buy/Buy/Neutral/Sell/Strong Sell"""
    total = buy_count + sell_count + neutral_count
    if total == 0:
        return 'Neutral'
    
    buy_ratio = buy_count / total
    
    if buy_ratio >= 0.75:
        return 'Strong Buy'
    elif buy_ratio >= 0.55:
        return 'Buy'
    elif buy_ratio <= 0.25:
        return 'Strong Sell'
    elif buy_ratio <= 0.45:
        return 'Sell'
    else:
        return 'Neutral'


def price_vs_ma_signal(price, ma_value):
    """Determine BUY/SELL/NEUTRAL based on price vs MA"""
    return 'BUY' if price > ma_value else 'SELL'


def get_technical_indicators(stock_name: str):
    """
    Calculate comprehensive technical indicators
    Returns structure matching frontend TechnicalIndicators interface
    """
    try:
        stock = yf.Ticker(stock_name)
        hist = stock.history(period='6mo', interval='1d')
        
        if hist.empty or len(hist) < 50:
            print(f"⚠️  Insufficient data for {stock_name}")
            return {}
        
        close = hist['Close']
        high = hist['High']
        low = hist['Low']
        current_price = close.iloc[-1]
        
        print(f"📊 Calculating comprehensive technical analysis for {stock_name}...")
        
        # ============================================
        # OSCILLATORS
        # ============================================
        
        # RSI (14)
        rsi_values = ta.rsi(close, length=14)
        rsi = float(rsi_values.iloc[-1]) if not rsi_values.empty else 50
        rsi_signal = 'BUY' if rsi < 30 else 'SELL' if rsi > 70 else 'NEUTRAL'
        
        # Stochastic (14, 3, 3)
        stoch_result = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
        stoch_k = float(stoch_result['STOCHk_14_3_3'].iloc[-1]) if not stoch_result.empty else 50
        stoch_signal = 'BUY' if stoch_k < 20 else 'SELL' if stoch_k > 80 else 'NEUTRAL'
        
        # CCI (20)
        cci_values = ta.cci(high, low, close, length=20)
        cci = float(cci_values.iloc[-1]) if not cci_values.empty else 0
        cci_signal = 'BUY' if cci < -100 else 'SELL' if cci > 100 else 'NEUTRAL'
        
        # ADX (14)
        adx_result = ta.adx(high, low, close, length=14)
        adx = float(adx_result['ADX_14'].iloc[-1]) if not adx_result.empty else 25
        # ADX doesn't give BUY/SELL, just trend strength
        adx_signal = 'BUY' if adx > 25 else 'NEUTRAL'
        
        # Momentum (10)
        momentum_values = ta.mom(close, length=10)
        momentum = float(momentum_values.iloc[-1]) if not momentum_values.empty else 0
        momentum_signal = 'BUY' if momentum > 0 else 'SELL' if momentum < 0 else 'NEUTRAL'
        
        # MACD (12, 26, 9)
        macd_result = ta.macd(close, fast=12, slow=26, signal=9)
        if not macd_result.empty:
            macd_value = float(macd_result['MACD_12_26_9'].iloc[-1])
            macd_signal_value = float(macd_result['MACDs_12_26_9'].iloc[-1])
            macd_signal = 'BUY' if macd_value > macd_signal_value else 'SELL'
        else:
            macd_value = 0
            macd_signal = 'NEUTRAL'
        
        # Count oscillator signals
        osc_signals = [rsi_signal, stoch_signal, cci_signal, adx_signal, momentum_signal, macd_signal]
        osc_buy = osc_signals.count('BUY')
        osc_sell = osc_signals.count('SELL')
        osc_neutral = osc_signals.count('NEUTRAL')
        osc_rating = map_to_rating(osc_buy, osc_sell, osc_neutral)
        
        # ============================================
        # MOVING AVERAGES
        # ============================================
        
        def calc_ma_pair(period):
            """Calculate SMA and EMA for a period"""
            sma = float(ta.sma(close, length=period).iloc[-1]) if len(close) >= period else current_price
            ema = float(ta.ema(close, length=period).iloc[-1]) if len(close) >= period else current_price
            return {
                'simple': {'value': sma, 'action': price_vs_ma_signal(current_price, sma)},
                'exponential': {'value': ema, 'action': price_vs_ma_signal(current_price, ema)}
            }
        
        ma10 = calc_ma_pair(10)
        ma20 = calc_ma_pair(20)
        ma50 = calc_ma_pair(50)
        ma100 = calc_ma_pair(100)
        ma200 = calc_ma_pair(200)
        
        # Count MA signals
        ma_signals = [
            ma10['simple']['action'], ma10['exponential']['action'],
            ma20['simple']['action'], ma20['exponential']['action'],
            ma50['simple']['action'], ma50['exponential']['action'],
            ma100['simple']['action'], ma100['exponential']['action'],
            ma200['simple']['action'], ma200['exponential']['action']
        ]
        ma_buy = ma_signals.count('BUY')
        ma_sell = ma_signals.count('SELL')
        ma_neutral = ma_signals.count('NEUTRAL')
        ma_rating = map_to_rating(ma_buy, ma_sell, ma_neutral)
        
        # ============================================
        # OVERALL SUMMARY
        # ============================================
        
        all_signals = osc_signals + ma_signals
        total_buy = all_signals.count('BUY')
        total_sell = all_signals.count('SELL')
        total_neutral = all_signals.count('NEUTRAL')
        overall_rating = map_to_rating(total_buy, total_sell, total_neutral)
        
        # ============================================
        # SUPPORT & RESISTANCE
        # ============================================
        
        levels = calculate_support_resistance(high, low, close)
        
        print(f"✅ Technical Analysis: {overall_rating} ({total_buy} BUY, {total_sell} SELL)")

        # ============================================
        # Volatility
        # ============================================
        atr_value = calculate_atr(high, low, close, period=14)
        volatility_score = "High" if(atr_value > current_price * .02) else "Low"   
        volatility_analysis = get_volatility_analysis(high, low, close, current_price)
        

        return {
            'overall_signal': overall_rating,
            'signal_strength': f"{total_buy}/{len(all_signals)} indicators bullish",
            'summary': {
                'buy': total_buy,
                'sell': total_sell,
                'neutral': total_neutral
            },
            'oscillators': {
                'rating': osc_rating,
                'buy': osc_buy,
                'sell': osc_sell,
                'neutral': osc_neutral,
                'rsi': {'value': round(rsi, 2), 'action': rsi_signal},
                'stoch': {'value': round(stoch_k, 2), 'action': stoch_signal},
                'cci': {'value': round(cci, 2), 'action': cci_signal},
                'macd': {'value': round(macd_value, 4), 'action': macd_signal},
                'adx': {'value': round(adx, 2), 'action': adx_signal},
                'momentum': {'value': round(momentum, 2), 'action': momentum_signal}
            },
            'moving_averages': {
                'rating': ma_rating,
                'buy': ma_buy,
                'sell': ma_sell,
                'neutral': ma_neutral,
                'ma10': ma10,
                'ma20': ma20,
                'ma50': ma50,
                'ma100': ma100,
                'ma200': ma200
            },
            'current_price': round(current_price, 2),
            'volatility': {
                'atr': round(atr_value, 2),
                'volatility_score': volatility_score
            }, 
            'support_levels': [round(float(x), 2) for x in levels['support']],
            'resistance_levels': [round(float(x), 2) for x in levels['resistance']],
            'signals':{
                'rsi': rsi,
                'macd': macd_signal,
                'ema_20': ma20['exponential']['action'],
                'ema_50': ma50['exponential']['action'],
                'ema_100': ma100['exponential']['action'],
                
            }

        }
        
    except Exception as e:
        print(f"❌ Error in technical analysis for {stock_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}