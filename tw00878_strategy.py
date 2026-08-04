import os, json, requests
from datetime import datetime, timedelta
import pandas as pd

BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
USER_ID = os.environ.get('TG_USER_ID', '')
STATE_FILE = '.tw00878_state.json'

def send(msg):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    requests.post(url, json={'chat_id': USER_ID, 'text': msg, 'parse_mode': 'HTML'})

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'position': 'none', 'position_size': 0, 'entry_price': 0, 'total_cost': 0, 'entry_date': ''}

def save_state(s):
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f)

def get_realtime():
    url = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_00878.tw'
    r = requests.get(url, timeout=10)
    data = r.json()['msgArray'][0]
    return {
        'code': data['c'],
        'price': float(data['z']) if data['z'] != '-' else None,
        'open': float(data['o']) if data['o'] != '-' else None,
        'high': float(data['h']) if data['h'] != '-' else None,
        'low': float(data['l']) if data['l'] != '-' else None,
        'yesterday': float(data['y']) if data['y'] != '-' else None,
        'volume': int(data['v']) if data['v'] != '-' else 0,
        'time': data['t'],
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
        df['rsi'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() / df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
        return df
    except:
        return None

def run():
    state = load_state()
    try:
        rt = get_realtime()
    except Exception as e:
        send(f'00878 即時資料取得失敗: {e}')
        return

    price = rt['price']
    if price is None:
        send('00878 目前無成交價')
        return

    now = datetime.now().strftime('%H:%M')
    price_change = round(price - rt['yesterday'], 2)
    price_change_pct = round(price_change / rt['yesterday'] * 100, 2)

    # 技術指標
    df = get_history()
    if df is not None:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        ema5 = round(latest['ema5'], 2)
        ema10 = round(latest['ema10'], 2)
        ema20 = round(latest['ema20'], 2)
        rsi = round(latest['rsi'], 1)
        prev_ema5 = round(prev['ema5'], 2)
        prev_ema20 = round(prev['ema20'], 2)
        cross = '金叉(多頭)' if ema5 > ema20 else '死叉(空頭)' if ema5 < ema20 else '糾結'
    else:
        ema5 = ema10 = ema20 = rsi = 0
        prev_ema5 = prev_ema20 = 0
        cross = '無法計算'

    # 盈虧
    if state['position'] == 'long':
        unrealized = round((price - state['entry_price']) * state['position_size'], 2)
        pnl_pct = round((price - state['entry_price']) / state['entry_price'] * 100, 2)
    else:
        unrealized = 0
        pnl_pct = 0

    # 訊號判斷
    signal = 'none'
    reason = ''
    if prev_ema5 <= prev_ema20 and ema5 > ema20:
        signal = 'buy'
        reason = f'EMA5({ema5}) 突破 EMA20({ema20}) 金叉'
    elif prev_ema5 >= prev_ema20 and ema5 < ema20:
        signal = 'sell'
        reason = f'EMA5({ema5}) 跌破 EMA20({ema20}) 死叉'
    elif rsi < 30 and state['position'] == 'none':
        signal = 'buy'
        reason = f'RSI({rsi}) 超賣區'
    elif rsi > 75 and state['position'] == 'long':
        signal = 'sell'
        reason = f'RSI({rsi}) 超買區'

    # 心理分析
    psych = []
    if rsi < 30: psych.append('恐慌區，適合分批進場')
    elif rsi > 70: psych.append('貪婪區，考慮減倉')
    elif 40 <= rsi <= 60: psych.append('中性，正常持有')
    if price_change_pct > 2: psych.append('漲幅較大，追高注意')
    elif price_change_pct < -2: psych.append('跌幅較大，勿恐慌')

    current_min = datetime.now().minute

    # ====== 訊號推送 (優先) ======
    if signal in ('buy', 'sell'):
        msg = f'{"🔔" if signal=="buy" else "⚠️"} <b>{signal.upper()} 訊號</b>\n'
        msg += f'00878 現價: ${price}\n'
        msg += f'原因: {reason}\n'
        msg += f'RSI: {rsi} | 均線: {cross}\n'
        if state['position'] == 'long':
            msg += f'持倉: {state["position_size"]}股 | 成本: ${state["entry_price"]}\n'
            msg += f'帳面: {pnl_pct:+.2f}% (${unrealized:+.2f})\n'
        msg += f'---\n'
        if signal == 'buy' and state['position'] == 'none':
            msg += f'✅ 建議買入 00878\n'
            msg += f'掛單: ${price} | 12股 (約$400)\n'
            msg += f'下單: 玉山App → 零股買入'
        elif signal == 'sell' and state['position'] == 'long':
            msg += f'✅ 建議賣出 00878\n'
            msg += f'掛單: ${price} | 全部賣出'
        send(msg)

        if signal == 'buy' and state['position'] == 'none':
            state['position'] = 'long'
            state['position_size'] = 12
            state['entry_price'] = price
            state['total_cost'] = price * 12
            state['entry_date'] = datetime.now().strftime('%Y-%m-%d')
        elif signal == 'sell' and state['position'] == 'long':
            state['position'] = 'none'
            state['position_size'] = 0
            state['entry_price'] = 0
            state['total_cost'] = 0
            state['entry_date'] = ''

    # ====== 完整報告 (每10分鐘) ======
    if current_min % 10 == 0:
        rpt = f'<b>📊 00878 完整報告 [{now}]</b>\n'
        rpt += f'{"="*28}\n'
        rpt += f'<b>【即時報價】</b>\n'
        rpt += f'現價: ${price} ({price_change_pct:+.2f}%)\n'
        rpt += f'開: ${rt["open"]} 高: ${rt["high"]} 低: ${rt["low"]}\n'
        rpt += f'昨收: ${rt["yesterday"]} 量: {rt["volume"]:,}\n'
        rpt += f'{"="*28}\n'
        rpt += f'<b>【技術指標】</b>\n'
        rpt += f'EMA5: {ema5} | EMA10: {ema10}\n'
        rpt += f'EMA20: {ema20} | RSI: {rsi}\n'
        rpt += f'均線: {cross}\n'
        rpt += f'{"="*28}\n'
        rpt += f'<b>【持倉】</b>\n'
        if state['position'] == 'long':
            rpt += f'持有: {state["position_size"]}股 | 成本: ${state["entry_price"]}\n'
            rpt += f'帳面: {pnl_pct:+.2f}% (${unrealized:+.2f})\n'
        else:
            rpt += f'空倉 | 可用: $400\n'
        rpt += f'{"="*28}\n'
        rpt += f'<b>【策略建議】</b>\n'
        if state['position'] == 'none':
            if rsi < 30: rpt += f'超賣，建議分批進場\n'
            else: rpt += f'等待金叉或超賣訊號\n'
        else:
            if rsi > 75: rpt += f'超買，考慮減倉\n'
            elif pnl_pct < -5: rpt += f'虧損>5%，評估停損\n'
            else: rpt += f'持有觀察\n'
        rpt += f'{"="*28}\n'
        for p in psych:
            rpt += f'• {p}\n'
        send(rpt)

    # ====== 價格推送 (每5分鐘) ======
    elif current_min % 5 == 0:
        pmsg = f'<b>00878 [{now}]</b>\n'
        pmsg += f'${price} ({price_change_pct:+.2f}%)\n'
        pmsg += f'RSI: {rsi}'
        if state['position'] == 'long':
            pmsg += f' | 帳面: {pnl_pct:+.2f}%'
        send(pmsg)

    save_state(state)

if __name__ == '__main__':
    run()