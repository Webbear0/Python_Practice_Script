# remote_monitor.py -- 多主机自动化巡检与服务自愈工具
# 基于 paramiko + psutil(远端) + sqlite3, 支持主机信息持久化与交互式管理
# 前置要求: 目标 Ubuntu 24.04.5 LTS 主机已安装 python3-psutil
import json, os, sys, time, getpass, sqlite3, paramiko

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hosts.db")

# 远程一行 Python 命令: 调用目标机 psutil 采集 CPU/内存/磁盘占用率, 以 JSON 返回
COLLECT_CMD = (
    "python3 -c '"
    "import psutil,json; d=psutil.disk_usage(\"/\"); "
    "print(json.dumps({\"cpu\":psutil.cpu_percent(interval=1),"
    "\"mem\":psutil.virtual_memory().percent,"
    "\"disk\":round(d.used/d.total*100,1)}))"
    "'"
)
THRESHOLD = 90  # 资源占用率告警阈值 (%)


# == 数据库操作 ================================================
def init_db():
    """初始化 SQLite 数据库, 返回连接对象。"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS hosts (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        ip       TEXT    NOT NULL,
        port     INTEGER NOT NULL DEFAULT 22,
        user     TEXT    NOT NULL,
        password TEXT    NOT NULL,
        services TEXT    NOT NULL
    )""")
    conn.commit()
    return conn


def add_host(conn):
    """交互式添加一台主机到数据库。"""
    print("\n-- 添加主机 --")
    ip   = input("  IP 地址: ").strip()
    ps   = input("  SSH 端口 [22]: ").strip()
    port = int(ps) if ps else 22
    user = input("  用户名: ").strip()
    pwd  = getpass.getpass("  密码: ")
    svcs = input("  监控服务名 (逗号分隔, 如 apache2,mariadb): ").strip()
    if not all([ip, user, pwd, svcs]):
        return print("  [错误] 所有字段均为必填项")
    conn.execute("INSERT INTO hosts (ip,port,user,password,services) VALUES (?,?,?,?,?)",
                 (ip, port, user, pwd, svcs))
    conn.commit()
    print(f"  [完成] 已添加 {user}@{ip}:{port}  服务: {svcs}")


def list_hosts(conn):
    """列出数据库中所有主机。"""
    rows = conn.execute("SELECT id,ip,port,user,services FROM hosts").fetchall()
    if not rows:
        return print("  (暂无主机记录)")
    print(f"\n  {'ID':>4}  {'IP':<16} {'端口':>5}  {'用户':<10} {'监控服务'}")
    print(f"  {'─'*4}  {'─'*16} {'─'*5}  {'─'*10} {'─'*24}")
    for r in rows:
        print(f"  {r[0]:>4}  {r[1]:<16} {r[2]:>5}  {r[3]:<10} {r[4]}")


def delete_host(conn):
    """按 ID 删除一台主机。"""
    list_hosts(conn)
    try:
        hid = int(input("\n  输入要删除的主机 ID: ").strip())
    except ValueError:
        return print("  [错误] ID 必须是数字")
    cur = conn.execute("DELETE FROM hosts WHERE id=?", (hid,))
    conn.commit()
    print(f"  [完成] 已删除 ID={hid}" if cur.rowcount else f"  [错误] 未找到 ID={hid}")


# == SSH 工具 ==================================================
def ssh_connect(ip, port, user, pwd):
    """建立 SSH 连接, 返回 SSHClient。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, port=port, username=user, password=pwd, timeout=10)
    return c


def ssh_exec(client, cmd):
    """远程执行命令, 返回 (stdout, stderr, exit_code)。"""
    _, stdout, stderr = client.exec_command(cmd, timeout=30)
    out  = stdout.read().decode().strip()
    err  = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code


# == 巡检与自愈 ================================================
def collect_metrics(client):
    """远程采集 CPU/内存/磁盘指标, 返回字典或 None。"""
    out, err, code = ssh_exec(client, COLLECT_CMD)
    if code != 0:
        print(f"    [警告] 指标采集失败: {err or '目标机未安装 python3-psutil'}")
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"    [警告] JSON 解析异常: {out}")
        return None


def check_and_heal(client, service):
    """检查单个服务状态, 若停止则自动重启, 返回最终状态字符串。"""
    out, _, _ = ssh_exec(client, f"systemctl is-active {service}")
    status = out.strip().lower()
    if status == "active":
        print(f"    [正常] {service}: 运行中")
        return "active"
    # 服务异常, 触发告警并自动重启
    print(f"    [告警] {service}: {status}  -- 正在自动重启...")
    _, err, code = ssh_exec(client, f"sudo systemctl restart {service}")
    if code != 0:
        print(f"    [失败] {service} 重启失败: {err}")
        return "重启失败"
    time.sleep(2)
    out2, _, _ = ssh_exec(client, f"systemctl is-active {service}")
    if out2.strip().lower() == "active":
        print(f"    [恢复] {service}: 已成功重启")
        return "已恢复"
    print(f"    [失败] {service}: 重启后仍异常 ({out2.strip()})")
    return "重启失败"


def inspect_all(conn):
    """遍历数据库中所有主机, 执行完整巡检。"""
    rows = conn.execute("SELECT ip,port,user,password,services FROM hosts").fetchall()
    if not rows:
        return print("  (暂无主机记录, 请先添加主机)")

    print(f"\n{'='*56}")
    print(f"  开始巡检 {len(rows)} 台主机")
    print(f"{'='*56}")

    results = []
    for ip, port, user, pwd, svcs in rows:
        tag = f"{user}@{ip}:{port}"
        print(f"\n  --- {tag} ---")

        try:
            client = ssh_connect(ip, port, user, pwd)
        except Exception as e:
            print(f"    [错误] SSH 连接失败: {e}")
            results.append((tag, "连接失败", {}))
            continue

        svc_results = {}
        try:
            # 1) 采集资源指标
            m = collect_metrics(client)
            if m:
                for key, label in [("cpu","CPU"), ("mem","内存"), ("disk","磁盘")]:
                    v = m[key]
                    warn = "  <-- 超阈值!" if v > THRESHOLD else ""
                    print(f"    {label}: {v:.1f}%{warn}")

            # 2) 逐个检查并自愈服务
            for svc in svcs.split(","):
                svc = svc.strip()
                if svc:
                    svc_results[svc] = check_and_heal(client, svc)
        finally:
            client.close()

        ok = all(v in ("active", "已恢复") for v in svc_results.values())
        results.append((tag, "正常" if ok else "异常", svc_results))

    # -- 汇总 --
    print(f"\n\n{'='*60}")
    print(f"  巡检汇总报告")
    print(f"{'='*60}")
    print(f"  {'主机':<28} {'状态':<8} {'服务详情'}")
    print(f"  {'─'*26}  {'─'*6}  {'─'*22}")
    for tag, status, svcs in results:
        detail = "  ".join(f"{k}={v}" for k, v in svcs.items()) or "-"
        print(f"  {tag:<28} {status:<8} {detail}")
    ok = sum(1 for _, s, _ in results if s == "正常")
    print(f"\n  共 {len(results)} 台 | 正常 {ok} 台 | 异常 {len(results)-ok} 台")
    print(f"{'='*60}\n")


# == 主菜单 ====================================================
def main():
    print("=" * 46)
    print("  多主机自动化巡检与服务自愈工具")
    print("  paramiko + psutil + sqlite3")
    print("=" * 46)

    conn = init_db()
    menu = {
        "1": ("添加主机",   lambda: add_host(conn)),
        "2": ("主机列表",   lambda: list_hosts(conn)),
        "3": ("删除主机",   lambda: delete_host(conn)),
        "4": ("执行巡检",   lambda: inspect_all(conn)),
    }
    try:
        while True:
            print("\n----- 主菜单 -----")
            for k, (v, _) in menu.items():
                print(f"  {k}. {v}")
            print("  0. 退出")
            print("-" * 20)
            c = input("请选择: ").strip()
            if c == "0":
                break
            if c in menu:
                menu[c][1]()
            else:
                print("  无效选项, 请重新输入")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
