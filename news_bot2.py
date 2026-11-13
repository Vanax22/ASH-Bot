import requests, json, os, re, time, sys
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_2"]
LIST_URL = "https://forg.gg/forever/news"
ARTICLE_RE = re.compile(r"^https://forg\.gg/forever/news/[A-Za-z0-9]+$")
SEEN_FILE = "seen2.json"
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
    links = {}
    for a in soup.select('a[href*="/forever/news/"]'):
        href = a["href"]
        if href.startswith("/"):
            href = "https://forg.gg" + href
        if ARTICLE_RE.match(href) and href not in links:
            links[href] = a.get_text(strip=True)  # 링크 글자(제목)를 예비용으로 저장
    return links  # 최신 글이 앞에 옴

def get_meta(url, fallback_title):
    try:
        html = requests.get(url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return {"title": fallback_title or url, "description": "", "image": ""}
    def og(prop):
        tag = soup.find("meta", property=prop)
        return tag["content"] if tag and tag.get("content") else ""
    title = og("og:title").replace(" | ForG", "").strip()
    return {
        "title": title or fallback_title or url,
        "description": og("og:description"),
        "image": og("og:image"),
    }

def send(url, fallback_title):
    m = get_meta(url, fallback_title)
    embed = {
        "title": m["title"][:256],
        "url": url,
        "description": m["description"][:300],
        "footer": {"text": "ForG"},
    }
    payload = {"embeds": [embed]}
    for _ in range(3):
        r = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if r.status_code == 429:  # 속도 제한이면 잠깐 기다렸다 재시도
            time.sleep(r.json().get("retry_after", 2))
            continue
        if r.status_code >= 300:
            print("전송 실패:", r.status_code, r.text)
        return r.status_code < 300
    return False

def main():
    first_run = not os.path.exists(SEEN_FILE)
    seen = load_seen()
    links = get_article_links()
    new = [u for u in links if u not in seen]
    print(f"사이트에서 찾은 글 {len(links)}개 / 기록된 글 {len(seen)}개 / 새 글 {len(new)}개 / 첫 실행: {first_run}")
    if not links:
        print("글 링크를 찾지 못했습니다. 사이트 구조가 바뀌었을 수 있어요.")
        sys.exit(1)

    for url in reversed(list(links)):  # 오래된 글부터
        if url in seen:
            continue
        if first_run:
            seen.add(url)  # 첫 실행: 기존 글은 기록만 함
        elif send(url, links[url]):
            print("전송 성공:", url)
            seen.add(url)
            time.sleep(1.5)
        else:
            print("전송 실패로 건너뜀:", url)
    save_seen(seen)

main()
