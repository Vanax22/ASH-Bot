import requests, json, os, time, sys
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]
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
    for _ in range(3):
        r = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        if r.status_code == 429:  # 속도 제한이면 잠깐 기다렸다 재시도
            time.sleep(r.json().get("retry_after", 2))
            continue
        return r.status_code < 300
    return False

def main():
    first_run = not os.path.exists(SEEN_FILE)
    seen = load_seen()
    links = get_article_links()
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
    save_seen(seen)

main()
