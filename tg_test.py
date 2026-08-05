import os, requests, json
from datetime import datetime, timezone, timedelta

BOT = os.environ.get('TG_BOT_TOKEN', '')
UID = os.environ.get('TG_USER_ID', '')
STATE_FILE = '.tw00878_state.json'

BUY_FEE = 0.001425
SELL_FEE = 0.001425
TAX = 0.001
TOTAL_FEE = BUY_FEE + SELL_FEE + TAX

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
    
    price = None
    if d['z'] != '-' and d['z']:
        price = float(d['z'])
    elif d['a'] and d['b']:
        ask = float(d['a'].split('_')[0])
        bid = float(d['b'].split('_')[0])
        price = round((ask + bid) / 2, 2)
    elif d['o'] and d['o'] != '-':
        price = float(d['o'])
    
    return {
        'price': price,
        'open': float(d['o']) if d['o'] != '-' else 0,
        'high': float(d['h']) if d['h'] != '-' else 0,
        'low': float(d['l']) if d['l'] != '-' else 0,
        'yesterday': float(d['y']) if d['y'] != '-' else 0,
        'volume': int(d['v']) if d['v'] != '-' else 0,
    }

def get_history():
    try:
        import pandas as pd
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/00878.TW?range=6mo&interval=1d'
        hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=hdr, timeout=20)
        data = r.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        
        if len(closes) < 20:
            return None
        
        df = pd.DataFrame({'Close': closes})
        df['ema5'] = df['Close'].ewm(span=5).mean()
        df['ema10'] = df['Close'].ewm(span=10).mean()
        df['ema20'] = df['Close'].ewm(span=20).mean()
        df['ema60'] = df['Close'].ewm(span=60).mean()
        df['rsi'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() / df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
        return df
    except Exception as e:
        return None

try:
    Taipei = timezone(timedelta(hours=8))
    now = datetime.now(Taipei)
    now_str = now.strftime('%Y-%m-%d %H:%M')
    rt = get_price()
    price = rt['price']

    if price is None:
        send('00878 no price')
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
        if prev_ema5 <= prev_ema20 and ema5 > ema20:
            signal = 'buy'
        elif prev_ema5 >= prev_ema20 and ema5 < ema20:
            signal = 'sell'
        elif rsi < 30 and state['position'] == 'none':
            signal = 'buy'
        elif rsi > 75 and state['position'] == 'long':
            signal = 'sell'

        pnl = 0
        pnl_pct = 0
        fee = 0
        net_pnl = 0
        if state['position'] == 'long' and state['entry'] > 0:
            fee = round(state['entry'] * state['size'] * TOTAL_FEE, 2)
            pnl = round((price - state['entry']) * state['size'], 2)
            pnl_pct = round((price - state['entry']) / state['entry'] * 100, 2)
            net_pnl = round(pnl - fee, 2)

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
            report += '\u8cb2\u5165\u6210\u672c: $' + str(state['entry']) + '\n'
            report += '\u6bdb\u5229: ' + str(pnl_pct) + '% ($' + str(pnl) + ')\n'
            report += '\u624b\u7e8c\u8cbb: $' + str(fee) + '\n'
            report += '\u6de8\u5229: $' + str(net_pnl) + '\n'
        else:
            report += '\u7a7a\u5009 - \u7b49\u5f85\u8cb2\u5165\u573a\n'
        psych = []
        if state['position'] == 'long':
            if net_pnl > 0:
                psych.append('\u767d\u8a71\uff1a\u7b97\u4e86\u624b\u7e8c\u8cbb\u4e4b\u5f8c\u4f60\u9084\u662f\u8d0f\u94b1\u7684\uff0c\u5225\u56e0\u70ba\u662f\u8d0f\u5c31\u7dca\u5f35\u60f3\u8ce4\uff0c\u7b49\u6307\u6a19\u554a\u7b49\u6307\u6a19\u3002')
            elif net_pnl > -state['entry'] * state['size'] * 0.01:
                psych.append('\u767d\u8a71\uff1a\u76ee\u524d\u8b17\u4e00\u9ede\u9ede\u3002\u4f46 00878 \u662f ETF\uff0c\u8dcc\u5f97\u6162\uff0c\u5225\u5bb3\u6015\u3002\u7b49\u8ce4\u51fa\u8a0a\u865f\u518d\u8ce4\uff0c\u4e0d\u8981\u81ea\u5df1\u7dca\u5f35\u5c31\u8ce4\u6389\u3002')
            else:
                psych.append('\u767d\u8a71\uff1a\u8b17\u8d85\u904e 1% \u4e86\uff0c\u6709\u9ede\u591a\u3002\u4e0b\u6b21\u8a0a\u865f\u4f86\u6642\u8981\u8ddf\u7740\u505a\uff0c\u4e0d\u8981\u53ef\u60dc\u3002')
        else:
            psych.append('\u767d\u8a71\uff1a\u73fe\u5728\u7a7a\u5009\uff0c\u60a8\u53ea\u8981\u7b49\u8cb2\u5165\u8a0a\u865f\u5c31\u597d\u3002')
        if pct < -2:
            psych.append('\u767d\u8a71\uff1a\u4eca\u5929\u8dcc\u5f97\u6bd4\u8f03\u591a\u3002\u5225\u5bb3\u6015\uff0c\u767d\u8a71\u5c31\u662f\u5225\u7dca\u5f35\u3002')
        elif pct > 2:
            psych.append('\u767d\u8a71\uff1a\u4eca\u5929\u6f32\u5f97\u6bd4\u8f03\u591a\u3002\u5225\u8ffd\u9ad8\uff0c\u7b49\u7b2c\u4e00\u500b\u8ce4\u51fa\u8a0a\u865f\u5c31\u597d\u3002')
        report += '\n\u3010\u767d\u8a71\u5fc3\u7406\u5c0f\u5340\u3011\n'
        for p in psych:
            report += p + '\n'
        report += '\n'
        report += '\u3010\u4ea4\u6613\u6210\u672c\u3011\n'
        report += '\u4f86\u56de\u7e3d\u6210\u672c: 0.385%\n'
        report += '\u6bcf\u80a1\u6700\u4f4e\u76c8\u92b7: $' + str(round(price * TOTAL_FEE, 2)) + '\n\n'
        report += '\u3010\u7b56\u7565\u5efa\u8b70\u3011\n'
        if signal == 'buy':
            report += '\u2705 \u8cb2\u5165\u8a0a\u865f \u2705\n'
            report += '\u5efa\u8b70\u8cb2\u5165 00878\n'
            report += '\u6311\u55ae\u50f9: $' + str(round(price, 2)) + '\n'
            report += '\u6578\u91cf: 12\u80a1 (\u7d04$400)\n'
            report += '\u7e3d\u624b\u7e8c\u8cbb: $' + str(round(price * 12 * TOTAL_FEE, 2)) + '\n'
            report += '\u4e0b\u55ae\u65b9\u5f0f: \u7389\u5c71App \u96f6\u80a1\u8cb2\u5165\n'
        elif signal == 'sell':
            if state['position'] == 'long' and state['entry'] > 0:
                gross_pct = round((price - state['entry']) / state['entry'] * 100, 2)
                net_pct = round(gross_pct - TOTAL_FEE * 100, 2)
                report += '\u26a0\ufe0f \u8ce4\u51fa\u8a0a\u865f \u26a0\ufe0f\n'
                report += '\u5efa\u8b70\u8ce4\u51fa 00878\n'
                report += '\u6311\u55ae\u50f9: $' + str(round(price, 2)) + '\n'
                report += '\u6bdb\u5229: ' + str(gross_pct) + '%\n'
                report += '\u624b\u7e8c\u8cbb: ' + str(round(TOTAL_FEE * 100, 2)) + '%\n'
                report += '\u6de8\u5229: ' + str(net_pct) + '%\n'
                if net_pct > 0:
                    report += '\u6de8\u8d5a: $' + str(net_pnl) + '\n'
                else:
                    report += '\u6de8\u8b17: $' + str(net_pnl) + '\n'
            else:
                report += '\u26a0\ufe0f \u8ce4\u51fa\u8a0a\u865f \u26a0\ufe0f\n'
                report += '\u5efa\u8b70\u8ce4\u51fa 00878\n'
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