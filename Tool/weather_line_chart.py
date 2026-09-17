# 天气预报折线图 —— 未来7天气温变化趋势
# API：Open-Meteo（免费、无需注册、无需Key）
import requests
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rc("font", family="Microsoft YaHei")

# 常用城市的经纬度
cities = {
    "北京": (39.90, 116.40), "上海": (31.23, 121.47),
    "广州": (23.13, 113.26), "深圳": (22.54, 114.06),
    "成都": (30.57, 104.07), "武汉": (30.59, 114.30),
    "杭州": (30.27, 120.15), "西安": (34.26, 108.94),
    "重庆": (29.56, 106.55), "长沙": (28.23, 112.94),
    "南宁": (22.82, 108.32),
}


def fetch_weather(lat, lon):
    """调用Open-Meteo API获取7天天气预报"""
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": "Asia/Shanghai",
    }
    data = requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()["daily"]

    # 打印预报
    for i in range(len(data["time"])):
        print(f"  {data['time'][i]}  最高 {data['temperature_2m_max'][i]}°C  最低 {data['temperature_2m_min'][i]}°C")
    return data


def draw_weather_chart(data, city):
    """绘制气温折线图"""
    dates = [d[5:] for d in data["time"]]
    max_temps = data["temperature_2m_max"]
    min_temps = data["temperature_2m_min"]

    plt.figure(figsize=(10, 5))

    # 最高温折线（红色）
    plt.plot(dates, max_temps, "o-", color="#e74c3c", label="最高温", linewidth=2, markersize=8)
    for i, temp in enumerate(max_temps):
        plt.text(i, temp + 0.5, f"{temp}°", ha="center", fontsize=9, color="#e74c3c")

    # 最低温折线（蓝色）
    plt.plot(dates, min_temps, "o-", color="#3498db", label="最低温", linewidth=2, markersize=8)
    for i, temp in enumerate(min_temps):
        plt.text(i, temp - 1.2, f"{temp}°", ha="center", fontsize=9, color="#3498db")

    # 温差填充
    plt.fill_between(dates, max_temps, min_temps, alpha=0.15, color="#9b59b6")

    plt.title(f"{city} 未来7天气温变化趋势", fontsize=14, fontweight="bold")
    plt.xlabel("日期")
    plt.ylabel("温度（°C）")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    filename = f"{city}_天气预报.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"\n图表已保存至：{filename}")
    plt.show()


if __name__ == "__main__":
    print("可查询的城市：", "、".join(cities.keys()))
    print("也可以直接输入经纬度，格式：纬度,经度（如 39.90,116.40）")
    user_input = input("请输入城市名称或经纬度：")

    if "," in user_input:
        parts = user_input.split(",")
        lat, lon = float(parts[0]), float(parts[1])
        city = f"({lat},{lon})"
    elif user_input in cities:
        lat, lon = cities[user_input]
        city = user_input
    else:
        print("输入无效！请输入城市名或经纬度。")
        exit()

    print(f"\n{city} 未来7天天气预报：")
    data = fetch_weather(lat, lon)
    draw_weather_chart(data, city)