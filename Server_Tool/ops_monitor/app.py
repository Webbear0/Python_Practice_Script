# app.py -- Flask Web 主程序 (门户 + 监控看板)
# Gunicorn 启动: gunicorn -b 127.0.0.1:8000 app:app
import json
from collections import defaultdict
from flask import Flask, render_template
from pyecharts.charts import Bar, Line
from pyecharts import options as opts
from db_helper import init_local_db, get_db_server, get_latest_status, get_history

app = Flask(__name__)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
