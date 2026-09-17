#coding=utf-8
# 功能: 爬取喜马拉雅
# 日期：2023年6月6日
import requests,re,os

def ximalaya(book_id):
    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
         AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'} # 模拟浏览器
    url=f"https://www.ximalaya.com/album/{book_id}"
    response=requests.get(url=url, headers=headers)
    audia_info=re.findall('"trackId":(\d+),"isPaid":false,"tag":0,"title":"(.*?)","playCount"', response.text)
    try:
        os.makedirs(f"ximalaya\\{book_id}")
    except Exception as e:
        print(f"{book_id} 文件夹已存在\n{e}") 
        
    for id,title in audia_info:
        link = 'https://www.ximalaya.com/revision/play/v1/audio?id='+id+'&ptype=1'
        try:
            audia_content = requests.get(url=link, headers=headers)
            audia_url = audia_content.json()['data']['src'] # 播放地址
            audio = requests.get(url=audia_url,headers=headers).content
            print(f"正在下载{title}")
            with open(f'ximalaya\\{book_id}\\' + title + '.mp3' , 'wb') as f:
                f.write(audio)
        except Exception as e:
            print(f"{title} 下载失败 原因：\n{e}")
            continue
    print(f"{book_id}下载完成")

if __name__ == "__main__" :
    bookid = int(input("请输入节目号(节目的url里有)\n:"))
    ximalaya(bookid)