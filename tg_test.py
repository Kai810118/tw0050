import os, requests, json
from datetime import datetime

BOT = os.environ.get('TG_BOT_TOKEN', '')
UID = os.environ.get('TG_USER_ID', '')

def send(msg):
    requests.post('https://api.telegram.org/bot' + BOT + '/sendMessage', json={'chat_id': UID, 'text': msg})

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

try:
    rt = get_price()
    price = rt['price']
    if price is None:
        send('00878 no price')
    else:
        change = price - rt['yesterday']
        pct = change / rt['yesterday'] * 100 if rt['yesterday'] else 0
        now = datetime.now().strftime('%H:%M')

        msg = '\u3010 00878 \u5373\u6642\u5831\u50f9 \u3011\n'
        msg += '==================\n'
        msg += '\u73fe\u50f9: $' + str(round(price, 2)) + '\n'
        msg += '\u6f32\u8dcc: $' + str(round(change, 2)) + ' (' + str(round(pct, 2)) + '%)\n'
        msg += '\u958b\u76e4: $' + str(round(rt['open'], 2)) + '\n'
        msg += '\u6700\u9ad8: $' + str(round(rt['high'], 2)) + '\n'
        msg += '\u6700\u4f4e: $' + str(round(rt['low'], 2)) + '\n'
        msg += '\u6210\u4ea4\u91cf: ' + str(rt['volume']) + '\n'
        msg += '==================\n'
        msg += 'RSI: \u7121\u6cd5\u8a08\u7b97(\u76d5\u5f8c)\n'
        msg += '\u5747\u7dda: \u7b49\u5f85\u660e\u5929\u958b\u76e4\n'
        msg += '\u6301\u4ed3: \u7a7a\u5009\n'
        msg += '==================\n'
        msg += '\u7b56\u7565: \u7b49\u5f85\u660e\u5929\u958b\u76e4\u5f8c\u81ea\u52d5\u76d1\u63a7\n'
        msg += '\u6642\u9593: ' + now + '\n'
        msg += '\u6e2c\u8a66\u63a8\u64ad'
        send(msg)
except Exception as e:
    send('Error: ' + str(e))