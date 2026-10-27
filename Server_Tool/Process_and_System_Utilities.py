#进程和系统实用程序 -- 基于 psutil 的交互式系统管理工具
import datetime, time, psutil
def fmt(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{u}"
        n /= 1024


def show_procs(procs, n=None):
    print(f"{'PID':>8}  {'CPU%':>6}  {'MEM%':>6}  进程名")
    print("-" * 50)
    for p in (procs[:n] if n else procs):
        print(f"{p['pid']:>8}  {p.get('cpu_percent',0) or 0:>5.1f}%  "
              f"{p.get('memory_percent',0) or 0:>5.1f}%  {p.get('name','')}")

def get_procs():
    ps = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try: ps.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
    return ps

def system_overview():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    net = psutil.net_io_counters()
    boot = datetime.datetime.fromtimestamp(psutil.boot_time())
    up = int(time.time() - psutil.boot_time())
    print(f"\n[CPU] {psutil.cpu_count(logical=False)}核{psutil.cpu_count()}线程  使用率: {cpu}%")
    freq = psutil.cpu_freq()
    if freq: print(f"      频率: {freq.current:.0f} MHz")
    print(f"[内存] {fmt(mem.used)} / {fmt(mem.total)} ({mem.percent}%)")
    print(f"[交换] {fmt(swap.used)} / {fmt(swap.total)} ({swap.percent}%)")
    print(f"[磁盘]")
    for d in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(d.mountpoint)
            print(f"  {d.device:10} {fmt(u.used):>8} / {fmt(u.total):>8} ({u.percent}%) [{d.fstype}]")
        except PermissionError: pass
    print(f"[网络] 发送: {fmt(net.bytes_sent)}  接收: {fmt(net.bytes_recv)}")
    print(f"[系统] 开机: {boot:%Y-%m-%d %H:%M}  已运行: {up//86400}天{up%86400//3600}时{up%3600//60}分  进程: {len(psutil.pids())}")

def top_processes():
    n = int(input("显示前几个?(默认10): ").strip() or 10)
    key = "memory_percent" if input("排序 1-CPU 2-内存(默认1): ").strip() == "2" else "cpu_percent"
    if key == "cpu_percent":
        get_procs(); time.sleep(0.5)  # 首次采样预热
    ps = sorted(get_procs(), key=lambda x: x.get(key, 0) or 0, reverse=True)
    print()
    show_procs(ps, n)

def search_process():
    kw = input("进程名关键词: ").strip().lower()
    if not kw: return print("关键词不能为空")
    found = [p for p in get_procs() if kw in (p.get("name") or "").lower()]
    if not found: return print(f"未找到 '{kw}'")
    print(f"\n找到 {len(found)} 个:")
    show_procs(found)

def kill_process():
    try: pid = int(input("输入PID: ").strip())
    except ValueError: return print("PID必须是数字")
    try:
        p = psutil.Process(pid)
        if input(f"结束 {p.name()}(PID={pid})? (y/N): ").strip().lower() != "y": return
        p.terminate()
        try: p.wait(timeout=3); print("已正常结束")
        except psutil.TimeoutExpired: p.kill(); print("已强制结束")
    except psutil.NoSuchProcess: print("进程不存在")
    except psutil.AccessDenied: print("权限不足, 请以管理员运行")

def realtime_monitor():
    print("实时监控(Ctrl+C 停止)\n")
    try:
        while True:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory().percent
            bar = lambda v: "#" * int(v / 5) + "-" * (20 - int(v / 5))
            print(f"  [{time.strftime('%H:%M:%S')}] CPU[{bar(cpu)}]{cpu:5.1f}%  MEM[{bar(mem)}]{mem:5.1f}%")
    except KeyboardInterrupt: print("\n已停止")

if __name__ == "__main__":
    ops = {"1": ("系统概览", system_overview), "2": ("进程排行", top_processes),
           "3": ("搜索进程", search_process), "4": ("结束进程", kill_process),
           "5": ("实时监控", realtime_monitor)}
    while True:
        print("\n===== 进程和系统实用程序 =====")
        for k, (v, _) in ops.items(): print(f"  {k}. {v}")
        print("  0. 退出\n" + "-" * 30)
        c = input("请选择: ").strip()
        if c == "0": break
        if c in ops: ops[c][1]()