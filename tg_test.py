import os, requests, json

BOT = os.environ.get('TG_BOT_TOKEN', '')
UID = os.environ.get('TG_USER_ID', '')

r = requests.get('https://api.telegram.org/bot' + BOT + '/getMe')
print('Bot OK:', r.json().get('ok'))

msg = '00878 Strategy Test\n'
msg += 'Price: $32.57\n'
msg += 'Change: +$0.25 (+0.77%)\n'
msg += 'RSI: 58.2\n'
msg += 'EMA: Golden Cross\n'
msg += 'Position: None\n'
msg += 'Action: Wait for buy\n'

r2 = requests.post('https://api.telegram.org/bot' + BOT + '/sendMessage', json={'chat_id': UID, 'text': msg})
print('Send:', r2.status_code, r2.json().get('ok'))