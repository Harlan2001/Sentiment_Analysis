import requests
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import json
from vector_store import FaissStore

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cls.cn/"}
DETAIL_URL = "https://www.cls.cn/detail/{}"
LIST_PAGE = "https://www.cls.cn/depth?id=1032"

store = FaissStore()


def save_news(data, path="data/news.jsonl"):
    os.makedirs("data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def get_all_detail_ids():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")  # 可选，无头模式

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    driver.get(LIST_PAGE)
    time.sleep(5)

    ids = set()

    for _ in range(200):  # 加载更多次数，可调整
        links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/detail/']")
        for a in links:
            href = a.get_attribute("href")
            if href and "/detail/" in href:
                try:
                    ids.add(int(href.split("/")[-1]))
                except:
                    pass

        # 滚动触发加载
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        try:
            btn = driver.find_element(By.XPATH, "//div[contains(text(),'加载更多')]")
            btn.click()
            time.sleep(2)
        except:
            pass

    driver.quit()
    return list(ids)


def parse_detail(news_id):
    url = DETAIL_URL.format(news_id)
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 标题
    title_tag = soup.select_one("div.detail-title span")
    title = title_tag.text.strip() if title_tag else ""

    # 摘要
    summary_tag = soup.select_one("pre.detail-brief")
    summary = summary_tag.text.strip() if summary_tag else ""

    # 发布时间（支持两种形式）
    publish_time = ""

    info1 = soup.select_one("div.m-b-20.c-999")
    if info1:
        time_divs = info1.find_all("div", class_="f-l", recursive=False)
        if time_divs:
            publish_time = time_divs[0].text.strip()
    else:
        info2 = soup.select_one("div.detail-time div.f-l span")
        if info2:
            publish_time = info2.text.strip()

    # 正文 + 图片
    content_div = soup.select_one("div.detail-content")
    paragraphs, images = [], []

    if content_div:
        for p in content_div.find_all(["p", "h3"]):
            if p.name == "p":
                img = p.find("img")
                if img and img.get("src"):
                    images.append(img["src"])
                else:
                    text = p.text.strip()
                    if text:
                        paragraphs.append(text)
            else:
                paragraphs.append(p.text.strip())

    content = "\n".join(paragraphs)

    return {
        "id": news_id,
        "title": title,
        "summary": summary,
        "content": content,
        "images": images,
        "publish_time": publish_time,
        "source": "",  # 暂不需要
        "url": url,
    }


def crawl():
    # 用 FaissStore.id_set 代替 seen_ids
    seen_ids = store.id_set
    print(f"📦 已抓取 {len(seen_ids)} 条历史新闻")

    news_ids = get_all_detail_ids()
    print(f"📄 本次发现 {len(news_ids)} 条新闻")

    new_ids = [nid for nid in news_ids if nid not in seen_ids]
    print(f"🆕 新增 {len(new_ids)} 条新闻")

    results = []

    for news_id in new_ids:
        try:
            data = parse_detail(news_id)
            results.append(data)
            print(f"✅ {data['title']}")

            text = data["title"] + "\n" + data["content"]
            store.add(data["id"], text)
            time.sleep(1)

        except Exception as e:
            print(f"❌ {news_id} 失败：{e}")

    store.save()
    return results


if __name__ == "__main__":
    data = crawl()
    save_news(data)
    print(f"\n共抓取 {len(data)} 条新闻")
