import json
import os
import time
import urllib.request

from bot import answer, make_llm

API = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/"
OPERATOR_CHAT = os.getenv("OPERATOR_CHAT_ID")


def tg(method, **params):
    req = urllib.request.Request(API + method, json.dumps(params).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=40))["result"]


llm = make_llm()
offset = 0
while True:
    try:
        updates = tg("getUpdates", offset=offset, timeout=30)
    except Exception as e:
        print(e)
        time.sleep(5)
        continue

    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message", {})
        if "text" not in msg:
            continue
        r = answer(msg["text"], llm)
        tg("sendMessage", chat_id=msg["chat"]["id"], text=r["text"])
        if r["operator"] and OPERATOR_CHAT:
            tg("sendMessage", chat_id=OPERATOR_CHAT, text="Нужен оператор:\n" + msg["text"])
