import requests, json, os, time, sys
from bs4 import BeautifulSoup

FORUM_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")        # 포럼 채널용
TEXT_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_TEXT", "")    # 텍스트 채널용
LIST_URL = "https://wowf.io/ko/news"
SEEN_FILE = "seen.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (news-to-discord bot)"}

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)

def get_article_links():
    html = requests.get(LIST_URL, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select('a[href*="/ko/news/"]'):
        href = a["href"]
        if href.startswith("/"):
            href = "https://wowf.io" + href
        if href.rstrip("/") != LIST_URL and href not in links:
            links.append(href)
    return links  # 최신 글이 앞에 옴

def get_meta(url):
    html = requests.get(url, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")
    def og(prop):
        tag = soup.find("meta", property=prop)
        return tag["content"] if tag and tag.get("content") else ""
    return {
        "title": og("og:title") or url,
        "description": og("og:description"),
        "image": og("og:image"),
    }

def post(webhook, payload, label):
    for _ in range(3):
        r = requests.post(webhook, json=payload, timeout=15)
        if r.status_code == 429:  # 속도 제한이면 잠깐 기다렸다 재시도
            time.sleep(r.json().get("retry_after", 2))
            continue
        if r.status_code >= 300:
            print(f"[{label}] 전송 실패:", r.status_code, r.text)
        return r.status_code < 300
    return False

def send(url):
    m = get_meta(url)
    embed = {
        "title": m["title"][:256],
        "url": url,
        "description": m["description"][:300],
        "footer": {"text": "WOWF.IO"},
    }
    if m["image"]:
        embed["image"] = {"url": m["image"]}

    ok = False
    if FORUM_WEBHOOK:
        forum_payload = {"thread_name": m["title"][:100], "embeds": [embed]}
        if post(FORUM_WEBHOOK, forum_payload, "포럼"):
            print("[포럼] 전송 성공:", url)
            ok = True
    if TEXT_WEBHOOK:
        if post(TEXT_WEBHOOK, {"embeds": [embed]}, "텍스트"):
            print("[텍스트] 전송 성공:", url)
            ok = True
    return ok  # 한 곳이라도 성공하면 '보낸 글'로 기록

def main():
    first_run = not os.path.exists(SEEN_FILE)
    seen = load_seen()
    links = get_article_links()
    new = [u for u in links if u not in seen]
    print(f"사이트에서 찾은 글 {len(links)}개 / 기록된 글 {len(seen)}개 / 새 글 {len(new)}개 / 첫 실행: {first_run}")
    if not links:
        print("글 링크를 찾지 못했습니다. 사이트 구조가 바뀌었을 수 있어요.")
        sys.exit(1)

    for url in reversed(links):  # 오래된 글부터
        if url in seen:
            continue
        if first_run:
            seen.add(url)  # 첫 실행: 기존 글은 기록만 함
        elif send(url):
            seen.add(url)
            time.sleep(1.5)
        else:
            print("전송 실패로 건너뜀:", url)
    save_seen(seen)

main()
