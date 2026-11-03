# collector.py -- 后台定时采集与告警总控脚本
# 功能: 首次运行引导配置 -> 定时 SSH 采集 -> 服务自愈 -> MariaDB 入库 -> 邮件告警
import json, time, paramiko
from db_helper import (init_local_db, has_config, save_db_server, save_host,
                        get_db_server, get_all_hosts, init_remote_db, insert_status,
                        cleanup_old_data)
from mail_alert import send_alert

# 远程一行 Python 命令: 在目标机调用 psutil 采集指标并以 JSON 返回
COLLECT_CMD = (
    "python3 -c '"
    "import psutil,json,socket; d=psutil.disk_usage(\"/\"); "
    "print(json.dumps({\"cpu\":psutil.cpu_percent(interval=1),"
    "\"mem\":psutil.virtual_memory().percent,"
    "\"disk\":round(d.used/d.total*100,1),"
    "\"hostname\":socket.gethostname()}))"
    "'"
)
THRESHOLD = 80      # 资源告警阈值 (%)
INTERVAL  = 30      # 采集间隔 (秒)
CLEANUP_EVERY = 100 # 每 N 轮清理一次历史数据
KEEP_DAYS = 30      # 保留最近 N 天的数据


# == SSH 工具 ==================================================
def ssh_exec(ip, user, pwd, cmd):
    """SSH 远程执行命令, 返回 (stdout, stderr, exit_code)。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, port=22, username=user, password=pwd, timeout=10)
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    out  = stdout.read().decode().strip()
    err  = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    c.close()
    return out, err, code


# == 首次运行引导 ==============================================
def first_run_setup():
    """首次运行: 引导用户输入数据库服务器和被监控主机信息。"""
    print("=" * 50)
    print("  首次运行 -- 初始化监控配置")
    print("=" * 50)

    # 1) MariaDB 数据库服务器
    print("\n-- 数据库服务器 --")
    db_ip  = input("  MariaDB 服务器 IP (如 172.16.10.254): ").strip()
    db_svc = input("  该服务器需监控的服务 (逗号分隔, 如 apache2,mariadb): ").strip()
    save_db_server(db_ip, db_svc)
    save_host(db_ip, db_svc, hostname="SQL_server")
    print(f"  -> 已保存数据库服务器: {db_ip}")

    # 2) 其他被监控服务器 (循环输入)
    print("\n-- 添加其他被监控服务器 (直接回车结束) --")
    idx = 1
    while True:
        ip = input(f"\n  服务器 {idx} IP (回车结束): ").strip()
        if not ip:
            break
        name = input(f"  主机名 [server{idx:02d}]: ").strip() or f"server{idx:02d}"
        svcs = input(f"  监控服务 (逗号分隔): ").strip()
        if svcs:
            save_host(ip, svcs, hostname=name)
            print(f"  -> 已保存: {name} ({ip})")
            idx += 1

    total = len(get_all_hosts())
    print(f"\n  配置完成, 共 {total} 台主机 (含数据库服务器)")


# == 单机采集与自愈 ============================================
def collect_one(host, db_info):
    """对一台主机执行: 采集指标 -> 检查服务 -> 自愈 -> 入库 -> 告警。"""
    ip, user, pwd = host["ip"], host["user"], host["password"]
    tag = host["hostname"] or ip
    print(f"\n  --- {tag} ({ip}) ---")
    alerts = []

    # 1) 远程采集 CPU/内存/磁盘
    try:
        out, err, code = ssh_exec(ip, user, pwd, COLLECT_CMD)
    except Exception as e:
        print(f"    [错误] SSH 连接失败: {e}")
        return

    if code != 0:
        print(f"    [警告] 采集失败: {err or '目标机未安装 python3-psutil'}")
        return

    try:
        m = json.loads(out)
    except json.JSONDecodeError:
        print(f"    [警告] JSON 解析失败: {out}")
        return

    hostname = m.get("hostname", tag)
    for key, label in [("cpu", "CPU"), ("mem", "内存"), ("disk", "磁盘")]:
        v = m[key]
        if v > THRESHOLD:
            alerts.append(f"{label}使用率 {v:.1f}% 超过阈值 {THRESHOLD}%")
            print(f"    {label}: {v:.1f}%  <-- 超阈值!")
        else:
            print(f"    {label}: {v:.1f}%")

    # 2) 服务状态检查与自愈
    svc_results = {}
    for svc in host["services"].split(","):
        svc = svc.strip()
        if not svc:
            continue
        try:
            out2, _, _ = ssh_exec(ip, user, pwd, f"systemctl is-active {svc}")
            status = out2.strip().lower()
            if status == "active":
                print(f"    [正常] {svc}: 运行中")
                svc_results[svc] = "active"
            else:
                print(f"    [告警] {svc}: {status} -- 正在自动重启...")
                ssh_exec(ip, user, pwd, f"systemctl restart {svc}")
                time.sleep(2)
                out3, _, _ = ssh_exec(ip, user, pwd, f"systemctl is-active {svc}")
                if out3.strip().lower() == "active":
                    print(f"    [恢复] {svc}: 重启成功")
                    svc_results[svc] = "已恢复"
                    alerts.append(f"服务 {svc} 异常, 已自动重启恢复")
                else:
                    print(f"    [失败] {svc}: 重启后仍异常")
                    svc_results[svc] = "异常"
                    alerts.append(f"服务 {svc} 重启失败, 需人工处理!")
        except Exception as e:
            print(f"    [错误] 服务 {svc} 检查失败: {e}")
            svc_results[svc] = "检查失败"

    svc_str = ", ".join(f"{k}={v}" for k, v in svc_results.items())

    # 3) 写入 MariaDB
    try:
        insert_status(db_info, hostname, ip, m["cpu"], m["mem"], m["disk"], svc_str)
    except Exception as e:
        print(f"    [警告] MariaDB 入库失败: {e}")

    # 4) 触发告警邮件
    if alerts:
        subject = f"[运维告警] {hostname} ({ip})"
        body  = f"主机: {hostname} ({ip})\n"
        body += f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        body += "\n".join(f"  - {a}" for a in alerts)
        body += f"\n\nCPU: {m['cpu']:.1f}%  内存: {m['mem']:.1f}%  磁盘: {m['disk']:.1f}%"
        body += f"\n服务状态: {svc_str}"
        send_alert(subject, body)


# == 主入口 ====================================================
def main():
    init_local_db()

    # 首次运行引导配置
    if not has_config():
        first_run_setup()

    db_info = get_db_server()
    if not db_info:
        return print("[错误] 未找到数据库服务器配置, 请删除 local_config.db 后重新运行")

    # 初始化 MariaDB 远程数据库
    try:
        init_remote_db(db_info)
        print("[完成] MariaDB 监控数据库 (ops_monitor) 已就绪")
    except Exception as e:
        return print(f"[错误] MariaDB 初始化失败: {e}")

    print(f"\n开始定时巡检 (间隔 {INTERVAL} 秒, Ctrl+C 停止)\n")

    try:
        round_count = 0
        while True:
            round_count += 1
            print(f"\n{'='*50}")
            print(f"  巡检时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}")
            hosts = get_all_hosts()
            for host in hosts:
                collect_one(host, db_info)
            # 定期清理历史数据
            if round_count % CLEANUP_EVERY == 0:
                try:
                    n = cleanup_old_data(db_info, KEEP_DAYS)
                    if n:
                        print(f"\n  [清理] 已删除 {n} 条 {KEEP_DAYS} 天前的历史数据")
                except Exception as e:
                    print(f"\n  [清理] 失败: {e}")
            print(f"\n  -- 本轮完成, {INTERVAL} 秒后下一轮 --")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n\n巡检已停止")


if __name__ == "__main__":
    main()
