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
                trend = 'Golden Cross (Bull)'
            elif ema5 < ema20:
                trend = 'Death Cross (Bear)'
            else:
                trend = 'Neutral'
        else:
            ema5 = ema10 = ema20 = ema60 = rsi = prev_ema5 = prev_ema20 = 0
            trend = 'N/A'

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

        report = '00878 Report\n'
        report += now_str + ' Taipei\n'
        report += '==================\n'
        report += 'Price: $' + str(round(price, 2)) + '\n'
        report += 'Change: $' + str(round(change, 2)) + ' (' + str(round(pct, 2)) + '%)\n'
        report += 'Open: $' + str(round(rt['open'], 2)) + '\n'
        report += 'High: $' + str(round(rt['high'], 2)) + '\n'
        report += 'Low: $' + str(round(rt['low'], 2)) + '\n'
        report += 'Volume: ' + str(rt['volume']) + '\n\n'
        report += 'EMA5: ' + str(ema5) + '\n'
        report += 'EMA10: ' + str(ema10) + '\n'
        report += 'EMA20: ' + str(ema20) + '\n'
        report += 'EMA60: ' + str(ema60) + '\n'
        report += 'RSI: ' + str(rsi) + '\n'
        report += 'Trend: ' + trend + '\n\n'
        if state['position'] == 'long':
            report += 'Position: ' + str(state['size']) + ' shares\n'
            report += 'Entry: $' + str(state['entry']) + '\n'
            report += 'Gross PnL: ' + str(pnl_pct) + '% ($' + str(pnl) + ')\n'
            report += 'Fees: $' + str(fee) + '\n'
            report += 'Net PnL: $' + str(net_pnl) + '\n\n'
        else:
            report += 'Position: Empty\n\n'

        buy_fee_per_share = round(price * TOTAL_FEE, 2)
        report += 'Fees per share: $' + str(buy_fee_per_share) + ' (0.385%)\n'
        report += 'Min profit per share: $' + str(round(price * 0.00385, 2)) + '\n\n'

        if signal == 'buy':
            report += '>>> BUY <<<\n'
            report += 'Buy 00878 at $' + str(round(price, 2)) + '\n'
            report += '12 shares (~$400)\n'
            report += 'Total fee: $' + str(round(price * 12 * TOTAL_FEE, 2)) + '\n'
            report += 'Min profit needed: ' + str(round(TOTAL_FEE * 100, 2)) + '%\n'
        elif signal == 'sell':
            if state['position'] == 'long' and state['entry'] > 0:
                gross_pct = round((price - state['entry']) / state['entry'] * 100, 2)
                net_pct = round(gross_pct - TOTAL_FEE * 100, 2)
                report += '>>> SELL <<<\n'
                report += 'Sell 00878 at $' + str(round(price, 2)) + '\n'
                report += 'Gross profit: ' + str(gross_pct) + '%\n'
                report += 'Total fee: ' + str(round(TOTAL_FEE * 100, 2)) + '%\n'
                report += 'Net profit: ' + str(net_pct) + '%\n'
                if net_pct > 0:
                    report += 'NET GAIN: $' + str(net_pnl) + '\n'
                else:
                    report += 'NET LOSS: $' + str(net_pnl) + '\n'
            else:
                report += '>>> SELL <<<\n'
                report += 'Sell 00878 at $' + str(round(price, 2)) + '\n'
        else:
            report += 'Action: Wait\n'

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