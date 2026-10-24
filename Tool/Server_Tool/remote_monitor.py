# 远程多主机健康巡检与 Apache 自愈工具
# 功能: SSH 远程采集 CPU/内存/磁盘, 检查 Apache2/MySQL 状态, Apache 停止时自动重启
# 前置: 目标 Ubuntu 主机需安装 python3-psutil (apt install python3-psutil)
import json, sys, time, getpass, paramiko

# ── 远程命令 ──────────────────────────────────────────────────
# 在目标机上一行调用 psutil, 以 JSON 返回 CPU/内存/磁盘占用率
COLLECT_CMD = (
    "python3 -c '"
    "import psutil,json; d=psutil.disk_usage(\"/\"); "
    "print(json.dumps({\"cpu\":psutil.cpu_percent(interval=1),"
    "\"mem\":psutil.virtual_memory().percent,"
    "\"disk\":round(d.used/d.total*100,1)}))"
    "'"
)
CHECK_APACHE = "systemctl is-active apache2"
CHECK_MYSQL  = "systemctl is-active mysql"
RESTART_APACHE = "sudo systemctl restart apache2"

# 占用率告警阈值 (%)
THRESHOLD = 90


# ── SSH 工具 ──────────────────────────────────────────────────
def ssh_connect(host, port, user, pwd):
    """建立 SSH 连接并返回客户端实例。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=user, password=pwd, timeout=10)
    return client


def ssh_exec(client, cmd):
    """执行远程命令, 返回 (stdout, stderr, exit_code)。"""
    _, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code


# ── 业务函数 ──────────────────────────────────────────────────
def collect_metrics(client):
    """远程采集系统指标, 返回 dict 或 None。"""
    out, err, code = ssh_exec(client, COLLECT_CMD)
    if code != 0:
        print(f"     指标采集失败: {err or '目标机可能未安装 python3-psutil'}")
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"     JSON 解析异常: {out}")
        return None


def check_service(client, cmd):
    """检查服务状态, 返回 active / inactive / 其他。"""
    out, _, _ = ssh_exec(client, cmd)
    return out.strip().lower()


def try_restart_apache(client):
    """尝试远程重启 Apache2, 返回 (成功？, 错误信息)。"""
    _, err, code = ssh_exec(client, RESTART_APACHE)
    if code != 0:
        return False, err
    time.sleep(2)  # 等待服务拉起
    status = check_service(client, CHECK_APACHE)
    return status == "active", f"重启后状态: {status}"


# ── 交互式输入 ────────────────────────────────────────────────
def input_hosts():
    """收集用户输入的主机连接信息, 返回列表。"""
    while True:
        try:
            n = int(input("\n请输入要监控的主机数量: "))
            if n < 1:
                raise ValueError
            break
        except ValueError:
            print("请输入一个正整数。")

    hosts = []
    for i in range(1, n + 1):
        print(f"\n── 主机 {i}/{n} ──")
        host = input("  IP 地址: ").strip()
        port_s = input("  SSH 端口 [22]: ").strip()
        port = int(port_s) if port_s else 22
        user = input("  用户名: ").strip()
        pwd  = getpass.getpass("  密码: ")
        hosts.append({"host": host, "port": port, "user": user, "pwd": pwd})
    return hosts


# ── 单机巡检 ──────────────────────────────────────────────────
def bar(v):
    """根据百分比生成 20 格 ASCII 进度条。"""
    filled = int(v / 5)
    return "█" * filled + "░" * (20 - filled)


def inspect(info):
    """对一台主机执行完整巡检, 返回结果字典。"""
    tag = f"{info['user']}@{info['host']}:{info['port']}"
    print(f"\n{'═' * 56}")
    print(f"  🖥  {tag}")
    print(f"{'═' * 56}")

    try:
        client = ssh_connect(info["host"], info["port"], info["user"], info["pwd"])
    except Exception as e:
        print(f"  X SSH 连接失败: {e}")
        return {"tag": tag, "status": "连接失败"}

    r = {"tag": tag, "status": "正常", "apache": "-", "mysql": "-"}

    try:
        # 1) 采集 CPU / 内存 / 磁盘
        m = collect_metrics(client)
        if m:
            r["metrics"] = m
            for k, label in [("cpu", "CPU"), ("mem", "内存"), ("disk", "磁盘")]:
                v = m[k]
                warn = "  超阈值!" if v > THRESHOLD else ""
                print(f"  [{bar(v)}] {label}: {v:5.1f}%{warn}")

        # 2) 检查 Apache2
        apache = check_service(client, CHECK_APACHE)
        if apache == "active":
            print("   Apache2: 运行中")
            r["apache"] = "active"
        else:
            print(f"  X Apache2: {apache}")
            print("   正在自动重启 Apache2 ...")
            ok, msg = try_restart_apache(client)
            if ok:
                print("   Apache2 已成功恢复!")
                r["apache"] = "已自愈"
            else:
                print(f"  X 自愈失败 — {msg}")
                r["apache"] = "自愈失败"
                r["status"] = "需人工介入"

        # 3) 检查 MySQL
        mysql = check_service(client, CHECK_MYSQL)
        label = "运行中" if mysql == "active" else mysql
        icon  = "V" if mysql == "active" else "！ "
        print(f"  {icon} MySQL:   {label}")
        r["mysql"] = mysql

    finally:
        client.close()

    return r


# ── 汇总报告 ──────────────────────────────────────────────────
def summary(results):
    """打印全部主机的巡检汇总。"""
    w = 60
    print(f"\n\n{'━' * w}")
    print("    巡 检 汇 总 报 告")
    print(f"{'━' * w}")
    hdr = f"  {'主机':<28} {'状态':<10} {'Apache':<10} {'MySQL':<10}"
    print(hdr)
    print(f"  {'─' * 26}  {'─' * 8}  {'─' * 8}  {'─' * 8}")

    for r in results:
        t = r["tag"][:26]
        print(f"  {t:<28} {r['status']:<10} {r['apache']:<10} {r['mysql']:<10}")

    ok = sum(1 for r in results if r["status"] == "正常")
    print(f"\n  共 {len(results)} 台 |  正常 {ok} 台 | ！ 异常 {len(results) - ok} 台")

    problems = [r for r in results if r["status"] != "正常"]
    if problems:
        print("\n  ！  以下主机需要关注:")
        for r in problems:
            print(f"     • {r['tag']} — {r['status']}")
    print(f"{'━' * w}\n")


# ── 主入口 ────────────────────────────────────────────────────
def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║    远程多主机健康巡检与 Apache  自愈工具             ║")
    print("║    paramiko + psutil 联动 · SSH 远程采集与自动恢复   ║")
    print("╚══════════════════════════════════════════════════════╝")

    hosts = input_hosts()
    print(f"\n 开始巡检 {len(hosts)} 台主机 ...\n")

    results = [inspect(h) for h in hosts]
    summary(results)


if __name__ == "__main__":
    main()
