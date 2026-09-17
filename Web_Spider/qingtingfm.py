#coding=utf-8
# 功能: 爬取蜻蜓fm
# 日期：2023年6月6日

import hmac,time,requests,re,os
# 导入以上模块，由于蜻蜓做了反爬需要hmac库解密hmacMD5

def qingting(book_id,page,access_token,qingting_id) :
    headers={'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
             AppleWebKit/537.36 (KHTML,like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.50'}
    base_url = "https://audio.qingting.fm"
    access_token = access_token  # 没有登录可以为空，不影响
    qingting_id = qingting_id # 没有id可以为空，不影响
    try:
        os.makedirs(f"FM\\{book_id}")
    except Exception as e:
        print(f"{book_id} 文件夹已存在\n{e}")

    for pg in range(1,page+1):
        url=f'https://www.qingting.fm/channels/{book_id}/{pg}'
        response=requests.get(url=url,headers=headers)
        audio_id=re.findall('"id":(\d+),"title":"(.*?)","duration"',response.text)
        # 爬取多页结果 保存到变量
        for id,title in audio_id:
            timestamp = str(round(time.time()*1000))
            # 获取下载链接
            data = f"/audiostream/redirect/{book_id}/{id}?access_token={access_token}&device_id=MOBILESITE&qingting_id={qingting_id}&t={timestamp}"
            message = data.encode('utf-8')
            key = "fpMn12&38f_2e".encode('utf-8') # 这个密钥是固定的，直接写在js的生成sign函数里面，搜索就能找到
            sign = hmac.new(key, message, digestmod='MD5').hexdigest() # 使用hmac库解密，密钥就是上面那个
            whole_url = base_url+data+"&sign="+sign
            print(f'正在下载:{title}......')
            try:
                audio=requests.get(url=whole_url,headers=headers).content
                with open(f'FM\\{book_id}\\'+title+'.mp3','wb') as f:
                    f.write(audio)
                # 按照节目号保存到文件夹 重命名为节目名称.mp3
            except Exception as e:
                print(f"{title} 下载失败 原因：\n{e}")
                continue
        print(f'{book_id} 第{pg}页 下载完成......')

if __name__ == "__main__" :
    bookid = int(input("请输入节目号(节目的url里有)\n:"))
    page = int(input("请输入需要下载多少页内容(在节目下方查看)\n:"))
    access_token = input("请输入token(没有token直接回车)\n:") # 爬取特殊音频需要
    qingting_id = input("请输入蜻蜓id(没有账号可以直接回车)\n:") # 爬取付费音频需要登录账号
    qingting(bookid,page,access_token,qingting_id)