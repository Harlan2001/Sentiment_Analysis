import requests
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time


HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cls.cn/"}

DETAIL_URL = "https://www.cls.cn/detail/{}"
LIST_API = "https://www.cls.cn/v3/depth/home/assembled/1032"


def get_all_detail_ids():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )

    driver.get("https://www.cls.cn/depth?id=1032")
    time.sleep(5)

    ids = set()

    for _ in range(20):  # 加载更多次数，可自行调
        links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/detail/']")
        for a in links:
            href = a.get_attribute("href")
            if href and "/detail/" in href:
                ids.add(int(href.split("/")[-1]))

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


def get_news_list_html():
    url = "https://www.cls.cn/depth?id=1032"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    news = []
    for a in soup.select("a[href^='/detail/']"):
        href = a.get("href")
        if href:
            try:
                news_id = int(href.split("/")[-1])
                news.append(news_id)
            except:
                pass

    # 去重
    return list(set(news))


def parse_detail(news_id):
    """
    解析详情页
    """
    url = DETAIL_URL.format(news_id)
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # 标题
    title = soup.select_one("div.detail-title span")
    title = title.text.strip() if title else ""

    # 摘要
    summary = soup.select_one("pre.detail-brief")
    summary = summary.text.strip() if summary else ""

    # 发布时间 & 来源
    info = soup.select_one("div.c-999")
    publish_time, source = "", ""
    if info:
        spans = info.select("div.f-l")
        if len(spans) >= 2:
            publish_time = spans[1].text.strip()
        if len(spans) >= 3:
            source = spans[2].text.strip()

    # 正文 + 图片
    content_div = soup.select_one("div.detail-content")
    paragraphs = []
    images = []

    if content_div:
        for p in content_div.find_all(["p", "h3"]):
            if p.name == "p":
                img = p.find("img")
                if img:
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
        "source": source,
        "url": url,
    }


def crawl():
    news_ids = get_all_detail_ids()
    print(f"📄 共发现 {len(news_ids)} 条新闻")

    results = []
    for news_id in news_ids:
        try:
            data = parse_detail(news_id)
            results.append(data)
            print(f"✅ {data['title']}")
            time.sleep(1)
        except Exception as e:
            print(f"❌ {news_id} 失败：{e}")

    return results


if __name__ == "__main__":
    data = crawl()
    print(f"\n共抓取 {len(data)} 条新闻")
