import os, requests, json
from datetime import datetime, timezone, timedelta

BOT = os.environ.get('TG_BOT_TOKEN', '')
UID = os.environ.get('TG_USER_ID', '')
STATE_FILE = '.tw00878_state.json'

def send(msg):
    requests.post('https://api.telegram.org/bot' + BOT + '/sendMessage', json={'chat_id': UID, 'text': msg})

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {'position': 'none', 'size': 0, 'entry': 0, 'date': ''}

def save_state(s):
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f)

def get_price():
    url = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_00878.tw'
    r = requests.get(url, timeout=10)
    d = r.json()['msgArray'][0]
    return {
        'price': float(d['z']) if d['z'] != '-' else None,
        'open': float(d['o']) if d['o'] != '-' else 0,
        'high': float(d['h']) if d['h'] != '-' else 0,
        'low': float(d['l']) if d['l'] != '-' else 0,
        'yesterday': float(d['y']) if d['y'] != '-' else 0,
        'volume': int(d['v']) if d['v'] != '-' else 0,
    }

def get_history():
    try:
        import yfinance as yf
        tk = yf.Ticker('00878.TW')
        df = tk.history(period='3mo', interval='1d')
        if df.empty:
            return None
        df['ema5'] = df['Close'].ewm(span=5).mean()
        df['ema10'] = df['Close'].ewm(span=10).mean()
        df['ema20'] = df['Close'].ewm(span=20).mean()
        df['ema60'] = df['Close'].ewm(span=60).mean()
        df['rsi'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() / df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
        return df
    except:
        return None

try:
    Taipei = timezone(timedelta(hours=8))
    now = datetime.now(Taipei)
    now_str = now.strftime('%Y-%m-%d %H:%M')
    rt = get_price()
    price = rt['price']

    if price is None:
        send('00878 no price now')
    else:
        change = price - rt['yesterday']
        pct = change / rt['yesterday'] * 100 if rt['yesterday'] else 0

        state = load_state()
        df = get_history()
        if df is not None and len(df) >= 20:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            ema5 = round(latest['ema5'], 2)
            ema10 = round(latest['ema10'], 2)
            ema20 = round(latest['ema20'], 2)
            ema60 = round(latest['ema60'], 2)
            rsi = round(latest['rsi'], 1)
            prev_ema5 = round(prev['ema5'], 2)
            prev_ema20 = round(prev['ema20'], 2)
            if ema5 > ema20:
                trend = 'Bullish (Golden Cross)'
            elif ema5 < ema20:
                trend = 'Bearish (Death Cross)'
            else:
                trend = 'Neutral'
        else:
            ema5 = ema10 = ema20 = ema60 = rsi = prev_ema5 = prev_ema20 = 0
            trend = 'N/A'

        signal = 'none'
        reason = ''
        if prev_ema5 <= prev_ema20 and ema5 > ema20:
            signal = 'buy'
            reason = 'EMA5 cross above EMA20'
        elif prev_ema5 >= prev_ema20 and ema5 < ema20:
            signal = 'sell'
            reason = 'EMA5 cross below EMA20'
        elif rsi < 30 and state['position'] == 'none':
            signal = 'buy'
            reason = 'RSI oversold (<30)'
        elif rsi > 75 and state['position'] == 'long':
            signal = 'sell'
            reason = 'RSI overbought (>75)'

        pnl = 0
        pnl_pct = 0
        if state['position'] == 'long' and state['entry'] > 0:
            pnl = round((price - state['entry']) * state['size'], 2)
            pnl_pct = round((price - state['entry']) / state['entry'] * 100, 2)

        psych = []
        if rsi < 30:
            psych.append('Panic zone - good entry point')
        elif rsi > 70:
            psych.append('Greed zone - consider taking profit')
        elif 40 <= rsi <= 60:
            psych.append('Neutral sentiment - normal hold')
        if pct > 2:
            psych.append('Large gain today - watch for pullback')
        elif pct < -2:
            psych.append('Large drop today - do not panic')
        if rt['volume'] > 100000:
            psych.append('High volume - market attention high')
        elif rt['volume'] < 30000:
            psych.append('Low volume - low liquidity')

        report = '=== 00878 Report ===\n'
        report += now_str + ' Taipei Time\n'
        report += '========================\n\n'
        report += '[Price]\n'
        report += 'Current: $' + str(round(price, 2)) + '\n'
        report += 'Change: $' + str(round(change, 2)) + ' (' + str(round(pct, 2)) + '%)\n'
        report += 'Open: $' + str(round(rt['open'], 2)) + '\n'
        report += 'High: $' + str(round(rt['high'], 2)) + '\n'
        report += 'Low: $' + str(round(rt['low'], 2)) + '\n'
        report += 'Volume: ' + str(rt['volume']) + '\n\n'
        report += '[Technical]\n'
        report += 'EMA5: ' + str(ema5) + '\n'
        report += 'EMA10: ' + str(ema10) + '\n'
        report += 'EMA20: ' + str(ema20) + '\n'
        report += 'EMA60: ' + str(ema60) + '\n'
        report += 'RSI: ' + str(rsi) + '\n'
        report += 'Trend: ' + trend + '\n\n'
        report += '[Position]\n'
        if state['position'] == 'long':
            report += 'Holding: ' + str(state['size']) + ' shares\n'
            report += 'Entry: $' + str(state['entry']) + '\n'
            report += 'PnL: ' + str(pnl_pct) + '% ($' + str(pnl) + ')\n'
            days = (now - datetime.strptime(state['date'], '%Y-%m-%d')).days if state['date'] else 0
            report += 'Days held: ' + str(days) + '\n'
        else:
            report += 'Empty - waiting to buy\n'
        report += '\n[Psychology]\n'
        for p in psych:
            report += '- ' + p + '\n'
        report += '\n[Action]\n'
        if signal == 'buy':
            report += '>>> BUY Signal <<<\n'
            report += 'Buy 00878 at $' + str(round(price, 2)) + '\n'
            report += 'Quantity: 12 shares (~$400)\n'
            report += 'App: YuShan > Zero Stock > Buy\n'
        elif signal == 'sell':
            report += '>>> SELL Signal <<<\n'
            report += 'Sell 00878 at $' + str(round(price, 2)) + '\n'
        else:
            report += 'Wait for signal\n'

        send(report)

        if signal == 'buy' and state['position'] == 'none':
            state['position'] = 'long'
            state['size'] = 12
            state['entry'] = price
            state['date'] = now.strftime('%Y-%m-%d')
        elif signal == 'sell' and state['position'] == 'long':
            state['position'] = 'none'
            state['size'] = 0
            state['entry'] = 0
            state['date'] = ''
        save_state(state)

except Exception as e:
    send('Error: ' + str(e))