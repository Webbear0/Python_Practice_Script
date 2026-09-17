# B站分区排行榜数据可视化
import requests
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rc("font", family="Microsoft YaHei")

# 分区名称与编号
zones = {
    "动画": 1, "音乐": 3, "游戏": 4, "娱乐": 5,
    "科技": 188, "生活": 160, "鬼畜": 119, "舞蹈": 129,
    "影视": 181, "知识": 36, "美食": 211, "动物圈": 217,
}


def fetch_ranking(zone_name):
    """获取指定分区的排行榜数据"""
    url = "https://api.bilibili.com/x/web-interface/ranking/region"
    headers = {"User-Agent": "Mozilla/5.0"}
    data = requests.get(url, params={"rid": zones[zone_name], "day": 3}, headers=headers).json()["data"]

    for i, v in enumerate(data, 1):
        print(f"  {i}. {v['title']}（{v['play']}播放）")
    return data


def draw_ranking_chart(data, zone_name):
    """绘制排行榜柱状图和饼图"""
    titles = [v["title"][:10] for v in data]
    plays = [round(v["play"] / 10000, 1) for v in data]

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # 左图：水平柱状图
    axes[0].barh(titles[::-1], plays[::-1], color=plt.cm.viridis([i / len(titles) for i in range(len(titles))]))
    axes[0].set_xlabel("播放量（万）")
    axes[0].set_title(f"B站【{zone_name}区】排行榜 - 播放量")

    # 右图：饼图
    wedges, _, autotexts = axes[1].pie(
        plays, autopct="%1.1f%%", startangle=90, pctdistance=0.75,
        colors=plt.cm.Set3([i / len(titles) for i in range(len(titles))]))
    axes[1].legend(wedges, titles, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9)
    axes[1].set_title(f"B站【{zone_name}区】排行榜 - 播放量占比")

    plt.tight_layout()
    plt.savefig(f"bilibili_{zone_name}_ranking.png", dpi=150, bbox_inches="tight")
    print(f"图表已保存至：bilibili_{zone_name}_ranking.png")
    plt.show()


if __name__ == "__main__":
    print("可选分区：", "、".join(zones.keys()))
    name = input("请输入分区名称：")
    if name not in zones:
        print("错误：分区不存在！")
        exit()

    data = fetch_ranking(name)
    draw_ranking_chart(data, name)