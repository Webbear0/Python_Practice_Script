#coding=utf-8
#功能：实现银行业务开户、销户、存款、取款和查询余额等功能
import pymysql

class bank:
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
        create_table = f"create table if not exists {database}(`card_id` int(8) zerofill not null unique key auto_increment comment '卡号',\
            `card_name` varchar(8) not null primary key comment '持卡人',\
            `card_password` varchar(16) not null default '88888888' comment '卡密码',\
            `card_money` decimal(10,2) not null default 0 comment '余额')charset=utf8;"
        cr.execute(create_table) # 连接成功后创建数据库和数据表
        cr.close()
        db_conn.close()
        print(f"数据库 {database}@{host} 初始化成功")
        self.database = database
        self.db_conn = pymysql.connect(host=host, user=user, password=password, db=database, charset="utf8", port=3306)


    def create_user(self):
        print("————开户系统————")
        card_name = input('请输入开户用户名:')
        card_password = input('请输入密码:')
        if (len(card_name) == 0) or (len(card_password) == 0):
            print("输入的值不能为空")
        elif (len(card_name) <= 9) or (len(card_password) <= 17):
            cr = self.db_conn.cursor()
            create_sql = "insert ignore into `%s` (`card_name`,`card_password`) values (%%s,%%s);" % self.database
            try:
                # 添加数据（使用参数化查询防止SQL注入）
                cr.execute(create_sql, (card_name, card_password))
                self.db_conn.commit()
            except Exception as error:
                if str(error)[1] == "0":
                    print(f"开户失败，用户已经注册过了 错误代码 {str(error)[1]}")
                else:
                    print(f"未知错误 错误代码 {error}")
            finally:
                cr.close()
        else:
            print('输入的值错误，请重新输入')

    def delete_user(self):
        print("————销户系统————")
        card_name = input('请输入销户用户名')
        card_password = input('请输入密码')
        cr = self.db_conn.cursor()
        delete_sql = "delete from `%s` where card_name=%%s and card_password=%%s and card_money=0;" % self.database
        # 删除数据（使用参数化查询防止SQL注入）
        result = cr.execute(delete_sql, (card_name, card_password))
        self.db_conn.commit()
        if result == 0:
            print('销户失败,请检查输入')
        else:
            print(f'用户 {card_name} 销户成功')
        cr.close()

    def save_money(self):
        print("————存款系统————")
        card_name = input('请输入用户名')
        card_password = input('请输入密码')
        card_money = input('请输入存款金额')
        cr = self.db_conn.cursor()
        save_sql = "update `%s` set card_money=card_money+%%s where card_name=%%s and card_password=%%s;" % self.database
        # 余额加上输入的金额（使用参数化查询防止SQL注入）
        result = cr.execute(save_sql, (card_money, card_name, card_password))
        self.db_conn.commit()
        if result == 0:
            print('存款失败,请检查输入')
        else:
            print(f'用户{card_name}存款 {card_money}元 成功')
        cr.close()

    def get_money(self):
        print("————取款系统————")
        card_name = input('请输入用户名')
        card_password = input('请输入密码')
        card_money = input('请输入取款金额')
        cr = self.db_conn.cursor()
        get_sql = "update `%s` set card_money=card_money-%%s where card_name=%%s and card_password=%%s;" % self.database
        # 余额减去输入的金额（使用参数化查询防止SQL注入）
        result = cr.execute(get_sql, (card_money, card_name, card_password))
        self.db_conn.commit()
        if result == 0:
            print('取款失败,请检查输入')
        else:
            print(f'用户{card_name}取款 {card_money}元 成功')
        cr.close()

    def search_money(self):
        print("————查询系统————")
        card_name = input('请输入查询用户名')
        card_password = input('请输入密码')
        cr = self.db_conn.cursor()
        search_sql = "select card_money from `%s` where card_name=%%s and card_password=%%s;" % self.database
        # 查询数据库（使用参数化查询防止SQL注入）
        try:
            cr.execute(search_sql, (card_name, card_password))
            result = cr.fetchall()
            print(f"用户 {card_name} 的余额为 {result[0]}元")
        except:
            print('查询失败,用户不存在')
        cr.close()


if __name__ == '__main__':
    database_name = input("请输入连接的数据库名：")
    link_info = bank(database=database_name)
    while True:
        print("\n1.开户\n2.销户\n3.存款\n4.取款\n5.查询\n0.退出\n")
        user_input = input("请选择：")
        if user_input == '1':
            link_info.create_user()
        elif user_input == '2':
            link_info.delete_user()
        elif user_input == '3':
            link_info.save_money()
        elif user_input == '4':
            link_info.get_money()
        elif user_input == '5':
            link_info.search_money()
        elif user_input == '0':
            print("————欢迎下次使用————")
            break