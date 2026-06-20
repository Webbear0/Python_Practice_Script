#coding=utf-8
# 功能:爬前程无忧网站
# 日期：2023年6月6日
import csv,re,requests,os,urllib.parse # 导入模块

def qianchengwuyou(job_name, pages,cookie):
    try:
        os.makedirs("前程无忧\\")
    except Exception as e:
        print(f"文件夹已创建\n{e}")
    with open(f'前程无忧\\{job_name}.csv', mode='a', encoding='utf-8', newline='') as f: 
        csv_w = csv.DictWriter(f, fieldnames=['岗位', '公司', '学历', '工作经验', '月薪', '待遇', '岗位链接'])
        csv_w.writeheader()  # 写入标题
        
        job_name_encoded = urllib.parse.quote(job_name)  # 将汉字编码为URL编码（移到循环外，避免重复编码）
        for page in range(1,pages+1):
            url = f'https://we.51job.com/api/job/search-pc?api_key=51job&timestamp=1685494731&'\
f'keyword={job_name_encoded}&searchType=2&function=&industry=&jobArea=000000&jobArea2=&landmark=&metro=&salary=&workYear=&degree=&companyType=&companySize=&jobType=&issueDate=&sortType=0&'\
f'pageNum={page}&pageSize=20&source=1&pageCode=sou%7Csou%7Csoulb'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebK:it/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                'cookie' : cookie,
                'Referer' : url
            }
            # 不登录只能爬一页
            response = requests.get(url=url, headers=headers)
            jobs = re.findall(
                '"workYearString":"(.*?)","degreeString":"(.*?)","industryType1Str".*?"fullCompanyName":"(.*?)","companyLogo".*?"jobHref":"(.*?)","companyHref".*?"jobName":"(.*?)","jobTags":(.*?),"jobNumString".*?"provideSalaryString":"(.*?)","issueDateString"',
                response.text)
            
            for job in jobs:
                csv_w.writerow({'岗位': job[4],
                                '公司': job[2],
                                '学历': job[1],
                                '工作经验': job[0],
                                '月薪': job[6],
                                '待遇': job[5],
                                '岗位链接': job[3]})
    print("\n爬取成功")

if __name__ == "__main__" :
    job_name = input("请输入需要查找的职位名称:")
    pages = int(input("请输入需要爬取的页面数量:"))
    cookie = input("请输入登录后的cookie:\n")
    qianchengwuyou(job_name,pages,cookie)