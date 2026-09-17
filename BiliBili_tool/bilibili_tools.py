# B站数据查询工具集
# 功能：查询视频信息、用户信息
import requests
headers = {"User-Agent": "Mozilla/5.0"}

def get_video_info():
    """查询B站视频信息"""
    bvid = input("请输入BV号：")
    url = "https://api.bilibili.com/x/web-interface/view"
    data = requests.get(url, params={"bvid": bvid}, headers=headers).json()
    info = data["data"]
    stat = info["stat"]
    print(f"\n标题：{info['title']}")
    print(f"UP主：{info['owner']['name']}")
    print(f"播放量：{stat['view']}")
    print(f"点赞：{stat['like']}")
    print(f"投币：{stat['coin']}")
    print(f"收藏：{stat['favorite']}")
    print(f"弹幕：{stat['danmaku']}")

def get_user_info():
    """查询B站用户信息并获取评论"""
    uid = input("请输入B站UID：")
    # 第一部分：获取用户基本信息
    url = "https://api.bilibili.com/x/web-interface/card"
    data = requests.get(url, params={"mid": uid}, headers=headers).json()
    card = data["data"]["card"]
    print(f"\n昵称：{card['name']}")
    print(f"性别：{card['sex']}")
    print(f"等级：LV{card['level_info']['current_level']}")
    print(f"签名：{card['sign']}")
    print(f"粉丝数：{card['fans']}")
    print(f"关注数：{card['attention']}")

    # 第二部分：获取用户评论并保存
    print("\n正在获取评论...")
    reply_url = f"https://api.aicu.cc/api/v3/search/getreply?uid={uid}&pn=1&ps=500&mode=0"
    reply_data = requests.get(reply_url).json()
    replies = reply_data["data"]["replies"]
    total = reply_data["data"]["cursor"]["all_count"]
    print(f"共获取 {len(replies)} 条评论（总计 {total} 条）")

    filename = f"{card['name']}_评论.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for reply in replies:
            f.write(f"{reply['message']}\n")
            f.write("-" * 100 + "\n")
    print(f"已保存到：{filename}")

# ========== 主菜单 ==========
if __name__ == "__main__":
    print("=" * 40)
    print("      B站数据查询工具集")
    print("=" * 40)
    print("1. 查询视频信息")
    print("2. 查询用户信息")
    print("=" * 40)

    choice = input("请选择功能（1/2），输入0退出程序：")
    if choice == "1":
        get_video_info()
    elif choice == "2":
        get_user_info()
    elif choice == "0":
        exit()
    else:
        print("无效选择！")
