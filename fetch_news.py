#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가상화폐 뉴스 헤드라인 수집 스크립트 (클라우드 루틴용).
CoinDesk / Cointelegraph RSS 에서 최근 24시간 기사 제목을 출처별 최대 10건씩 받아
같은 폴더의 news.json 으로 저장하고, 화면에도 한 줄씩 출력한다.

- 한 출처가 실패해도 나머지 출처로 진행한다. 모두 실패하면 종료코드 1.
- 외부 라이브러리 없이 표준 라이브러리만 사용한다.
- 시각은 KST(UTC+9)로 변환해 표기한다.
"""
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
]
HOURS = 24
PER_SOURCE = 10
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")
TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (crypto-morning-briefing)"}
KST = timezone(timedelta(hours=9))


def fetch_feed(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return ET.fromstring(r.read())


def recent_items(root, source, now):
    items = []
    for it in root.findall("./channel/item"):
        title = (it.findtext("title") or "").strip()
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        if not title or now - pub > timedelta(hours=HOURS):
            continue
        items.append({
            "source": source,
            "title": title,
            "link": (it.findtext("link") or "").strip(),
            "published_kst": pub.astimezone(KST).strftime("%m-%d %H:%M"),
            "_ts": pub.timestamp(),
        })
    items.sort(key=lambda x: x["_ts"], reverse=True)
    return items[:PER_SOURCE]


def main():
    now = datetime.now(timezone.utc)
    items, ok, failed = [], [], []
    for source, url in FEEDS:
        try:
            items += recent_items(fetch_feed(url), source, now)
            ok.append(source)
        except Exception as e:  # noqa
            failed.append(f"{source}: {e}")
            print("FAIL", source, e, file=sys.stderr)
    if not ok:
        sys.exit("모든 RSS 실패")

    items.sort(key=lambda x: x["_ts"], reverse=True)
    for x in items:
        del x["_ts"]
    data = {
        "updated_at": now.isoformat(),
        "sources_ok": ok,
        "sources_failed": failed,
        "items": items,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

    for x in items:
        print(f"{x['published_kst']} KST | {x['source']} | {x['title']}")
    print(f"OK {len(items)}건 저장 (성공: {', '.join(ok)}) -> {OUT_PATH}")


if __name__ == "__main__":
    main()
