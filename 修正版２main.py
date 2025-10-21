# main.py
import os, time, random, re, json
import requests
from datetime import datetime, timezone, timedelta

# ====== 環境変数（RenderのEnvironmentに設定してある想定）======
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER  = os.getenv("LINE_USER_ID", "")

TZ = timezone(timedelta(hours=9))  # JST

# ====== 共通: LINE通知 ======
def send_line(text: str):
    if not LINE_TOKEN or not LINE_USER:
        print("LINE環境変数が未設定です。", text)
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "to": LINE_USER,
        "messages": [{"type": "text", "text": text[:4900]}]
    }
    try:
        r = requests.post(url, headers=headers, data=json.dumps(body), timeout=15)
        r.raise_for_status()
        print("LINE送信OK")
    except Exception as e:
        print("LINE送信エラー:", e)

# ====== 価格取得（投資.com -> ダメならYahoo）======
def get_price() -> float:
    # --- まず Investing.com（HTML） ---
    inv_url = "https://jp.investing.com/indices/japan-225-futures"
    inv_headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # 429に配慮したリトライ（指数バックオフ + ジッター）
    for i in range(5):
        try:
            r = requests.get(inv_url, headers=inv_headers, timeout=15)
            if r.status_code == 429:
                wait = 60 * (i + 1) + random.randint(0, 15)
                print(f"429 Too Many Requests（Investing）→ {wait}s待機して再試行")
                time.sleep(wait)
                continue
            r.raise_for_status()
            # HTMLから現在価格を抜く（data-test="instrument-price-last" を使用）
            m = re.search(r'data-test="instrument-price-last"[^>]*>([^<]+)<', r.text)
            if m:
                price = float(m.group(1).replace(",", ""))
                print("Investingから取得:", price)
                return price
            else:
                raise ValueError("Investing: 価格が見つかりませんでした。")
        except Exception as e:
            wait = 5 * (i + 1) + random.randint(0, 5)
            print(f"Investing取得失敗: {e} → {wait}s待機して再試行")
            time.sleep(wait)

    # --- だめなら Yahoo Finance（JSON API） ---
    # 先物: NK=F / 現物指数: ^N225 どちらか取れた方を採用
    for symbol in ["NK=F", "^N225"]:
        try:
            y_url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
            r = requests.get(y_url, timeout=15)
            r.raise_for_status()
            data = r.json()
            quote = data["quoteResponse"]["result"]
            if quote:
                price = float(quote[0]["regularMarketPrice"])
                print(f"Yahoo({symbol})から取得:", price)
                return price
        except Exception as e:
            print(f"Yahoo({symbol})取得失敗:", e)

    raise RuntimeError("どのデータソースからも価格を取得できませんでした。")

# ====== 実行タスク ======
def task():
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        price = get_price()
        msg = f"[225bot1] {now}\n現在価格: {price:,.0f}"
        print(msg)
        send_line(msg)
    except Exception as e:
        err = f"[225bot1] {now}\n価格取得エラー: {e}"
        print(err)
        send_line(err)

# ====== エントリポイント（常時稼働・10分間隔）======
if __name__ == "__main__":
    # 起動直後の一斉アクセスを避けるためランダム待機
    first_wait = random.randint(30, 120)
    print(f"初回起動待機: {first_wait}s")
    time.sleep(first_wait)

    while True:
        task()
        # 次回実行まで10分待ち（必要に応じて変更可）
        sleep_s = 600 + random.randint(0, 60)  # 少しジッターを入れる
        print(f"次回まで待機: {sleep_s}s")
        time.sleep(sleep_s)