import os, sys, pandas as pd, numpy as np, requests, datetime as dt

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER = os.getenv("LINE_USER_ID", "")
TZ = dt.timezone(dt.timedelta(hours=9))

def get_price():
    try:
        url = "https://jp.investing.com/indices/japan-225-futures"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        import re
        m = re.search(r'data-test="instrument-price-last"[^>]*>([^<]+)<', r.text)
        if m:
            return float(m.group(1).replace(",", ""))
    except Exception:
        pass
    # fallback: Yahoo
    csv_url = "https://query1.finance.yahoo.com/v7/finance/download/NK=F?interval=1d&events=history&includeAdjustedClose=true"
    df = pd.read_csv(csv_url)
    return float(df.iloc[-1]["Close"])

def get_history():
    csv_url = "https://query1.finance.yahoo.com/v7/finance/download/NK=F?interval=1d&events=history&includeAdjustedClose=true"
    df = pd.read_csv(csv_url)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.tail(200).reset_index(drop=True)

def compute(df):
    c = df["Close"]
    df["SMA5"] = c.rolling(5).mean()
    df["SMA20"] = c.rolling(20).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))
    ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    df["MACDhist"] = macd - signal
    return df

def signal(price, df):
    row = df.iloc[-1]
    score = 0
    if row["SMA5"] > row["SMA20"]: score += 1
    if row["MACDhist"] > 0: score += 1
    if row["RSI14"] < 35: score += 1
    if row["RSI14"] > 65: score -= 1
    prob = 0.5 + 0.15 * score  # ← 勝率係数0.15に変更（75%ぐらいでも出る）
    prob = max(0.05, min(0.95, prob))
    if prob >= 0.75: sig = "買い"
    elif (1 - prob) >= 0.75: sig = "売り"
    else: sig = "様子見"
    return sig, prob

def notify(msg):
    if not LINE_TOKEN or not LINE_USER:
        print(msg)
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    data = {"to": LINE_USER, "messages": [{"type": "text", "text": msg}]}
    requests.post(url, headers=headers, json=data)

def task():
    p = get_price()
    df = compute(get_history())
    sig, prob = signal(p, df)
    text = f"📊225先物\n価格:{p:,.0f}\n判定:{sig}\n勝率推定:{prob*100:.1f}%"
    notify(text)

if __name__ == "__main__":
    task()