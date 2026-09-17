# B站热门视频发布时段分析
import requests
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime
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


def analyze_publish_hours(videos):
    """统计发布时段并绘制柱状图+饼图"""
    # 统计每小时发布数量
    hours = [0] * 24
    for v in videos:
        hours[datetime.fromtimestamp(v["ctime"]).hour] += 1

    # 绘图
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # 左图：24小时柱状图
    colors = ["#e74c3c" if hours[h] == max(hours) else "#3498db" for h in range(24)]
    axes[0].bar(range(24), hours, color=colors, edgecolor="white")
    axes[0].set_xlabel("发布时间（小时）")
    axes[0].set_ylabel("视频数量")
    axes[0].set_title("B站热门视频发布时段分布")
    axes[0].set_xticks(range(24))
    axes[0].set_xticklabels([f"{h}:00" for h in range(24)], rotation=45, fontsize=8)
    axes[0].grid(axis="y", alpha=0.3)

    # 右图：四个时段占比饼图
    periods = {"深夜(0-6点)": sum(hours[0:6]), "上午(6-12点)": sum(hours[6:12]),
               "下午(12-18点)": sum(hours[12:18]), "晚上(18-24点)": sum(hours[18:24])}
    axes[1].pie(periods.values(), labels=periods.keys(), autopct="%1.1f%%",
                colors=["#2c3e50", "#f39c12", "#27ae60", "#8e44ad"], startangle=90)
    axes[1].set_title("发布时段占比")

    peak = max(range(24), key=lambda h: hours[h])
    plt.suptitle(f"UP主最爱 {peak}:00 发视频！", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig("bilibili_publish_hours.png", dpi=150, bbox_inches="tight")
    print(f"共{len(videos)}个视频，图表已保存至：bilibili_publish_hours.png")
    plt.show()


if __name__ == "__main__":
    pages = input("请输入获取页数（每页50个，默认2）：") or "2"
    videos = fetch_popular(int(pages))
    analyze_publish_hours(videos)
