# app.py -- Flask Web 主程序 (门户 + 监控看板 + API 接口)
# Gunicorn 启动: gunicorn -b 127.0.0.1:8000 app:app
import json, re, paramiko
from collections import defaultdict
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from pyecharts.charts import Bar, Line
from pyecharts import options as opts
from db_helper import (init_local_db, get_db_server, get_latest_status,
                        get_history, get_host_by_ip)

app = Flask(__name__)
CORS(app)  # 启用跨域, 允许 uni-app 前端调用


def chart_json(chart):
    """将 pyecharts 图表转为 JSON 字符串, 兼容不同版本返回类型。"""
    result = chart.dump_options()
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


def build_bar(data):
    """当前资源使用率柱状图。"""
    names = [d["hostname"] for d in data]
    bar = (
        Bar()
        .add_xaxis(names)
        .add_yaxis("CPU (%)",  [round(d["cpu"], 1) for d in data])
        .add_yaxis("内存 (%)", [round(d["mem"], 1) for d in data])
        .add_yaxis("磁盘 (%)", [round(d["disk"], 1) for d in data])
        .set_global_opts(
            title_opts=opts.TitleOpts(title="当前资源使用率"),
            yaxis_opts=opts.AxisOpts(name="%", max_=100),
            tooltip_opts=opts.TooltipOpts(trigger="axis"),
        )
    )
    return chart_json(bar)


def build_line(history):
    """CPU 历史趋势折线图。"""
    grouped = defaultdict(list)
    for h in history:
        grouped[h["hostname"]].append(h)

    all_times = sorted(set(h["time"] for h in history))
    display_times = all_times[-20:]

    line = Line()
    line.add_xaxis(display_times)
    for hostname, records in grouped.items():
        time_cpu = {r["time"]: r["cpu"] for r in records}
        cpu_data = [time_cpu.get(t) for t in display_times]
        line.add_yaxis(hostname, cpu_data, is_smooth=True,
                       linestyle_opts=opts.LineStyleOpts(width=2))
    line.set_global_opts(
        title_opts=opts.TitleOpts(title="CPU 使用率"),
        yaxis_opts=opts.AxisOpts(name="%", max_=100),
        xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=45)),
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
    )
    return chart_json(line)


@app.route("/")
def portal():
    """门户主页 -- 导航至各业务节点。"""
    return render_template("portal.html")


@app.route("/ops")
def ops():
    """运维监控看板 -- 从 MariaDB 读取数据, pyecharts 生成图表。"""
    init_local_db()
    db_info = get_db_server()
    if not db_info:
        return "<h2>未找到数据库配置, 请先运行 collector.py 完成初始化</h2>"

    try:
        latest  = get_latest_status(db_info)
        history = get_history(db_info, limit=60)
    except Exception as e:
        return f"<h2>数据库连接失败: {e}</h2>"

    bar_opts  = build_bar(latest)   if latest  else "{}"
    line_opts = build_line(history) if history else "{}"

    return render_template("index.html", servers=latest,
                           bar_options=bar_opts, line_options=line_opts)


# == SSH 工具 (供 /api/restart 使用) ============================
def _ssh_exec(ip, user, pwd, cmd):
    """SSH 远程执行命令, 返回 (stdout, stderr, exit_code)。"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, port=22, username=user, password=pwd, timeout=10)
    try:
        _, stdout, stderr = c.exec_command(cmd, timeout=30)
        out  = stdout.read().decode().strip()
        err  = stderr.read().decode().strip()
        code = stdout.channel.recv_exit_status()
    finally:
        c.close()
    return out, err, code


# == API 接口 (供 uni-app 前端调用) =============================
@app.route("/api/status")
def api_status():
    """GET /api/status -- 返回所有主机最新监控数据 (JSON)。"""
    init_local_db()
    db_info = get_db_server()
    if not db_info:
        return jsonify({"error": "未找到数据库配置"}), 500
    try:
        data = get_latest_status(db_info)
    except Exception as e:
        return jsonify({"error": f"数据库连接失败: {e}"}), 500
    return jsonify(data)


@app.route("/api/restart", methods=["POST"])
def api_restart():
    """POST /api/restart -- 远程重启指定主机的服务。
    请求体: {"ip": "172.16.10.10", "service": "apache2"}
    """
    body = request.get_json(silent=True)
    if not body or "ip" not in body or "service" not in body:
        return jsonify({"success": False, "message": "缺少 ip 或 service 参数"}), 400

    ip  = body["ip"].strip()
    svc = body["service"].strip()

    # 防命令注入: 服务名只允许字母、数字、连字符、下划线
    if not re.match(r'^[a-zA-Z0-9_\-]+$', svc):
        return jsonify({"success": False, "message": "服务名包含非法字符"}), 400

    # 从 SQLite 查询目标主机的 SSH 凭据
    host = get_host_by_ip(ip)
    if not host:
        return jsonify({"success": False, "message": f"未找到主机: {ip}"}), 404

    # 远程执行 systemctl restart
    try:
        out, err, code = _ssh_exec(ip, host["user"], host["password"],
                                   f"systemctl restart {svc}")
        if code == 0:
            return jsonify({"success": True, "message": f"{svc} 重启成功"})
        else:
            return jsonify({"success": False, "message": f"重启失败: {err or out}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"SSH 连接失败: {e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
