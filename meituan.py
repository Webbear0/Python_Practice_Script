# coding=utf-8
# 功能： 编写 python 爬虫程序，爬取美团网站的信息，存入本地csv文件中。
# 日期：2023年6月6日

import csv, urllib.parse, re, requests, os  # 导入模块

def meituan(name, pages, cookie_main, cookie_page):
    original_name = name  # 保存原始名称用于文件命名
    name = urllib.parse.quote(name)
    try:
        os.makedirs("美团\\")
    except Exception as e:
        print(f"文件夹已创建\n{e}")
    with open(f'美团\\{original_name}.csv', mode='a', encoding='utf-8', newline='') as f:
        csv_w = csv.DictWriter(f, fieldnames=['店名', '路名', '评价', '人均消费', '评价数', '详情链接'])
        csv_w.writeheader()

        for page in range(1, pages + 1):
            url = f'https://i.meituan.com/s/nanning-{name}?p={page}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebK:it/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                'cookie': cookie_main,
            }
            response = requests.get(url=url, headers=headers)
            dianmings = re.findall('<a class="react" href="(.*?)" data-ctpoi=".*?'
                                   '<span class="poiname">(.*?)</span>.*?'
                                   '<em class="star-text">(.*?)</em>.*?'
                                   '<a class="" onclick="return false;" href="//i.meituan.com/nanning.*?">(.*?)</a>',
                                   response.text, re.S)
            headers['cookie'] = cookie_page
            for dianming in dianmings:
                link = dianming[0]
                print(link)
                renjun_pingjia = requests.get(url=link, headers=headers)
                r_p = re.findall(r'人均：¥<!-- /react-text --><!-- react-text: 65 -->(\d+)<!-- /react-text -->.*?'
                                 r'<!-- react-text: \d+ -->(\d+)<!-- /react-text --><!-- react-text: \d+ -->',renjun_pingjia.text, re.S)
                try:
                    csv_w.writerow({
                        '店名': dianming[1],
                        '路名': dianming[-1],
                        '评价': dianming[-2],
                        '人均消费': r_p[0][0],
                        '评价数': r_p[0][1],
                        '详情链接': dianming[0]
                    })
                except Exception as e:
                    print(e)
    print(f"爬取完成")
if __name__ == "__main__":
    name = input("请输入需要查找的参数:")
    pages = int(input("请输入需要爬取的页面数量:"))
    cookie_main = input("请输入登录(i.meituan.com/)后的cookie:\n")
    cookie_page = input("请输入页面(meishi.meituan.com/i/poi/)的cookie:\n")
    meituan(name, pages, cookie_main, cookie_page)