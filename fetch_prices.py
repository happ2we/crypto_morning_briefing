#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가상화폐 가격 수집 스크립트 (GitHub Actions 러너용).
10종 USDT 페어의 현재가/24h 등락률/24h 거래대금을 받아 prices.json 으로 저장한다.

- api.binance.com 은 GitHub 러너에서 HTTP 451(지역 제한)이므로 사용하지 않고,
  시세 전용 주소 data-api.binance.vision 을 1순위로 쓴다.
- 실패 시 okx -> bybit 순으로 폴백한다.
- 외부 라이브러리 없이 표준 라이브러리(urllib)만 사용한다.
  출력 형식은 로컬용 fetch_prices.py(ccxt)와 동일: symbol / last / pct / qv
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SYMBOLS = ["BTC", "ETH", "XRP", "SOL", "BNB", "DOGE", "ADA", "TRX", "AVAX", "LINK"]
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.json")
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (crypto-morning-briefing)"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def f(x):
    return float(x) if x not in (None, "") else None


def from_binance():
    syms = json.dumps([s + "USDT" for s in SYMBOLS], separators=(",", ":"))
    url = ("https://data-api.binance.vision/api/v3/ticker/24hr?symbols="
           + urllib.parse.quote(syms))
    out = {}
    for d in get_json(url):
        out[d["symbol"][:-4]] = {
            "last": f(d["lastPrice"]),
            "pct": f(d["priceChangePercent"]),   # 이미 % 단위
            "qv": f(d["quoteVolume"]),
        }
    return out


def from_bybit():
    data = get_json("https://api.bybit.com/v5/market/tickers?category=spot")
    out = {}
    for d in data["result"]["list"]:
        s = d["symbol"]
        if s.endswith("USDT") and s[:-4] in SYMBOLS:
            out[s[:-4]] = {
                "last": f(d["lastPrice"]),
                "pct": f(d["price24hPcnt"]) * 100 if d.get("price24hPcnt") else None,  # 비율 -> %
                "qv": f(d["turnover24h"]),
            }
    return out


def from_okx():
    data = get_json("https://www.okx.com/api/v5/market/tickers?instType=SPOT")
    out = {}
    for d in data["data"]:
        inst = d["instId"]
        if inst.endswith("-USDT") and inst[:-5] in SYMBOLS:
            last, open24 = f(d["last"]), f(d["open24h"])
            out[inst[:-5]] = {
                "last": last,
                "pct": (last / open24 - 1) * 100 if last and open24 else None,
                "qv": f(d["volCcy24h"]),
            }
    return out


SOURCES = [("binance", from_binance), ("okx", from_okx), ("bybit", from_bybit)]


def fetch():
    last_err = None
    for name, fn in SOURCES:
        try:
            res = fn()
            coins = [{"symbol": s, **res[s]} for s in SYMBOLS if s in res]
            if len(coins) >= 8:
                return {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "source": name,
                    "coins": coins,
                }
            last_err = f"{name}: 코인 {len(coins)}종만 수신"
        except Exception as e:  # noqa
            last_err = f"{name}: {e}"
        print("FAIL", last_err, file=sys.stderr)
    raise RuntimeError(f"모든 거래소 실패: {last_err}")


def main():
    data = fetch()
    with open(OUT_PATH, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    print(f"OK {len(data['coins'])}종 저장 ({data['source']}) -> {OUT_PATH}")


if __name__ == "__main__":
    main()
