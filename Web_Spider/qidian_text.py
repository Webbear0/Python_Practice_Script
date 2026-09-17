#coding=utf-8
# 功能：编写 python 爬虫程序，爬取任意一个小说网站中的健康的一本小说内容
# 日期：2023年6月6日
import requests,os,re,time

# 1、请求小说首页、获取id和标题
def qidian(book_id,page) :
    url = f'https://book.qidian.com/info/{book_id}/#Catalog'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
            AppleWebKit/537.36 (KHTML,like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.50'}
    response = requests.get(url=url, headers=headers)
    url_title = re.findall('data-cid="(.*?)" alt=.*?">(.*?)</a></h2>', response.text)
    try:
        os.makedirs(f"text\\{book_id}")
    except Exception as e:
        print("文件夹已创建\n" , e) 
    # 3、请求地址，得到小说的内容
    for link , title in url_title[:page] :
        text=requests.get(url="https:" + link , headers=headers)
        time.sleep(0.2) # 太快可能会被拦截
        text_base = re.findall('data-v-a1a66cd7><p>(.*?)<p></main>',text.text)
        try:
            # 把 \u3000 替换成空
            #text_handle = text_base[0]
            text = text_base[0].replace('<p>\u3000\u3000', '\n')
            with open(f'text\\{book_id}\\{title}.txt' , 'a' ,encoding="utf-8") as f:
                f.write(title + '\n\n')
                f.write(text)
        except Exception as e:
            print(e)
            continue
        print(f"章节 {title} 下载完成")
    print(f"\n小说号 {book_id} 下载完成")
if __name__ == "__main__" :
    bookid = int(input("请输入小说号(小说页面的url里有)\n:"))
    page = int(input("请输入需要下载多少章内容(在小说目录查看)\n:"))
    qidian(bookid,page)