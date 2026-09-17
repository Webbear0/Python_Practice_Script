# B站热搜词云可视化工具
import requests
from wordcloud import WordCloud
from datetime import datetime
# 1. 获取B站热搜数据
url = "https://api.bilibili.com/x/web-interface/search/square"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, params={"limit": 50}, headers=headers)
data = response.json()
# 2. 提取热搜关键词和热度值，构建词频字典
trending = data["data"]["trending"]["list"]
word_freq = {}
for item in trending:
    word_freq[item["show_name"]] = item["heat_score"]
# 3. 生成词云并保存为图片
wc = WordCloud(font_path="msyh.ttc", width=1280, height=720, background_color="white")
wc.generate_from_frequencies(word_freq)

filename = f"{datetime.now().strftime('%Y-%m-%d')}.png"
wc.to_file(filename)
print(f"词云已保存至：{filename}")