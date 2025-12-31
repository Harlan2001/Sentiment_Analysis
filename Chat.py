import ollama


def analyze_news(news_text: str):
    prompt = f"""
你是一个宏观经济分析助手。

请分析下面这条新闻对经济的影响，并按以下格式输出：

【总体判断】：利多 / 利空 / 中性  
【影响领域】：（股市 / 债券 / 汇率 / 大宗商品 / 宏观）
【简要原因】：不超过 3 条要点
【时间维度】：短期 / 中期 / 长期

新闻内容：
{news_text}
"""

    response = ollama.chat(
        model="qwen3:4b", messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"]


if __name__ == "__main__":
    news = "美国12月CPI同比增长3.4%，高于市场预期，美联储官员表示短期内不急于降息。"
    result = analyze_news(news)
    print(result)
