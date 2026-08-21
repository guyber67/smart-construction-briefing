#!/usr/bin/env python3
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data" / "briefings.json"
KST = ZoneInfo("Asia/Seoul")

now = datetime.now(KST)
today = now.date().isoformat()
window_start = now - timedelta(hours=24)

if not DATA_FILE.exists():
    raise SystemExit(f"Missing {DATA_FILE}")

existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
if not isinstance(existing, list):
    raise SystemExit("data/briefings.json must be a JSON array")

prompt = f"""
현재 시각은 {now.strftime('%Y-%m-%d %H:%M KST')}이다.
검색 대상 시간창은 {window_start.strftime('%Y-%m-%d %H:%M KST')}부터
{now.strftime('%Y-%m-%d %H:%M KST')}까지의 최근 24시간이다.

스마트건설, 건설 AI, 건설 AX, 건설 DX, Smart Construction 관련 국내외 뉴스를
웹 검색으로 조사해 한국어 데일리 브리핑을 작성하라.

선별 원칙:
1. 최초 공개일·보도일이 최근 24시간 안에 있는 이슈를 우선한다.
2. 분야별 최대 3개. 같은 뉴스는 가장 관련성이 높은 한 분야에만 배치한다.
3. 광고성/기업 홍보성 보도는 sourceType에 명확히 표시한다.
4. 확인할 만한 신규 이슈가 없는 분야는 news에 억지로 넣지 말고 emptyCategories에
   "주요 신규 이슈 없음" 취지로 기록한다.
5. 원문 URL은 실제 확인한 링크만 기록한다.
6. 건설산업 시사점은 단순 요약이 아니라 생산성, 안전, 공정, 원가, 데이터,
   Digital Twin, Agentic AI, Physical AI 관점에서 분석한다.
7. 사실과 분석을 구분하고, 과장된 "세계 최초" 표현은 공식 근거가 있을 때만 쓴다.

반드시 아래 JSON 객체 하나만 출력하라. Markdown 코드펜스는 쓰지 마라.

필수 구조:
{{
  "date": "{today}",
  "displayDate": "YYYY년 M월 D일 · 요일 · 06:00 KST",
  "headline": "핵심 변화 한 문장. 강조할 구절은 <strong>...</strong> 사용 가능",
  "executiveSummary": ["문장1", "문장2", "문장3"],
  "signals": [
    {{"label":"TODAY'S FOCUS","value":"짧은 키워드","focus":true}},
    {{"label":"AI/AX SIGNAL","value":"짧은 키워드"}},
    {{"label":"DATA LAYER","value":"짧은 키워드"}},
    {{"label":"MARKET MOVE","value":"짧은 키워드"}}
  ],
  "news": [
    {{
      "id": "YYYYMMDD-영문슬러그",
      "category": "스마트건설|건설AI|건설AX|건설DX|Smart Construction 중 하나",
      "importance": 1,
      "featured": false,
      "title": "제목",
      "summary": "핵심 내용 2~3문장",
      "insight": "건설산업 시사점",
      "whyItMatters": "왜 중요한지 1문장",
      "recommendedAction": "권고 행동 1문장",
      "source": "출처",
      "sourceType": "공식 발표|언론 보도|전문가 기고|연구기관|글로벌 뉴스 등",
      "published": "YYYY-MM-DD 또는 YYYY-MM-DD HH:MM",
      "region": "국내/해외 · 짧은 설명",
      "url": "https://...",
      "linkStatus": "verified",
      "checkedAt": "{today}"
    }}
  ],
  "emptyCategories": {{
    "필요한 분야명": "최근 24시간 내 주요 신규 이슈 없음에 대한 설명"
  }},
  "implications": [
    {{"title":"시사점 1 제목","body":"설명"}},
    {{"title":"시사점 2 제목","body":"설명"}},
    {{"title":"시사점 3 제목","body":"설명"}}
  ],
  "closing": "오늘의 한 줄. 강조할 구절은 <span>...</span> 사용 가능"
}}

importance는 1~5 정수이며 가장 중요한 이슈만 featured=true로 한다.
news가 없는 분야는 다음 5개 범주 중 누락된 범주를 emptyCategories에 기록한다:
스마트건설, 건설AI, 건설AX, 건설DX, Smart Construction.
"""

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6",
    tools=[{"type": "web_search"}],
    reasoning={"effort": "medium"},
    input=prompt,
)

text = response.output_text.strip()
text = re.sub(r"^```(?:json)?\s*", "", text)
text = re.sub(r"\s*```$", "", text)
briefing = json.loads(text)

required_top = {
    "date", "displayDate", "headline", "executiveSummary", "signals",
    "news", "emptyCategories", "implications", "closing"
}
missing = sorted(required_top - set(briefing))
if missing:
    raise SystemExit(f"Model output missing fields: {missing}")

if briefing["date"] != today:
    briefing["date"] = today

if len(briefing.get("executiveSummary", [])) != 3:
    raise SystemExit("executiveSummary must contain exactly 3 items")
if len(briefing.get("implications", [])) != 3:
    raise SystemExit("implications must contain exactly 3 items")

valid_categories = {"스마트건설", "건설AI", "건설AX", "건설DX", "Smart Construction"}
seen_ids = set()
category_counts = {k: 0 for k in valid_categories}

for item in briefing["news"]:
    cat = item.get("category")
    if cat not in valid_categories:
        raise SystemExit(f"Invalid category: {cat}")
    category_counts[cat] += 1
    if category_counts[cat] > 3:
        raise SystemExit(f"Too many items in category: {cat}")

    item_id = item.get("id")
    if not item_id or item_id in seen_ids:
        raise SystemExit(f"Missing or duplicate news id: {item_id}")
    seen_ids.add(item_id)

    importance = item.get("importance")
    if not isinstance(importance, int) or not (1 <= importance <= 5):
        raise SystemExit(f"Invalid importance for {item_id}")

    url = item.get("url", "")
    if url and not url.startswith(("http://", "https://")):
        raise SystemExit(f"Invalid URL for {item_id}: {url}")

# Ensure every category without a news item is represented in emptyCategories.
for cat, count in category_counts.items():
    if count == 0 and cat not in briefing["emptyCategories"]:
        briefing["emptyCategories"][cat] = "주요 신규 이슈 없음"

# Replace today's entry if rerun; otherwise prepend.
updated = [x for x in existing if x.get("date") != today]
updated.insert(0, briefing)

DATA_FILE.write_text(
    json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"Updated {DATA_FILE}")
print(f"Date: {today}")
print(f"News items: {len(briefing['news'])}")
