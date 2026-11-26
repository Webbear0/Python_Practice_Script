# app.py -- Flask Web 主程序 (门户 + 监控看板 + API 接口)
# Gunicorn 启动: gunicorn -b 127.0.0.1:8000 app:app
import json, re, functools
from collections import defaultdict
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from pyecharts.charts import Bar, Line
from pyecharts import options as opts
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from db_helper import (init_local_db, get_db_server, get_latest_status,
                        get_history, get_history_by_ip, get_host_by_ip, ssh_exec)

app = Flask(__name__)
CORS(app)  # 启用跨域, 允许 uni-app 前端调用

# == Token 鉴权配置 =============================================
SECRET_KEY = "ops-monitor-secret-2026"
token_serializer = URLSafeTimedSerializer(SECRET_KEY)
ADMIN_USER = "admin"
ADMIN_PASS = "123456"
TOKEN_MAX_AGE = 86400  # 24 小时


def token_required(f):
    """鉴权装饰器: 校验 Authorization: Bearer <token>, 缺失/过期/无效返回 401。"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "未提供 Token"}), 401
        try:
            token_serializer.loads(auth[7:], max_age=TOKEN_MAX_AGE)
        except SignatureExpired:
            return jsonify({"error": "Token 已过期, 请重新登录"}), 401
        except BadSignature:
            return jsonify({"error": "Token 无效"}), 401
        return f(*args, **kwargs)
    return decorated


# == 图表工具 ===================================================
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


# == Web 页面路由 (无需鉴权) ====================================
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


# == API 接口 (供 uni-app 前端调用) =============================
@app.route("/api/login", methods=["POST"])
def api_login():
    """POST /api/login -- 管理员登录, 签发 24h Token (无需鉴权)。"""
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "请提供登录信息"}), 400
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    if username == ADMIN_USER and password == ADMIN_PASS:
        token = token_serializer.dumps({"user": username})
        return jsonify({"success": True, "token": token, "username": username})
    return jsonify({"success": False, "message": "账号或密码错误"}), 401


@app.route("/api/status")
@token_required
def api_status():
    """GET /api/status -- 返回所有主机最新监控数据 (需鉴权)。"""
    init_local_db()
    db_info = get_db_server()
    if not db_info:
        return jsonify({"error": "未找到数据库配置"}), 500
    try:
        data = get_latest_status(db_info)
    except Exception as e:
        return jsonify({"error": f"数据库连接失败: {e}"}), 500
    return jsonify(data)


@app.route("/api/history/<ip>")
@token_required
def api_history(ip):
    """GET /api/history/<ip> -- 返回指定主机近 20 条历史记录 (需鉴权)。"""
    init_local_db()
    db_info = get_db_server()
    if not db_info:
        return jsonify({"error": "未找到数据库配置"}), 500
    try:
        data = get_history_by_ip(db_info, ip, limit=20)
    except Exception as e:
        return jsonify({"error": f"数据库连接失败: {e}"}), 500
    return jsonify(data)


@app.route("/api/restart", methods=["POST"])
@token_required
def api_restart():
    """POST /api/restart -- 远程重启指定主机的服务 (需鉴权)。
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
        out, err, code = ssh_exec(ip, host["user"], host["password"],
                                   f"systemctl restart {svc}")
        if code == 0:
            return jsonify({"success": True, "message": f"{svc} 重启成功"})
        else:
            return jsonify({"success": False, "message": f"重启失败: {err or out}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"SSH 连接失败: {e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
