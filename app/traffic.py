# Simulated users: mostly searches, some checkouts
import json, random, time, urllib.error, urllib.request

SHOP = "http://shop:8000"
WORDS = ["laptop", "phone", "kazakh", "book", "chair", "lamp", "bag", "shoes", "tea", "pen"]
CARDS = ["visa"] * 6 + ["mastercard"] * 3 + ["unionpay"]


def call(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(SHOP + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except (urllib.error.HTTPError, OSError):
        pass


while True:
    if random.random() < 0.7:
        n = 6 if random.random() < 0.08 else random.randint(1, 2)
        call("GET", "/api/search?q=" + "+".join(random.choices(WORDS, k=n)))
    else:
        number = "".join(random.choices("0123456789", k=16))
        call("POST", "/api/checkout", {"card": random.choice(CARDS), "amount": random.randint(500, 90000),
                                       "card_number": number})
    time.sleep(random.uniform(0.05, 0.25))
