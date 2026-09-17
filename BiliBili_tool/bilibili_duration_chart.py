# B站热门视频时长分析
import requests
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rc("font", family="Microsoft YaHei")


def fetch_popular(pages=2):
    """获取B站热门视频列表"""
    url = "https://api.bilibili.com/x/web-interface/popular"
    headers = {"User-Agent": "Mozilla/5.0"}
    videos = []
    for page in range(1, pages + 1):
        data = requests.get(url, params={"pn": page, "ps": 50}, headers=headers).json()
        videos += data["data"]["list"]
    print(f"获取到 {len(videos)} 个热门视频")
    return videos


def analyze_duration(videos):
    """统计视频时长分布并绘制饼图"""
    groups = {"3分钟以内": 0, "3-10分钟": 0, "10-30分钟": 0, "30分钟以上": 0}
    for v in videos:
        m = v["duration"] / 60
        if m < 3:      groups["3分钟以内"] += 1
        elif m < 10:   groups["3-10分钟"] += 1
        elif m < 30:   groups["10-30分钟"] += 1
        else:          groups["30分钟以上"] += 1

    for label, count in groups.items():
        print(f"  {label}：{count} 个")

    # 绘制饼图
    colors = ["#e74c3c", "#f39c12", "#27ae60", "#3498db"]
    plt.figure(figsize=(8, 6))
    plt.pie(groups.values(), labels=groups.keys(), autopct="%1.1f%%",
            colors=colors, startangle=90, explode=[0.05] * 4)
    plt.title(f"B站热门视频时长分布（Top {len(videos)}）", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig("bilibili_duration.png", dpi=150, bbox_inches="tight")
    print(f"图表已保存至：bilibili_duration.png")
    plt.show()


if __name__ == "__main__":
    pages = input("请输入获取页数（每页50个，默认2）：") or "2"
    videos = fetch_popular(int(pages))
    analyze_duration(videos)