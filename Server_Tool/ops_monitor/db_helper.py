# db_helper.py -- 数据库操作模块 (SQLite3 本地配置 + MariaDB 远程入库)
import os, sqlite3, pymysql

LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_config.db")


# == SQLite 本地配置 ============================================
def _local_conn():
    return sqlite3.connect(LOCAL_DB)


def init_local_db():
    """初始化本地 SQLite 配置库, 建表。"""
    conn = _local_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS db_server (
            id       INTEGER PRIMARY KEY,
            ip       TEXT NOT NULL,
            port     INTEGER DEFAULT 3306,
            user     TEXT DEFAULT 'root',
            password TEXT DEFAULT '123456',
            services TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS hosts (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ip       TEXT NOT NULL UNIQUE,
            hostname TEXT DEFAULT '',
            user     TEXT DEFAULT 'root',
            password TEXT DEFAULT '123456',
            services TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def has_config():
    """检查是否已有配置数据。"""
    conn = _local_conn()
    count = conn.execute("SELECT COUNT(*) FROM db_server").fetchone()[0]
    conn.close()
    return count > 0


def save_db_server(ip, services, port=3306, user="root", pwd="123456"):
    """保存 MariaDB 服务器信息 (仅一条, id 固定为 1)。"""
    conn = _local_conn()
    conn.execute("INSERT OR REPLACE INTO db_server (id,ip,port,user,password,services) "
                 "VALUES (1,?,?,?,?,?)", (ip, port, user, pwd, services))
    conn.commit()
    conn.close()


def get_db_server():
    """读取 MariaDB 服务器配置, 返回字典或 None。"""
    conn = _local_conn()
    row = conn.execute("SELECT ip,port,user,password,services FROM db_server WHERE id=1").fetchone()
    conn.close()
    if row:
        return {"ip": row[0], "port": row[1], "user": row[2], "password": row[3], "services": row[4]}
    return None


def save_host(ip, services, hostname="", user="root", pwd="123456"):
    """保存一台被监控主机。"""
    conn = _local_conn()
    conn.execute("INSERT OR IGNORE INTO hosts (ip,hostname,user,password,services) VALUES (?,?,?,?,?)",
                 (ip, hostname, user, pwd, services))
    conn.commit()
    conn.close()


def get_all_hosts():
    """读取所有被监控主机, 返回字典列表。"""
    conn = _local_conn()
    rows = conn.execute("SELECT ip,hostname,user,password,services FROM hosts").fetchall()
    conn.close()
    return [{"ip": r[0], "hostname": r[1], "user": r[2], "password": r[3], "services": r[4]}
            for r in rows]


# == MariaDB 远程入库 ===========================================
def _remote_conn(db_info, database="ops_monitor"):
    return pymysql.connect(host=db_info["ip"], port=db_info["port"],
                           user=db_info["user"], password=db_info["password"],
                           database=database, charset="utf8mb4")


def init_remote_db(db_info):
    """在 MariaDB 上创建监控数据库和状态记录表。"""
    conn = pymysql.connect(host=db_info["ip"], port=db_info["port"],
                           user=db_info["user"], password=db_info["password"], charset="utf8mb4")
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS ops_monitor CHARACTER SET utf8mb4")
    cur.execute("USE ops_monitor")
    cur.execute("""CREATE TABLE IF NOT EXISTS server_status (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        hostname        VARCHAR(64),
        ip              VARCHAR(15),
        cpu             FLOAT,
        mem             FLOAT,
        disk            FLOAT,
        services_status TEXT,
        collected_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_ip (ip),
        INDEX idx_time (collected_at)
    )""")
    conn.commit()
    conn.close()


def insert_status(db_info, hostname, ip, cpu, mem, disk, svc_status):
    """将一条巡检记录写入 MariaDB。"""
    conn = _remote_conn(db_info)
    try:
        conn.cursor().execute(
            "INSERT INTO server_status (hostname,ip,cpu,mem,disk,services_status) VALUES (%s,%s,%s,%s,%s,%s)",
            (hostname, ip, cpu, mem, disk, svc_status))
        conn.commit()
    finally:
        conn.close()


def get_latest_status(db_info):
    """获取每台主机最新一条记录。"""
    conn = _remote_conn(db_info)
    try:
        cur = conn.cursor()
        cur.execute("""SELECT hostname, ip, cpu, mem, disk, services_status, collected_at
                       FROM server_status
                       WHERE id IN (SELECT MAX(id) FROM server_status GROUP BY ip)
                       ORDER BY ip""")
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"hostname": r[0], "ip": r[1], "cpu": r[2], "mem": r[3],
             "disk": r[4], "services": r[5], "time": str(r[6])} for r in rows]


def get_history(db_info, limit=60):
    """获取最近 N 条历史记录 (用于折线图)。"""
    conn = _remote_conn(db_info)
    try:
        cur = conn.cursor()
        cur.execute("SELECT hostname, ip, cpu, mem, disk, collected_at "
                    "FROM server_status ORDER BY collected_at DESC LIMIT %s", (limit,))
        rows = list(cur.fetchall())
    finally:
        conn.close()
    rows.reverse()
    return [{"hostname": r[0], "ip": r[1], "cpu": r[2], "mem": r[3],
             "disk": r[4], "time": r[5].strftime("%H:%M") if hasattr(r[5], "strftime") else str(r[5])[11:16]}
            for r in rows]


def cleanup_old_data(db_info, keep_days=30):
    """清理 N 天前的历史数据, 防止表无限膨胀。"""
    conn = _remote_conn(db_info)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM server_status WHERE collected_at < DATE_SUB(NOW(), INTERVAL %s DAY)",
                    (keep_days,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted
