import requests
import os

def fetch_and_download_bing_wallpaper():
    # 微软官方接口，mkt=zh-CN 代表中国区壁纸
    api_url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-CN"
    
    try:
        # 1. 请求壁纸信息
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("images"):
            latest_wallpaper = data["images"][0]
            title = latest_wallpaper.get("title", "未知标题")
            
            # 官方接口返回的是相对路径，需拼接前缀
            img_url = "https://www.bing.com" + latest_wallpaper.get("url")
            
            # 获取壁纸日期，用于给文件命名（例如：20260418）
            date_str = latest_wallpaper.get("startdate", "unknown_date")
            
            # 过滤掉标题中可能导致文件保存报错的特殊字符
            safe_title = "".join([c for c in title if c not in r'\/:*?"<>|'])
            
            # 拼接最终保存的文件名，例如：Bing_20260418_春日的长城.jpg
            filename = f"Bing_{date_str}_{safe_title}.jpg"
            
            print("=== Bing 官方每日壁纸 ===")
            print(f"标题: {title}")
            print(f"链接: {img_url}")
            print("正在下载中，请稍候...")
            
            # 2. 请求图片本身的数据
            img_response = requests.get(img_url)
            img_response.raise_for_status()
            
            # 3. 以二进制写入模式('wb')将图片保存到当前目录
            with open(filename, 'wb') as file:
                file.write(img_response.content)
                
            # os.path.abspath 可以打印出文件保存的绝对路径，方便你找到它
            print(f" 下载完成！图片已保存至: {os.path.abspath(filename)}")
            
        else:
            print("未能解析到壁纸数据。")

    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {e}")
    except IOError as e:
        print(f"文件保存失败: {e}")

if __name__ == "__main__":
    fetch_and_download_bing_wallpaper()