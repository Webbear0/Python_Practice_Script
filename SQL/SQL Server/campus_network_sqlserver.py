#coding=utf-8
# 功能：模拟数字校园的 注册 和 登录 功能，用 SQL Server 数据库存放注册的用户名和密码
# 日期：2026年10月1日
import pyodbc

class CampusNetwork:
    def __init__(self, database):
        server = input("请输入数据库服务器地址：")
        user = input("请输入数据库登录用户名：")
        password = input("请输入数据库登录密码：")
        print("\n————初始化系统————")

        try:
            # 连接 master 数据库进行初始化
            conn = pyodbc.connect(
                f'DRIVER={{SQL Server}};'
                f'SERVER={server};'
                f'DATABASE=master;'
                f'UID={user};'
                f'PWD={password};'
            )
            cursor = conn.cursor()

            # 检查并创建数据库
            cursor.execute(f"""
                IF NOT EXISTS(SELECT * FROM sys.databases WHERE name = '{database}')
                BEGIN
                    CREATE DATABASE {database};
                END
            """)
            conn.commit()

            # 切换到目标数据库
            cursor.execute(f"USE {database};")

            # 创建用户表
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='campus_users' AND xtype='U')
                CREATE TABLE campus_users(
                    user_name     VARCHAR(8)  NOT NULL PRIMARY KEY,
                    user_password VARCHAR(16) NOT NULL DEFAULT '88888888'
                )
            """)
            conn.commit()
            cursor.close()
            conn.close()
            print(f"数据库 {database}@{server} 初始化成功")

        except pyodbc.Error as e:
            if '18456' in str(e):
                print("用户名或密码错误")
            elif '08001' in str(e):
                print("数据库连接错误，请检查服务器地址")
            else:
                print(f"数据库错误: {e}")
            exit(1)

        # 初始化完成后，重新连接到目标数据库供后续使用
        self.conn = pyodbc.connect(
            f'DRIVER={{SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={user};'
            f'PWD={password};'
        )

    def create_user(self):
        print("\n————注册系统————")
        user_name = input("请输入注册用户名:")
        user_password = input("请输入密码:")

        if not user_name or not user_password:
            print("输入的值不能为空")
            return
        if len(user_name) > 8 or len(user_password) > 16:
            print("用户名不超过8位，密码不超过16位")
            return

        cursor = self.conn.cursor()
        try:
            # 查询用户是否已存在（参数化查询防止SQL注入）
            cursor.execute("SELECT user_name FROM campus_users WHERE user_name = ?", user_name)
            if cursor.fetchone():
                print(f"\n用户 {user_name} 已存在")
            else:
                cursor.execute(
                    "INSERT INTO campus_users (user_name, user_password) VALUES (?, ?)",
                    user_name, user_password
                )
                self.conn.commit()
                print("注册成功")
        except pyodbc.Error as e:
            print(f"操作错误: {e}")
        finally:
            cursor.close()

    def login_user(self):
        print("\n————登录系统————")
        user_name = input("请输入用户名:")
        user_password = input("请输入密码:")

        cursor = self.conn.cursor()
        try:
            # 参数化查询验证用户名与密码
            cursor.execute(
                "SELECT user_name FROM campus_users WHERE user_name = ? AND user_password = ?",
                user_name, user_password
            )
            if cursor.fetchone():
                print(f"\n用户 {user_name} 登录成功")
            else:
                print(f"\n用户名或密码错误，请重新输入")
        except pyodbc.Error as e:
            print(f"查询错误: {e}")
        finally:
            cursor.close()


if __name__ == '__main__':
    database_name = input("请输入连接的数据库名：")
    system = CampusNetwork(database=database_name)
    while True:
        print("\n1.注册\n2.登录\n0.退出\n")
        user_input = input("请选择：")
        if user_input == '1':
            system.create_user()
        elif user_input == '2':
            system.login_user()
        elif user_input == '0':
            system.conn.close()
            print("————欢迎下次使用————")
            break
