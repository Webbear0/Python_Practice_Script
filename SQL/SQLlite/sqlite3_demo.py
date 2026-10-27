# coding=utf-8
import sqlite3

# 1、连接本地 SQLite 数据库（若 hosts.db 不存在则自动创建）
conn = sqlite3.connect("hosts.db")

# 2、创建主机资产表 hosts（id 为自增主键，port 默认值为 22）
conn.execute("""CREATE TABLE IF NOT EXISTS hosts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ip       TEXT    NOT NULL,
    port     INTEGER NOT NULL DEFAULT 22,
    user     TEXT    NOT NULL,
    password TEXT    NOT NULL,
    services TEXT    NOT NULL
)""")
conn.commit()

# 3、添加主机记录（使用 ? 占位符传参，调用 commit 提交事务）
conn.execute(
    "INSERT INTO hosts (ip,port,user,password,services) VALUES (?,?,?,?,?)",
    ("172.16.10.254", 22, "root", "123456", "apache2,mariadb")
)
conn.commit()

# 4、查询并打印数据库中所有主机记录（fetchall 返回元组列表）
rows = conn.execute("SELECT id,ip,port,user,services FROM hosts").fetchall()
print("=== 已保存的巡检主机列表 ===")
for r in rows:
    print(f"ID: {r[0]} | 主机: {r[3]}@{r[1]}:{r[2]} | 监控服务: {r[4]}")

# 5、修改指定主机的监控服务（UPDATE 按 ID 定位行, 用 ? 占位符传入新值）
conn.execute("UPDATE hosts SET services=? WHERE id=?", ("apache2,mariadb", 1))
conn.commit()

choice = input("是否按 ID 删除指定主机？输入 'y' 继续: ").strip().lower()
if choice == 'y':
    # 6、按 ID 删除指定主机（通过 cur.rowcount 判断是否删除成功）
    cur = conn.execute("DELETE FROM hosts WHERE id=?", (1,))
    conn.commit()
else:
    print("已取消删除操作")

# 7、关闭数据库连接
conn.close()