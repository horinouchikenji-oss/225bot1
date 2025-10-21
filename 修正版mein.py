import os, sys, pandas as pd, numpy as np, requests, datetime as dt
import time   # ← これを追加！

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER = os.getenv("LINE_USER_ID", "")
TZ = dt.timezone(dt.timedelta(hours=9))

def get_price():
    try:
        url = "https://jp.investing.com/indices/japan-225-futures"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        time.sleep(10)  # ← これを追加（10秒休ませる）
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