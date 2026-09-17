#coding=utf-8
# 功能：模拟数字校园的 注册 和 登录 功能，用数据库存放注册的用户名和密码
import pymysql

class campus_network:
    def __init__(self, database):
        host = input("请输入数据库ip地址：")
        user = input("请输入数据库登录用户名：")
        password = input("请输入数据库登录密码：")
        print("\n————初始化系统————")
        try: # 尝试登录数据库
            db_conn = pymysql.connect(host=host, user=user, password=password, charset="utf8", port=3306)
            cr = db_conn.cursor()
        except pymysql.err.OperationalError as error:
            if str(error)[1:5] == "2003": # 连接错误
                print(f"数据库连接错误 错误代码{str(error)[1:5]}")
                exit(1)
            elif str(error)[1:5] == "1045": # 登录信息错误
                print(f"用户名或密码错误 错误代码{str(error)[1:5]}")
                exit(1)
            else: # 输出错误代码
                print(f"未知错误 请检查网络配置是否正确 错误代码{str(error)[1:5]}")
                exit(1)
        cr.execute(f"create database if not exists {database};") 
        cr.execute(f"use {database};")
        create_table = f"create table if not exists {database}\
                    (`user_name` varchar(8)  not null primary key comment '用户名',\
                    `user_password` varchar(16) not null default '88888888' comment '用户密码')charset=utf8;"
        cr.execute(create_table) # 连接成功后创建数据库和数据表
        cr.close()
        db_conn.close()
        print(f"数据库 {database}@{host} 初始化成功")
        self.database = database
        self.db_conn = pymysql.connect(host=host, user=user, password=password, db=database, charset="utf8", port=3306)

    def create_user(self):
        print("\n————注册系统————")
        user_name = input('请输入注册用户名:')
        user_password = input('请输入密码:')
        if (len(user_name) == 0) or (len(user_password) == 0): # 简单判断输入信息
            print("输入的值不能为空")
        elif (len(user_name) <= 9) or (len(user_password) <= 17):
            cr = self.db_conn.cursor()
            search_sql = "select user_name from `%s` where user_name=%%s and user_password=%%s;" % self.database
            try: # 查询数据库中账号密码是否对应（使用参数化查询防止SQL注入）
                cr.execute(search_sql, (user_name, user_password))
                result = cr.rowcount
            except Exception as error:
                print(f"查询错误{error}")
                cr.close()
                return
            if result >= 1:
                print(f"\n用户 {user_name} 已存在")
            elif result == 0:
                create_sql = "insert ignore into `%s`(`user_name`,`user_password`)values (%%s,%%s);" % self.database
                cr.execute(create_sql, (user_name, user_password))
                self.db_conn.commit()
                print("注册成功") 
            else:
                print(f"未知错误{result}")
            cr.close()
        else:
            print('输入的值错误，请重新输入')

    def login_user(self):
        print("\n————登录系统————")
        user_name = input('请输入用户名:')
        user_password = input('请输入密码:')
        cr = self.db_conn.cursor()
        search_sql = "select user_name from `%s` where user_name=%%s and user_password=%%s;" % self.database
        try: # 查询数据库中账号密码是否对应（使用参数化查询防止SQL注入）
            cr.execute(search_sql, (user_name, user_password))
            result = cr.rowcount
        except Exception as error:
            print(f"查询错误{error}")
            cr.close()
            return
        if result == 0:
            print(f"\n用户 {user_name} 不存在请重新输入")
        elif result >= 1:
            print(f"\n用户 {user_name} 登录成功")
        else:
            print("未知错误")
        cr.close()

if __name__ == '__main__':
    database_name = input("请输入连接的数据库名：")
    link_info = campus_network(database=database_name)
    while True:
        print("\n1.注册\n2.登录\n0.退出\n")
        user_input = input("请选择：")
        if user_input == '1':
            link_info.create_user()
        elif user_input == '2':
            link_info.login_user()
        elif user_input == '0':
            print("————欢迎下次使用————")
            break