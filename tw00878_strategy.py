import os, json, requests, time
from datetime import datetime, timedelta
import yfinance as yf
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
    return {'position': 'none', 'position_size': 0, 'entry_price': 0, 'total_cost': 0, 'entry_date': '', 'signals': []}

def save_state(s):
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f)

def get_data():
    tk = yf.Ticker('00878.TW')
    df = tk.history(period='6mo', interval='1d')
    if df.empty:
        return None
    df['ema5'] = df['Close'].ewm(span=5).mean()
    df['ema10'] = df['Close'].ewm(span=10).mean()
    df['ema20'] = df['Close'].ewm(span=20).mean()
    df['ema60'] = df['Close'].ewm(span=60).mean()
    df['rsi'] = 100 - 100 / (1 + df['Close'].diff().clip(lower=0).rolling(14).mean() / df['Close'].diff().clip(upper=0).abs().rolling(14).mean())
    df['upper'] = df['Close'].rolling(20).mean() + df['Close'].rolling(20).std() * 2
    df['lower'] = df['Close'].rolling(20).mean() - df['Close'].rolling(20).std() * 2
    df['volume_ma'] = df['Volume'].rolling(20).mean()
    return df

def calc_pnl(state, price):
    if state['position'] == 'long' and state['position_size'] > 0:
        unrealized = (price - state['entry_price']) * state['position_size']
        cost = state['entry_price'] * state['position_size']
        pnl_pct = (price - state['entry_price']) / state['entry_price'] * 100
        return round(unrealized, 2), round(pnl_pct, 2), round(cost, 2)
    return 0, 0, 0

def run():
    state = load_state()
    df = get_data()
    if df is None:
        send('00878 無法取得資料，請檢查網路或代碼')
        return

    now = datetime.now().strftime('%H:%M')
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = round(latest['Close'], 2)
    prev_price = round(prev['Close'], 2)
    price_change = round(price - prev_price, 2)
    price_change_pct = round((price - prev_price) / prev_price * 100, 2)
    ema5 = round(latest['ema5'], 2)
    ema10 = round(latest['ema10'], 2)
    ema20 = round(latest['ema20'], 2)
    ema60 = round(latest['ema60'], 2)
    rsi = round(latest['rsi'], 1)
    bb_upper = round(latest['upper'], 2)
    bb_lower = round(latest['lower'], 2)
    vol = int(latest['Volume'])
    vol_ma = int(latest['volume_ma'])
    vol_ratio = round(vol / vol_ma, 2) if vol_ma > 0 else 0
    prev_ema5 = round(prev['ema5'], 2)
    prev_ema20 = round(prev['ema20'], 2)

    # 計算盈虧
    unrealized_pnl, pnl_pct, position_cost = calc_pnl(state, price)

    # 判斷訊號 (金叉/死叉/超買/超賣)
    signal = 'none'
    reason = ''
    urgency = 0

    # 金叉確認
    if prev_ema5 <= prev_ema20 and ema5 > ema20:
        signal = 'buy'
        reason = f'EMA5({ema5}) 突破 EMA20({ema20}) 金叉'
        urgency = 3
    # 死叉確認
    elif prev_ema5 >= prev_ema20 and ema5 < ema20:
        signal = 'sell'
        reason = f'EMA5({ema5}) 跌破 EMA20({ema20}) 死叉'
        urgency = 3
    # 超賣區
    elif rsi < 30 and state['position'] == 'none':
        signal = 'buy'
        reason = f'RSI({rsi}) 進入超賣區(<30)'
        urgency = 2
    # 超買區
    elif rsi > 75 and state['position'] == 'long':
        signal = 'sell'
        reason = f'RSI({rsi}) 進入超買區(>75)'
        urgency = 2
    # 持有中普通提醒
    elif state['position'] == 'long' and rsi < 40:
        signal = 'caution'
        reason = f'RSI({rsi}) 偏低，注意支撐'
        urgency = 1
    elif state['position'] == 'long' and rsi > 65:
        signal = 'caution'
        reason = f'RSI({rsi}) 偏高，注意壓力'
        urgency = 1

    # 心理面分析
    psychology = []
    if rsi < 30:
        psychology.append('市場恐慌區，適合分批進場')
    elif rsi > 70:
        psychology.append('市場貪婪區，考慮減倉')
    elif 40 <= rsi <= 60:
        psychology.append('市場情緒中性，正常持有')
    if price_change_pct > 2:
        psychology.append('今日漲幅較大，追高注意風險')
    elif price_change_pct < -2:
        psychology.append('今日跌幅較大，勿恐慌拋售')
    if vol_ratio > 1.5:
        psychology.append(f'成交量放大{vol_ratio}倍，市場關注度高')
    elif vol_ratio < 0.5:
        psychology.append('成交量偏低，流動性較差')

    # ====== 5分鐘價格推送 ======
    price_msg = f'<b>00878 即時報價 [{now}]</b>\n'
    price_msg += f'現價: ${price}'
    if price_change >= 0:
        price_msg += f' (+${price_change} / +{price_change_pct}%)'
    else:
        price_msg += f' (${price_change} / {price_change_pct}%)'
    price_msg += f'\nRSI: {rsi}'
    if state['position'] == 'long':
        price_msg += f'\n帳面: {pnl_pct:+.2f}% (${unrealized_pnl:+.2f})'
    price_msg += f'\n量: {vol}'

    # ====== 10分鐘完整報告 ======
    # 用目前秒數來判斷是否為10分鐘的整數倍
    current_min = datetime.now().minute
    is_full_report = current_min % 10 == 0

    # ====== 訊號推送 ======
    if urgency >= 2:
        signal_msg = f'<b>🔔 {signal.upper()} 訊號</b>\n'
        signal_msg += f'00878 現價: ${price}\n'
        signal_msg += f'原因: {reason}\n'
        signal_msg += f'---\n'
        signal_msg += f'EMA5: {ema5} | EMA10: {ema10} | EMA20: {ema20}\n'
        signal_msg += f'RSI: {rsi} | 漲跌幅: {price_change_pct:+.2f}%\n'
        if state['position'] == 'long':
            signal_msg += f'持倉: {state["position_size"]}股 | 成本: ${state["entry_price"]}\n'
            signal_msg += f'帳面: {pnl_pct:+.2f}% (${unrealized_pnl:+.2f})\n'
        signal_msg += f'---\n'
        signal_msg += f'<b>操作建議:</b>\n'
        if signal == 'buy':
            if state['position'] == 'none':
                signal_msg += f'✅ 建議買入 00878 零股\n'
                signal_msg += f'   掛單價格: ${price}\n'
                signal_msg += f'   建議數量: 12股 (約$400)\n'
                signal_msg += f'   下單方式: 玉山App → 零股買入'
            else:
                signal_msg += f'✅ 建議加碼買入\n'
        elif signal == 'sell':
            signal_msg += f'✅ 建議賣出 00878 零股\n'
            signal_msg += f'   掛單價格: ${price}\n'
            signal_msg += f'   建議數量: 全部賣出'
        send(signal_msg)

        # 更新狀態
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

    # 整份報告 (10分鐘)
    if is_full_report:
        report = f'<b>📊 00878 完整報告 [{now}]</b>\n'
        report += f'{"="*30}\n'
        report += f'<b>【即時報價】</b>\n'
        report += f'現價: ${price}'
        if price_change >= 0:
            report += f' (+${price_change} / +{price_change_pct}%)'
        else:
            report += f' (${price_change} / {price_change_pct}%)'
        report += f'\n成交量: {vol:,} | 量比: {vol_ratio}x\n'
        report += f'{"="*30}\n'
        report += f'<b>【技術指標】</b>\n'
        report += f'EMA5:  {ema5}\n'
        report += f'EMA10: {ema10}\n'
        report += f'EMA20: {ema20}\n'
        report += f'EMA60: {ema60}\n'
        report += f'RSI:   {rsi}\n'
        report += f'布林上: {bb_upper} | 布林下: {bb_lower}\n'
        cross = '金叉(多頭)' if ema5 > ema20 else '死叉(空頭)' if ema5 < ema20 else '糾結'
        report += f'均線: {cross}\n'
        report += f'{"="*30}\n'
        report += f'<b>【持倉狀況】</b>\n'
        if state['position'] == 'long':
            report += f'狀態: 持倉中\n'
            report += f'持倉: {state["position_size"]}股\n'
            report += f'成本: ${state["entry_price"]}\n'
            report += f'投入: ${state["total_cost"]:.2f}\n'
            report += f'帳面: {pnl_pct:+.2f}% (${unrealized_pnl:+.2f})\n'
            days_held = (datetime.now() - datetime.strptime(state['entry_date'], '%Y-%m-%d')).days if state['entry_date'] else 0
            report += f'持有天數: {days_held}天\n'
        else:
            report += f'狀態: 空倉\n'
            report += f'可用資金: $400\n'
        report += f'{"="*30}\n'
        report += f'<b>【市場心理分析】</b>\n'
        for p in psychology:
            report += f'• {p}\n'
        report += f'{"="*30}\n'
        report += f'<b>【策略建議】</b>\n'
        if state['position'] == 'none':
            if rsi < 30:
                report += f'建議: 超賣區可分批進場\n'
            elif rsi < 40:
                report += f'建議: 接近低檔，準備進場\n'
            else:
                report += f'建議: 等待金叉或超賣訊號\n'
        else:
            if rsi > 75:
                report += f'建議: 超買區考慮減倉\n'
            elif pnl_pct > 10:
                report += f'建議: 獲利超過10%，可考慮部分止盈\n'
            elif pnl_pct < -5:
                report += f'建議: 虧損超過5%，評估是否停損\n'
            else:
                report += f'建議: 持有觀察\n'
        send(report)

    # 5分鐘價格推送 (只在整點5分時，避免洗版)
    elif current_min % 5 == 0:
        send(price_msg)

    # 更新狀態
    save_state(state)

if __name__ == '__main__':
    run()