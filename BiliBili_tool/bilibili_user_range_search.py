# B站用户范围查询与Excel保存工具（面向对象版）
import requests
import xlwt
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


class BilibiliUserSearch:
    """B站用户批量查询器"""

    def __init__(self, start_uid, end_uid):
        self.start_uid = start_uid
        self.end_uid = end_uid
        self.url = "https://api.bilibili.com/x/web-interface/card"
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.results = []  # 保存查询结果

    def query_user(self, uid):
        """查询单个用户信息，返回字典或 None"""
        response = requests.get(self.url, params={"mid": uid}, headers=self.headers, timeout=5)
        res_data = response.json()

        if res_data["code"] == 0:
            card = res_data["data"]["card"]
            return {
                "uid": uid,
                "name": card["name"],
                "sex": card["sex"],
                "level": card["level_info"]["current_level"],
                "fans": card["fans"],
            }
        elif res_data["code"] == -352:
            print(f"[警告] UID: {uid} -> 触发-352风控限制")
        else:
            print(f"[跳过] UID: {uid} -> 用户不存在或被封禁")
        return None

    def search_range(self):
        """批量查询 UID 范围内的用户"""
        total = self.end_uid - self.start_uid + 1
        print(f"\n开始查询范围 [{self.start_uid} ~ {self.end_uid}]，共 {total} 个UID...")
        for i, uid in enumerate(range(self.start_uid, self.end_uid + 1), 1):
            try:
                user = self.query_user(uid)
                if user:
                    self.results.append(user)
                    print(f"  [{i}/{total}] UID: {user['uid']} | {user['name']} | {user['sex']} | LV{user['level']} | 粉丝: {user['fans']}")
            except Exception as e:
                print(f"  [{i}/{total}] UID: {uid} -> 请求失败: {e}")
            time.sleep(0.1)

    def save_to_excel(self):
        """将查询结果保存为 Excel 文件"""
        wb = xlwt.Workbook(encoding="utf-8")
        sheet = wb.add_sheet("用户数据")

        # 写入表头
        for col, header in enumerate(["UID", "用户名", "性别", "等级", "粉丝数"]):
            sheet.write(0, col, header)

        # 写入数据
        for row, user in enumerate(self.results, 1):
            sheet.write(row, 0, user["uid"])
            sheet.write(row, 1, user["name"])
            sheet.write(row, 2, user["sex"])
            sheet.write(row, 3, user["level"])
            sheet.write(row, 4, user["fans"])

        filename = f"bilibili_users_{self.start_uid}_{self.end_uid}.xls"
        wb.save(filename)
        print(f"\n查询完毕！共成功查询到 {len(self.results)} 个用户。")
        print(f"数据已保存至：{filename}")


if __name__ == "__main__":
    # 获取 UID 范围
    if len(sys.argv) >= 3:
        start, end = int(sys.argv[1]), int(sys.argv[2])
    else:
        start = int(input("请输入起始UID（如 5555500）："))
        end = int(input("请输入结束UID（如 5555555）："))

    if start > end:
        print("错误：起始UID不能大于结束UID！")
        exit()

    searcher = BilibiliUserSearch(start, end)
    searcher.search_range()
    searcher.save_to_excel()