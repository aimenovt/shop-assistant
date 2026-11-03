import json
import os
import re

with open("data/kb.json", encoding="utf-8") as f:
    KB = json.load(f)

# заглушка, в реальном магазине тут был бы запрос в CRM
with open("data/orders.json", encoding="utf-8") as f:
    ORDERS = json.load(f)

DISCOUNT = ["скидк", "промокод", "купон", "дешевле", "акци", "%"]
DEFECT = ["брак", "слома", "не работа", "дефект"]
RETURN = ["вернуть", "верну", "возврат", "сдать"]
OPENED = ["вскрыт", "распаков", "открыл"]
DELIVERY = ["достав", "курьер", "привез", "где мой"]
PRICE = ["цена", "стоит", "стоят", "стоимость", "в наличии"]
# этого в регламенте нет
NOT_IN_KB = ["оплат", "наличн", "гаранти", "обмен", "самовывоз", "адрес", "телефон", "батаре", "цвет"]
HACK = ["забудь", "игнорируй", "ты теперь", "промпт", "prompt", "ignore"]

OPERATOR = "Передал вопрос оператору, он ответит здесь."
NO_ANSWER = "В регламенте ответа на этот вопрос нет, а придумывать я не буду. " + OPERATOR
NO_HACK = "Правила поменять не могу, отвечаю только по регламенту магазина."


def has(text, words):
    return any(w in text for w in words)


def reply(text, facts, operator=False):
    return {"text": text, "facts": facts, "operator": operator}


def answer(question, llm=None):
    t = question.lower().replace("ё", "е")
    order = re.search(r"заказ\D{0,5}(\d+)", t)
    day = re.search(r"(\d+)\s*-?\s*[а-я]{0,2}\s*(день|дня|дней)", t)
    start = NO_HACK + " " if has(t, HACK) else ""

    if has(t, DISCOUNT):
        percent = re.search(r"(\d+)\s*%", t)
        text = KB["discount"]
        if percent:
            text = f"Скидок нет ни при каких условиях, так что {percent.group(1)}% дать не могу."
        return reply(start + text + " " + KB["product"], ["discount", "product"])

    if has(t, NOT_IN_KB):
        return ask_llm(question, llm, start)

    if has(t, DEFECT):
        return reply(start + KB["defect"] + " " + OPERATOR, ["defect"], operator=True)

    if has(t, RETURN):
        rule = "return_opened" if has(t, OPENED) else "return"
        if not day:
            return reply(start + KB[rule] + " " + KB["money_back"], [rule, "money_back"])
        n = int(day.group(1))
        if n <= 14:
            return reply(start + f"Да, на {n}-й день ещё можно. {KB[rule]} {KB['money_back']}", [rule, "money_back"])
        return reply(start + f"Нет, на {n}-й день уже нельзя. {KB[rule]} "
                     "Если у наушников брак, можем принять их на экспертизу, но деньги сразу не обещаем.",
                     [rule, "defect"])

    if order:
        number = order.group(1)
        if number in ORDERS:
            o = ORDERS[number]
            return reply(start + f"Заказ №{number}: {o['status']}, доставка {o['date']} с {o['slot']}.", [])
        return reply(start + f"Заказ №{number} не нашёл в системе, поэтому статус и время доставки "
                     f"назвать не могу. Общее правило: {KB['delivery']} {OPERATOR}", ["delivery"], operator=True)

    if has(t, DELIVERY):
        return reply(start + KB["delivery"], ["delivery"])

    if has(t, PRICE):
        return reply(start + KB["product"], ["product"])

    if start:
        return reply(NO_HACK, [])

    return ask_llm(question, llm)


def ask_llm(question, llm, start=""):
    # LLM отвечает только на то, что не покрыли правила.
    # Ответ берём, если он ссылается на пункты базы и в нём нет чисел не из этих пунктов.
    if llm:
        res = llm(question)
        if res and res["facts"] and all(f in KB for f in res["facts"]):
            allowed = numbers(question + " " + " ".join(KB[f] for f in res["facts"]))
            if numbers(res["text"]) <= allowed:
                return reply(start + res["text"], res["facts"])
    return reply(start + NO_ANSWER, [], operator=True)


def numbers(text):
    return set(re.findall(r"\d+", text.replace(" ", "")))


def make_llm():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    from pydantic import BaseModel

    class Answer(BaseModel):
        text: str
        facts: list[str]

    client = anthropic.Anthropic()
    kb_text = "\n".join(f"[{k}] {v}" for k, v in KB.items())
    with open("prompt.txt", encoding="utf-8") as f:
        prompt = f.read().replace("{kb}", kb_text)

    def ask(question):
        try:
            resp = client.messages.parse(
                model="claude-opus-5-5",
                max_tokens=2000,
                system=prompt,
                output_config={"effort": "low"},
                output_format=Answer,
                messages=[{"role": "user", "content": question}],
            )
            return resp.parsed_output.model_dump()
        except Exception as e:
            print("ошибка LLM:", e)
            return None

    return ask


if __name__ == "__main__":
    llm = make_llm()
    while True:
        q = input("Вы: ")
        if not q:
            break
        r = answer(q, llm)
        print("Бот:", r["text"])
        print("    факты:", r["facts"], "| оператор:", r["operator"], "\n")
