import os, json, requests
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
USER_ID = os.environ.get('TG_USER_ID', '')
STATE_FILE = '.tw00878_state.json'

def send(msg):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    requests.post(url, json={'chat_id': USER_ID, 'text': msg})

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'position': 'none', 'last_price': 0, 'last_signal': 'none'}

def save_state(s):
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f)

def get_data():
    tk = yf.Ticker('00878.TW')
    df = tk.history(period='3mo', interval='1d')
    df['ema5'] = df['Close'].ewm(span=5).mean()
    df['ema20'] = df['Close'].ewm(span=20).mean()
    df['rsi'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() / df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
    return df

def strategy(df, state):
    now = datetime.now().strftime('%H:%M')
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = round(latest['Close'], 2)
    ema5 = round(latest['ema5'], 2)
    ema20 = round(latest['ema20'], 2)
    rsi = round(latest['rsi'], 1)
    prev_ema5 = round(prev['ema5'], 2)
    prev_ema20 = round(prev['ema20'], 2)

    signal = 'none'
    reason = ''

    if prev_ema5 <= prev_ema20 and ema5 > ema20:
        signal = 'buy'
        reason = f'EMA5({ema5}) > EMA20({ema20}), 金叉'
    elif prev_ema5 >= prev_ema20 and ema5 < ema20:
        signal = 'sell'
        reason = f'EMA5({ema5}) < EMA20({ema20}), 死叉'
    elif state['position'] == 'long' and rsi > 75:
        signal = 'sell'
        reason = f'RSI({rsi}) > 75, 超買'
    elif state['position'] == 'none' and rsi < 30:
        signal = 'buy'
        reason = f'RSI({rsi}) < 30, 超賣'

    msg = f'00878 盤中監控 [{now}]\n'
    msg += f'股價: ${price}\n'
    msg += f'EMA5: {ema5}  EMA20: {ema20}\n'
    msg += f'RSI: {rsi}\n'
    msg += f'持倉: {state["position"]}\n'
    msg += f'---\n'

    if signal == 'buy' and state['position'] == 'none':
        msg += f'BUY 訊號: {reason}\n'
        msg += f'建議買入: {price}'
        send(msg)
        state['position'] = 'long'
        state['last_price'] = price
        state['last_signal'] = 'buy'
    elif signal == 'sell' and state['position'] == 'long':
        msg += f'SELL 訊號: {reason}\n'
        msg += f'建議賣出: {price}'
        send(msg)
        state['position'] = 'none'
        state['last_price'] = price
        state['last_signal'] = 'sell'

    return state

if __name__ == '__main__':
    state = load_state()
    df = get_data()
    state = strategy(df, state)
    save_state(state)