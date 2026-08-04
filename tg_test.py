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
                trend = '\u91d1\u53c9(\u591a\u982d)'
            elif ema5 < ema20:
                trend = '\u6b7b\u53c9(\u7a7a\u982d)'
            else:
                trend = '\u7e5d\u7d50'
        else:
            ema5 = ema10 = ema20 = ema60 = rsi = prev_ema5 = prev_ema20 = 0
            trend = '\u7121\u6cd5\u8a08\u7b97'

        signal = 'none'
        reason = ''
        if prev_ema5 <= prev_ema20 and ema5 > ema20:
            signal = 'buy'
            reason = 'EMA5\u7a7f\u904eEMA20\u91d1\u53c9'
        elif prev_ema5 >= prev_ema20 and ema5 < ema20:
            signal = 'sell'
            reason = 'EMA5\u8dcc\u7834EMA20\u6b7b\u53c9'
        elif rsi < 30 and state['position'] == 'none':
            signal = 'buy'
            reason = 'RSI\u8d85\u8ce4\u5340'
        elif rsi > 75 and state['position'] == 'long':
            signal = 'sell'
            reason = 'RSI\u8d85\u8cb8\u5340'

        pnl = 0
        pnl_pct = 0
        if state['position'] == 'long' and state['entry'] > 0:
            pnl = round((price - state['entry']) * state['size'], 2)
            pnl_pct = round((price - state['entry']) / state['entry'] * 100, 2)

        psych = []
        if rsi < 30:
            psych.append('\u6050\u614c\u5340-\u9滴92f\u5206\u6279\u9032\u5834')
        elif rsi > 70:
            psych.append('\u8ca8\u8ccc\u5340-\u8003\u616e\u6e1b\u5009')
        elif 40 <= rsi <= 60:
            psych.append('\u5e02\u5834\u4e2d\u6027-\u6b63\u5e38\u6301\u6709')
        if pct > 2:
            psych.append('\u4eca\u65e5\u6f32\u5e45\u8f03\u5927-\u6ce8\u610f\u8ffd\u9ad8\u98a8\u96aa')
        elif pct < -2:
            psych.append('\u4eca\u65e5\u8dcc\u5e45\u8f03\u5927-\u52ff\u6050\u614c\u629b\u552e')
        if rt['volume'] > 100000:
            psych.append('\u6210\u4ea4\u91cf\u653e\u5927-\u5e02\u5834\u95dc\u6ce8\u5ea6\u9ad8')
        elif rt['volume'] < 30000:
            psych.append('\u6210\u4ea4\u91cf\u504f\u4f4e-\u6d41\u52d5\u6027\u8f03\u5dee')

        report = '\u3010 00878 \u76d1\u63a7\u5831\u544a \u3011\n'
        report += now_str + ' \u53f0\u5317\u6642\u9593\n'
        report += '========================\n\n'
        report += '\u3010\u5373\u6642\u5831\u50f9\u3011\n'
        report += '\u73fe\u50f9: $' + str(round(price, 2)) + '\n'
        report += '\u6f32\u8dcc: $' + str(round(change, 2)) + ' (' + str(round(pct, 2)) + '%)\n'
        report += '\u958b\u76e4: $' + str(round(rt['open'], 2)) + '\n'
        report += '\u6700\u9ad8: $' + str(round(rt['high'], 2)) + '\n'
        report += '\u6700\u4f4e: $' + str(round(rt['low'], 2)) + '\n'
        report += '\u6210\u4ea4\u91cf: ' + str(rt['volume']) + '\n\n'
        report += '\u3010\u6280\u8853\u6307\u6a19\u3011\n'
        report += 'EMA5: ' + str(ema5) + '\n'
        report += 'EMA10: ' + str(ema10) + '\n'
        report += 'EMA20: ' + str(ema20) + '\n'
        report += 'EMA60: ' + str(ema60) + '\n'
        report += 'RSI: ' + str(rsi) + '\n'
        report += '\u5747\u7dda\u72b6\u614b: ' + trend + '\n\n'
        report += '\u3010\u6301\u4ed3\u72b6\u6cc1\u3011\n'
        if state['position'] == 'long':
            report += '\u6301\u6709: ' + str(state['size']) + '\u80a1\n'
            report += '\u6210\u672c: $' + str(state['entry']) + '\n'
            report += '\u5e38\u9762\u76c8\u4e8f: ' + str(pnl_pct) + '% ($' + str(pnl) + ')\n'
            days = (now - datetime.strptime(state['date'], '%Y-%m-%d')).days if state['date'] else 0
            report += '\u6301\u6709\u5929\u6578: ' + str(days) + '\u5929\n'
        else:
            report += '\u7a7a\u5009-\u7b49\u5f85\u8cb2\u5165\u573a\n'
        report += '\n\u3010\u5e02\u5834\u5fc3\u7406\u5206\u6790\u3011\n'
        for p in psych:
            report += '\u2022 ' + p + '\n'
        report += '\n\u3010\u7b56\u7565\u5efa\u8b70\u3011\n'
        if signal == 'buy':
            report += '\u2705 \u8cb2\u5165\u8a0a\u865f \u2705\n'
            report += '\u5efa\u8b70\u8cb2\u5165 00878\n'
            report += '\u6311\u55ae\u50f9: $' + str(round(price, 2)) + '\n'
            report += '\u6578\u91cf: 12\u80a1 (\u7d04$400)\n'
            report += '\u4e0b\u55ae\u65b9\u5f0f: \u7389\u5c71App \u96f6\u80a1\u8cb2\u5165\n'
        elif signal == 'sell':
            report += '\u26a0\ufe0f \u8ce4\u51fa\u8a0a\u865f \u26a0\ufe0f\n'
            report += '\u5efa\u8b70\u8ce4\u51fa 00878\n'
            report += '\u6311\u55ae\u50f9: $' + str(round(price, 2)) + '\n'
        else:
            report += '\u7b49\u5f85\u8a0a\u865f\n'

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