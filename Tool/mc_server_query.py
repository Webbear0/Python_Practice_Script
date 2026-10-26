# 我的世界服务器状态查询与IP定位工具
# 知识点：requests调用API、JSON解析、自定义函数、多API组合
import requests

def query_mc_server(address):
    """查询MC服务器状态，返回服务器IP"""
    print(f"\n正在查询 {address} ...")
    mc_data = requests.get(f"https://api.mcsrvstat.us/2/{address}").json()

    if mc_data.get("online"):
        print("\n" + "=" * 50)
        print(f"  MC 服务器状态")
        print("=" * 50)
        print(f"  地址：{address}")
        print(f"  IP：{mc_data['ip']}:{mc_data['port']}")
        print(f"  版本：{mc_data.get('version', '未知')}")
        print(f"  在线：{mc_data['players']['online']} / {mc_data['players']['max']}")
        print(f"  简介：{chr(10).join(mc_data['motd']['clean'])}")
        return mc_data["ip"]
    else:
        print(f"\n  {address} 不是MC服务器或已离线，尝试直接定位...")
        return mc_data.get("ip", address)

def locate_ip(ip):
    """通过IP地址查询地理位置"""
    print("\n正在定位 IP 位置...")
    ip_data = requests.get(f"http://ip-api.com/json/{ip}").json()

    if ip_data["status"] == "success":
        print("\n" + "-" * 50)
        print(f"  IP 定位结果")
        print("-" * 50)
        print(f"  IP：{ip_data['query']}")
        print(f"  国家：{ip_data['country']}")
        print(f"  地区：{ip_data['regionName']}")
        print(f"  城市：{ip_data['city']}")
        print(f"  经纬度：{ip_data['lat']}, {ip_data['lon']}")
        print(f"  运营商：{ip_data['isp']}")
        print(f"  时区：{ip_data['timezone']}")
    else:
        print("  IP 定位失败")
    print("\n" + "=" * 50)


if __name__ == "__main__":
    print("常用MC服务器：mc.hypixel.net / 2b2t.org")
    print("也可以输入任意域名或IP地址进行定位")
    address = input("请输入地址：")
    ip = query_mc_server(address)
    locate_ip(ip)