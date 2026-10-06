# 크립토 모닝 브리핑 — 클라우드 루틴 프롬프트 (초안)

> 기존 "Morning brief Weekday"(Claude for Windows '예약됨')를 Claude Code 클라우드 루틴용으로 옮긴 버전.
> 아래 `---` 사이가 루틴에 등록할 프롬프트 본문이다.

---

매일 오전 7시(KST) 실행되는 가상화폐 아침 브리핑 겸 라이브 대시보드 작업. 사용자(Jun)는 한국 거주·한국어 사용, ccxt/talib 기반 자동매매에 관심 있음. 모든 결과는 한국어로. 투자 권유·매매 추천은 하지 말고 사실 정보 위주로 중립적으로 작성. 모든 시각은 KST(UTC+9)로 변환해 표기.

이 작업은 클라우드 컨테이너에서 실행된다. PC 파일·Chrome·Gemini는 쓸 수 없으니 시도하지 마. 저장소에 커밋·푸시·PR 생성은 하지 마(읽기·실행만). 토큰 절약을 위해 큰 파일이나 웹페이지 전체를 읽지 말고, 아래 스크립트 출력만 사용해.

먼저 `TZ=Asia/Seoul date` 로 오늘 날짜·요일을 확인해(가상화폐는 24시간 시장이라 매일 동일 구성).

━━━━━━━━━━━━━━━━━━━━
【0단계】 저장소 준비

작업 디렉터리에 `happ2we/crypto_morning_briefing` 저장소가 있는지 확인. `fetch_prices.py`·`fetch_news.py` 가 없으면 `git fetch origin claude/zealous-bell-c66vdg && git checkout claude/zealous-bell-c66vdg` 로 받아. (main 에 합쳐진 뒤에는 main 그대로 사용.)

━━━━━━━━━━━━━━━━━━━━
【1단계】 코인 10종 가격 — `python3 fetch_prices.py`

실행 후 `prices.json` 을 읽어. 구조: updated_at(UTC ISO), source(binance/okx/bybit), coins[](각 symbol/last/pct/qv).
- 스크립트가 binance(data-api.binance.vision) → okx → bybit 순으로 자동 폴백한다. 직접 다른 방법을 시도하지 마.
- 출처 표기: "거래소 API (거래소명, MM-DD HH:MM KST 수집)" (updated_at 을 KST로 변환).
- qv 는 USDT 기준 24h 거래대금. source 가 binance 가 아니면 "거래소가 달라 거래대금 규모가 평소와 다를 수 있음"을 대시보드에 작게 표기.
- 스크립트가 실패하면(종료코드 ≠ 0) 시세는 "조회 실패"로 표시하고 다음 단계 진행.

대상 10종: BTC, ETH, XRP, SOL, BNB, DOGE, ADA, TRX, AVAX, LINK (USDT 페어).

━━━━━━━━━━━━━━━━━━━━
【2단계】 시장 심리 + 뉴스

■ 2-A. 공포·탐욕 지수 — `curl -sS https://api.alternative.me/fng/`
응답의 data[0].value(수치), value_classification(Extreme Fear/Fear/Neutral/Greed/Extreme Greed → 극단적 공포/공포/중립/탐욕/극단적 탐욕), timestamp(UNIX 초)를 사용. timestamp 는 KST(+9시간)로 변환해 "기준일 MM-DD HH:MM KST"로 표기하고, 출처를 "alternative.me API"로 명시. 실패하면 "조회 실패"(다른 사이트 값으로 대체하지 말 것).

■ 2-B. 뉴스 헤드라인 — `python3 fetch_news.py`
출력은 `MM-DD HH:MM KST | 출처 | 영어 제목` 형식의 최근 24시간 헤드라인(최대 20줄). 이 출력만 사용하고 기사 링크를 열거나 웹 검색하지 마.
- 시장 영향이 큰 것 위주로 3~5개를 골라, 각각 한국어 한 줄 요약 + 출처(CoinDesk/Cointelegraph) + 게시 시각(KST)을 붙여.
- 요약은 제목만 보고 쓴 것이므로 제목에 없는 수치·사실을 지어내지 마. 뉴스 섹션에 "제목 기반 요약"이라고 표기.
- 스크립트가 실패하면(종료코드 ≠ 0) 뉴스는 "조회 실패"로 표시.

■ 2-C. BTC 시장 분위기 2~3문장
1단계 BTC 시세(pct 부호·크기)와 2-B 헤드라인만 근거로 사실 위주로 작성. 시세와 모순되는 서술 금지.

━━━━━━━━━━━━━━━━━━━━
【3단계】 라이브 대시보드 아티팩트 갱신

'크립토 모닝 대시보드'(https://claude.ai/artifact/SR8g4yEasbowaiK5bnP7v1)를 Artifact 도구 action:read 로 읽은 뒤 그 url로 publish해 갱신. 읽기/갱신이 거부되면 새로 생성하고 새 URL을 브리핑에 적어. 이번 실행 수집값을 HTML에 직접 넣어(아침 스냅샷). 구성:
- 헤더: 날짜(KST) + 시세 출처 배지 + 공포탐욕 출처
- 공포·탐욕 지수: 수치 + 라벨 + 게이지(0~100) + 출처(alternative.me)와 기준일(KST). 실패 시 "조회 실패"
- BTC 강조 카드: 현재가·24h 등락률(상승 초록/하락 빨강) + 2-C 분위기 문장
- 코인 10종 표: 코인·현재가(USDT)·24h 등락률(초록/빨강)·거래대금(없으면 "—")
- 뉴스 섹션: 헤드라인 3~5개 + 한국어 한 줄 요약 + 출처 + 게시 시각(KST) + "제목 기반 요약" 표기
- 등락률은 pct 값 그대로(소수 둘째자리), 부호·색상 정확히. localStorage 등 브라우저 저장소 금지.

━━━━━━━━━━━━━━━━━━━━
【4단계】 브리핑 — 3~5줄 한국어 요약

비트코인 등락 흐름 / 가장 크게 오른·내린 코인(10종 pct 기준) / 공포·탐욕 지수(출처·기준일 KST 포함) / 주목 뉴스 1~2개. 마지막 줄에 데이터 출처(시세 거래소명, 뉴스 RSS)와 대시보드 링크. 실패한 항목이 있으면 무엇이 실패했는지 한 줄로. 투자 권유 없이 사실 위주로. PushNotification 도구가 있으면 이 요약을 푸시로 보내고, 없으면 최종 응답으로 남겨.

---
