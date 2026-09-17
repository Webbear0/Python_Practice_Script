# ============================================================
# 12306 火车票查询工具
# 功能：通过 12306 API 查询火车余票信息，并格式化展示
# 需要安装：pip install requests prettytable
# ============================================================

# -------------------- 导入所需模块 --------------------
import re                            # 内置库，正则表达式
import json                          # 内置库，JSON 解析
import ssl                           # 内置库，SSL 证书处理
from urllib import request as urllib_request  # 内置库，发送 HTTP 请求
import requests                      # 第三方库，更简洁的 HTTP 请求（用于获取站名）
from prettytable import PrettyTable  # 第三方库，在终端中以表格形式展示数据

# 解决 HTTPS 证书验证问题
# 12306 的 HTTPS 证书有时候会报错，加上这句可以跳过验证
ssl._create_default_https_context = ssl._create_unverified_context


# ============================================================
# 第一部分：获取全国火车站编码
# ============================================================

def get_station_data():
    """
    从 12306 获取全国所有火车站的名称和编码对应关系
    
    返回值：
        stations_dict     - 中文站名 → 编码，如 {'郑州': 'ZZF', '开封': 'KFF'}
        stations_dict_res - 编码 → 中文站名，如 {'ZZF': '郑州', 'KFF': '开封'}
    """
    print('正在获取全国火车站编码数据...')
    
    # 12306 的站名文件地址
    # 这个 JS 文件包含了全国所有火车站的名称和对应编码
    url = 'https://kyfw.12306.cn/otn/resources/js/framework/' \
          'station_name.js?station_version=1.9368'
    
    # 发送请求获取数据
    # verify=False 跳过 SSL 证书验证
    response = requests.get(url, verify=False)
    
    # 使用正则表达式提取中文站名和编码
    # [\u4e00-\u9fa5]+ 匹配一个或多个中文字符（站名）
    # [A-Z]+ 匹配一个或多个大写字母（站编码）
    # \| 匹配管道符（数据分隔符）
    stations = re.findall(r'([\u4e00-\u9fa5]+)\|([A-Z]+)', response.text)
    
    # 使用 dict() 将元组列表转为字典
    # stations 是 [('北京北', 'VAP'), ('北京东', 'BOP'), ...] 形式
    # dict() 后变为 {'北京北': 'VAP', '北京东': 'BOP', ...}
    stations_dict = dict(stations)
    
    # 反转字典：编码 → 中文站名
    # 使用 zip() 将 values 和 keys 反过来打包，再用 dict() 转为字典
    # zip(values, keys) → [('VAP', '北京北'), ('BOP', '北京东'), ...]
    stations_dict_res = dict(zip(stations_dict.values(), stations_dict.keys()))
    
    print(f'获取成功！共 {len(stations_dict)} 个车站')
    return stations_dict, stations_dict_res


# ============================================================
# 第二部分：演示 dict 和 zip 函数
# ============================================================

def demo_dict_and_zip():
    """
    演示 Python 内置函数 dict() 和 zip() 的用法
    """
    print('【演示】dict() 和 zip() 函数')
    print('-' * 40)
    
    # ---- zip() 的用法 ----
    # zip() 就像拉链一样，把两个列表"拉"到一起
    a = [1, 2, 3]
    b = [4, 5, 6]
    zipped = list(zip(a, b))
    print(f'zip([1,2,3], [4,5,6]) = {zipped}')
    # 输出：[(1, 4), (2, 5), (3, 6)]
    
    # ---- dict() 的用法 ----
    # 方式1：传入关键字参数
    d1 = dict(a='a', b='b', t='t')
    print(f"dict(a='a', b='b', t='t') = {d1}")
    
    # 方式2：从 zip 结果构建字典
    d2 = dict(zip(['one', 'two', 'three'], [1, 2, 3]))
    print(f"dict(zip(['one','two','three'], [1,2,3])) = {d2}")
    
    # 方式3：从元组列表构建
    d3 = dict([('one', 1), ('two', 2), ('three', 3)])
    print(f"dict([('one',1), ('two',2), ('three',3)]) = {d3}")
    print()


# ============================================================
# 第三部分：构造 API 请求获取余票数据
# ============================================================

def get_json(url, train_date, from_station, to_station,
             purpose_codes='ADULT'):
    """
    向 12306 API 发送请求，获取余票数据的 JSON
    
    参数：
        url            - API 基础地址
        train_date     - 查询日期，格式：'2024-01-15'
        from_station   - 出发站编码，如 'ZZF'
        to_station     - 到达站编码，如 'KFF'
        purpose_codes  - 票种类型：'ADULT'=成人，'0X00'=学生
    
    返回值：JSON 解析后的 Python 字典
    """
    # 拼接完整的 API 地址
    # 这就像填写一个网页表单，把参数拼到 URL 后面
    full_url = url + '?leftTicketDTO.train_date=' \
                   + train_date + '&leftTicketDTO.from_station=' \
                   + from_station + '&leftTicketDTO.to_station=' \
                   + to_station + '&purpose_codes=' + purpose_codes
    
    # 创建请求对象
    req = urllib_request.Request(full_url)
    
    # 添加 User-Agent 请求头 —— 伪装成浏览器
    # 就像间谍需要穿上合适的衣服才能混入人群
    req.add_header('User-Agent',
                   'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/56.0.2924.87 Safari/537.36')
    
    # 添加 Cookie 请求头
    # Cookie 就像一张"入场券"，证明你之前访问过这个网站
    req.add_header('Cookie',
                   'JSESSIONID=PLACEHOLDER; '
                   'RAIL_EXPIRATION=0; '
                   'RAIL_DEVICEID=placeholder')
    
    # 发送请求并读取响应
    with urllib_request.urlopen(req) as f:
        return json.loads(f.read())


# ============================================================
# 第四部分：解析并展示余票数据
# ============================================================

def list_ticket(from_station_name, to_station_name, train_date,
                stations_dict, stations_dict_res):
    """
    查询并展示火车票信息
    
    参数：
        from_station_name  - 出发站中文名，如 '郑州'
        to_station_name    - 到达站中文名，如 '开封'
        train_date         - 查询日期
        stations_dict      - 中文→编码字典
        stations_dict_res  - 编码→中文字典
    """
    # 将中文站名转为编码
    from_code = stations_dict.get(from_station_name)
    to_code = stations_dict.get(to_station_name)
    
    if not from_code:
        print(f'找不到站名：{from_station_name}')
        return
    if not to_code:
        print(f'找不到站名：{to_station_name}')
        return
    
    print(f'\n正在查询：{from_station_name}({from_code}) → '
          f'{to_station_name}({to_code})，日期：{train_date}')
    print('-' * 60)
    
    # 调用 API 获取数据
    try:
        json_result = get_json(
            'https://kyfw.12306.cn/otn/leftTicket/query',
            train_date, from_code, to_code
        )
    except Exception as e:
        print(f'查询失败：{e}')
        print('提示：12306 接口可能需要有效的 Cookie，'
              '或者查询日期超出了预售期范围')
        return
    
    # 获取车票列表
    list_tickets = json_result['data']['result']
    
    # 创建 PrettyTable 对象用于美化输出
    pt = PrettyTable()
    pt.field_names = (
        '车次 始发站 终点站 出发站 到达站 出发时间 到达时间 '
        '历时 商务座 一等座 二等座 软卧 硬卧 软座 硬座 无座 备注'.split()
    )
    
    # 遍历每条车票数据
    for ticket in list_tickets:
        # 用 | 分割字符串，得到各字段的列表
        item = ticket.split('|')
        
        # 根据数据分析的结果，按索引提取各字段
        # 站点编码使用 stations_dict_res 转为中文
        pt.add_row([
            item[3],                                    # 车次
            stations_dict_res.get(item[4], item[4]),    # 始发站（编码→中文）
            stations_dict_res.get(item[5], item[5]),    # 终点站（编码→中文）
            stations_dict_res.get(item[6], item[6]),    # 出发站（编码→中文）
            stations_dict_res.get(item[7], item[7]),    # 到达站（编码→中文）
            item[8],                                    # 出发时间
            item[9],                                    # 到达时间
            item[10],                                   # 历时
            item[32] if len(item) > 32 else '',         # 商务座
            item[31] if len(item) > 31 else '',         # 一等座
            item[30] if len(item) > 30 else '',         # 二等座
            item[23] if len(item) > 23 else '',         # 软卧
            item[28] if len(item) > 28 else '',         # 硬卧
            item[24] if len(item) > 24 else '',         # 软座
            item[29] if len(item) > 29 else '',         # 硬座
            item[26] if len(item) > 26 else '',         # 无座
            item[11] if len(item) > 11 else '',         # 备注
        ])
    
    # 打印美化后的表格
    print(pt)
    print(f'\n共找到 {len(list_tickets)} 趟列车')


# ============================================================
# 第五部分：主程序入口
# ============================================================

if __name__ == '__main__':
    print('12306 火车票查询工具')
    print('=' * 60)
    print()
    
    # ---- 演示 dict 和 zip ----
    demo_dict_and_zip()
    
    # ---- 获取站名编码 ----
    try:
        stations_dict, stations_dict_res = get_station_data()
    except Exception as e:
        print(f'获取站名数据失败：{e}')
        print('提示：将使用内置的示例数据进行演示')
        # 使用部分示例数据
        stations_dict = {
            '郑州': 'ZZF', '开封': 'KFF', '北京': 'BJP',
            '上海': 'SHH', '广州': 'GZQ', '深圳': 'SZQ',
            '郑州东': 'ZAF', '郑州西': 'XPF',
        }
        stations_dict_res = dict(
            zip(stations_dict.values(), stations_dict.keys())
        )
    
    # 展示部分站名编码
    print('\n部分站名编码示例：')
    sample_stations = ['郑州', '开封', '北京', '上海', '广州']
    for name in sample_stations:
        code = stations_dict.get(name, '未知')
        print(f'  {name} → {code}')
    print()
    
    # ---- 查询车票 ----
    print('=' * 60)
    print('开始查询余票')
    print('=' * 60)
    
    # 查询示例：郑州 → 开封
    # 注意：需要有效的日期（在预售期内）和有效的 Cookie
    from datetime import datetime, timedelta
    
    # 使用明天的日期作为查询日期
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    list_ticket(
        from_station_name='郑州',
        to_station_name='开封',
        train_date=tomorrow,
        stations_dict=stations_dict,
        stations_dict_res=stations_dict_res
    )
    
    print()
    print(' 查询演示完成！')
    print(' 提示：如果查询失败，可能需要更新 Cookie 或检查日期是否在预售期内')
