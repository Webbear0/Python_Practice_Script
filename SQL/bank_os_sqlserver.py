#coding=utf-8
# 功能：实现银行业务开户、销户、存款、取款和查询余额等功能
import pyodbc  # 改用 pyodbc 驱动

class BankSystem:
    def __init__(self, database):
        server = input("请输入数据库服务器地址：")
        user = input("请输入数据库登录用户名：")
        password = input("请输入数据库登录密码：")
        print("\n————初始化系统————")
        
        try:
            # 连接 master 数据库进行初始化
            self.conn = pyodbc.connect(
                f'DRIVER={{SQL Server}};'
                f'SERVER={server};'
                f'DATABASE=master;'
                f'UID={user};'
                f'PWD={password};'
            )
            self.cursor = self.conn.cursor()
            
            # 检查并创建数据库
            self.cursor.execute(f"""
                IF NOT EXISTS(SELECT * FROM sys.databases WHERE name = '{database}')
                BEGIN
                    CREATE DATABASE {database};
                END
            """)
            self.conn.commit()
            
            # 切换到目标数据库
            self.cursor.execute(f"USE {database};")
            
            # 创建数据表（调整字段类型和约束）
            create_table = f"""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='bank_accounts' AND xtype='U')
                CREATE TABLE bank_accounts(
                    card_id INT IDENTITY(10000000,1) PRIMARY KEY,  -- 从8位数开始自增
                    card_name VARCHAR(8) NOT NULL UNIQUE,
                    card_password VARCHAR(16) NOT NULL DEFAULT '88888888',
                    card_money DECIMAL(18,2) NOT NULL DEFAULT 0
                )
            """
            self.cursor.execute(create_table)
            self.conn.commit()
            print(f"数据库 {database}@{server} 初始化成功")
            
        except pyodbc.Error as e:
            if '18456' in str(e):  # 登录失败错误代码
                print("用户名或密码错误")
            elif '42000' in str(e):  # 权限错误
                print("数据库访问权限不足")
            else:
                print(f"数据库连接错误: {str(e)}")
            exit(1)

    def create_user(self):
        """开户功能（使用参数化查询防止SQL注入）"""
        print("————开户系统————")
        card_name = input('请输入开户用户名: ')
        card_password = input('请输入密码: ')
        
        try:
            self.cursor.execute(
                "INSERT INTO bank_accounts (card_name, card_password) VALUES (?, ?)",
                (card_name, card_password)
            )
            self.conn.commit()
            print(f"用户 {card_name} 开户成功，初始余额0元")
            
        except pyodbc.IntegrityError:  # 捕获唯一约束冲突
            print("开户失败，该用户名已存在！")

    def delete_user(self):
        """销户功能（必须余额为0）"""
        print("————销户系统————")
        card_name = input('请输入销户用户名: ')
        card_password = input('请输入密码: ')
        
        # 参数化查询
        self.cursor.execute(
            "DELETE FROM bank_accounts WHERE card_name=? AND card_password=? AND card_money=0",
            (card_name, card_password)
        )
        if self.cursor.rowcount > 0:
            self.conn.commit()
            print(f"用户 {card_name} 销户成功")
        else:
            print("销户失败：用户不存在、密码错误或余额不为零")

    def save_money(self):
        """存款功能（带事务处理）"""
        print("————存款系统————")
        card_name = input('请输入用户名: ')
        amount = float(input('请输入存款金额: '))
        
        try:
            # 开启事务
            self.conn.autocommit = False
            # 检查用户是否存在
            self.cursor.execute(
                "SELECT card_id FROM bank_accounts WHERE card_name=?", 
                (card_name,))
            if not self.cursor.fetchone():
                raise ValueError("用户不存在")
            
            # 更新余额
            self.cursor.execute(
                "UPDATE bank_accounts SET card_money = card_money + ? WHERE card_name=?",
                (amount, card_name)
            )
            self.conn.commit()
            print(f"成功存入 {amount} 元")
            
        except Exception as e:
            self.conn.rollback()
            print(f"存款失败: {str(e)}")
        finally:
            self.conn.autocommit = True

    def get_money(self):
        """取款功能（带余额检查）"""
        print("————取款系统————")
        card_name = input('请输入用户名: ')
        card_password = input('请输入密码: ')
        amount = float(input('请输入取款金额: '))
        
        try:
            self.conn.autocommit = False
            # 验证账户信息并获取当前余额
            self.cursor.execute(
                "SELECT card_money FROM bank_accounts WHERE card_name=? AND card_password=?",
                (card_name, card_password)
            )
            row = self.cursor.fetchone()
            if not row:
                raise ValueError("用户不存在或密码错误")
                
            balance = row[0]
            if balance < amount:
                raise ValueError("余额不足")
                
            # 执行扣款
            self.cursor.execute(
                "UPDATE bank_accounts SET card_money = card_money - ? WHERE card_name=?",
                (amount, card_name)
            )
            self.conn.commit()
            print(f"成功取出 {amount} 元，当前余额 {balance - amount} 元")
            
        except Exception as e:
            self.conn.rollback()
            print(f"取款失败: {str(e)}")
        finally:
            self.conn.autocommit = True

    def search_money(self):
        """查询余额（使用存储过程）"""
        print("————查询系统————")
        card_name = input('请输入用户名: ')
        card_password = input('请输入密码: ')
        
        # 创建存储过程（实际应提前创建）
        self.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE type = 'P' AND name = 'sp_get_balance')
            EXEC('
                CREATE PROCEDURE sp_get_balance
                    @name VARCHAR(8),
                    @pwd VARCHAR(16)
                AS
                BEGIN
                    SELECT card_money FROM bank_accounts
                    WHERE card_name = @name AND card_password = @pwd
                END
            ')
        """)
        
        try:
            self.cursor.execute("EXEC sp_get_balance @name=?, @pwd=?", 
                               (card_name, card_password))
            row = self.cursor.fetchone()
            if row:
                print(f"当前余额：{row[0]} 元")
            else:
                print("查询失败：用户不存在或密码错误")
        except pyodbc.Error as e:
            print(f"查询出错: {str(e)}")

if __name__ == '__main__':
    system = BankSystem("BankDB")
    menu = {
        '1': system.create_user,
        '2': system.delete_user,
        '3': system.save_money,
        '4': system.get_money,
        '5': system.search_money
    }
    
    while True:
        print("\n1.开户  2.销户  3.存款  4.取款  5.查询  0.退出")
        choice = input("请选择操作：")
        if choice == '0':
            system.conn.close()
            print("系统已退出")
            break
        elif choice in menu:
            menu[choice]()
        else:
            print("无效的输入，请重新选择！")