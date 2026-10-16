#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가상화폐 뉴스 수집 스크립트 (클라우드 루틴용).

1) 헤드라인 모드 (인자 없음)
   CoinDesk / Cointelegraph RSS 에서 최근 24시간 기사를 출처별 최대 10건씩 받아
   같은 폴더의 news.json 으로 저장하고, 번호 + 제목 + 요약문을 화면에 출력한다.

2) 본문 모드 (--body 번호 ...)
   헤드라인 모드가 만든 news.json 에서 고른 번호의 기사 페이지를 열어
   본문 앞부분(기사당 최대 BODY_MAX 자)을 화면에 출력한다.
   본문을 못 받은 기사는 요약문만 출력한다.

- 한 출처/기사가 실패해도 나머지로 진행한다. 전부 실패하면 종료코드 1.
- 외부 라이브러리 없이 표준 라이브러리만 사용한다.
- 시각은 KST(UTC+9)로 변환해 표기한다.
"""
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
]
HOURS = 24
PER_SOURCE = 10
BODY_MAX = 2500      # 기사당 본문 최대 글자 수
BODY_PICK_MAX = 5    # --body 로 한 번에 받을 최대 기사 수
MIN_PARAGRAPH = 40   # 이보다 짧은 문단은 버림 (메뉴·버튼 문구 등)
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")
TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (crypto-morning-briefing)"}
KST = timezone(timedelta(hours=9))

# 본문 끝에 붙는 기사 외 문단(광고·고지·관련기사)을 거르는 기준
SKIP_PREFIXES = ("Disclosure", "Related:", "Magazine:", "Read more", "Sign up")
SKIP_CONTAINS = (
    "is committed to providing independent",
    "full journalistic independence",
    "is an award-winning media outlet",
)


def clean_text(s):
    """HTML 태그·엔티티를 지우고 공백을 한 칸으로."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


# ---------------------------------------------------------------- 헤드라인 모드

def recent_items(root, source, now):
    items = []
    for it in root.findall("./channel/item"):
        title = clean_text(it.findtext("title"))
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        if not title or now - pub > timedelta(hours=HOURS):
            continue
        items.append({
            "source": source,
            "title": title,
            "summary": clean_text(it.findtext("description")),
            "link": (it.findtext("link") or "").strip(),
            "published_kst": pub.astimezone(KST).strftime("%m-%d %H:%M"),
            "_ts": pub.timestamp(),
        })
    items.sort(key=lambda x: x["_ts"], reverse=True)
    return items[:PER_SOURCE]


def run_headlines():
    now = datetime.now(timezone.utc)
    items, ok, failed = [], [], []
    for source, url in FEEDS:
        try:
            items += recent_items(ET.fromstring(http_get(url)), source, now)
            ok.append(source)
        except Exception as e:  # noqa
            failed.append(f"{source}: {e}")
            print("FAIL", source, e, file=sys.stderr)
    if not ok:
        sys.exit("모든 RSS 실패")

    items.sort(key=lambda x: x["_ts"], reverse=True)
    for i, x in enumerate(items, 1):
        del x["_ts"]
        x["id"] = i
    data = {
        "updated_at": now.isoformat(),
        "sources_ok": ok,
        "sources_failed": failed,
        "items": items,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

    for x in items:
        print(f"[{x['id']}] {x['published_kst']} KST | {x['source']} | {x['title']}")
        if x["summary"]:
            print(f"     요약: {x['summary']}")
    print(f"OK {len(items)}건 저장 (성공: {', '.join(ok)}) -> {OUT_PATH}")


# ---------------------------------------------------------------- 본문 모드

class ParagraphParser(HTMLParser):
    """<p> 안의 글자만 문단 단위로 모은다. script/style 안은 무시."""

    def __init__(self):
        super().__init__()
        self.paragraphs, self._buf = [], []
        self._in_p = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "p":
            self._in_p += 1
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "p" and self._in_p:
            self._in_p -= 1
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(text) >= MIN_PARAGRAPH:
                self.paragraphs.append(text)

    def handle_data(self, data):
        if self._in_p and not self._skip:
            self._buf.append(data)


def extract_body(page_html):
    p = ParagraphParser()
    p.feed(page_html)
    # 여러 번 반복되는 문단은 광고로 보고 전부 버림
    counts = {}
    for t in p.paragraphs:
        counts[t] = counts.get(t, 0) + 1
    out, total = [], 0
    for t in p.paragraphs:
        if counts[t] > 1 or t.startswith(SKIP_PREFIXES) or any(s in t for s in SKIP_CONTAINS):
            continue
        if total + len(t) > BODY_MAX:
            if not out:  # 첫 문단이 너무 길면 잘라서라도 넣음
                out.append(t[:BODY_MAX] + "…")
            break
        out.append(t)
        total += len(t)
    return "\n".join(out)


def run_body(ids):
    try:
        with open(OUT_PATH, encoding="utf-8") as fp:
            items = {x["id"]: x for x in json.load(fp)["items"]}
    except (OSError, ValueError, KeyError) as e:
        sys.exit(f"news.json 을 읽을 수 없음 (헤드라인 모드를 먼저 실행): {e}")

    ok = 0
    for i in ids[:BODY_PICK_MAX]:
        x = items.get(i)
        if not x:
            print(f"===== [{i}] 없는 번호", file=sys.stderr)
            continue
        print(f"===== [{i}] {x['source']} | {x['published_kst']} KST | {x['title']}")
        try:
            body = extract_body(http_get(x["link"]).decode("utf-8", "replace"))
        except Exception as e:  # noqa
            body = ""
            print(f"FAIL [{i}] {e}", file=sys.stderr)
        if body:
            print(body)
            ok += 1
        else:
            print(f"(본문 가져오기 실패, 요약문만 사용) {x['summary']}")
        print()
    if ids[BODY_PICK_MAX:]:
        print(f"(최대 {BODY_PICK_MAX}건까지만 처리, 나머지 무시)", file=sys.stderr)
    print(f"OK 본문 {ok}/{min(len(ids), BODY_PICK_MAX)}건")
    if ok == 0:
        sys.exit(1)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--body":
        try:
            ids = [int(a) for a in args[1:]]
        except ValueError:
            sys.exit("사용법: python3 fetch_news.py --body 번호 [번호 ...]")
        if not ids:
            sys.exit("사용법: python3 fetch_news.py --body 번호 [번호 ...]")
        run_body(ids)
    else:
        run_headlines()


if __name__ == "__main__":
    main()
