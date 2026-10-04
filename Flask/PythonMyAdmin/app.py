"""
PythonMyAdmin —— 基于 Flask 的迷你版 phpMyAdmin
================================================
功能：连接 MySQL / MariaDB，新建数据库，对表数据进行增删改查

运行：
  .venv\\Scripts\\python.exe Flask\\PythonMyAdmin\\app.py
  浏览器打开 http://127.0.0.1:5000

内网安全措施：
  - 所有值参数化；库/表/字段名先与数据库元数据比对，再用反引号转义
  - 数据库密码只保存在服务端内存，Cookie 中只有随机 token
  - 所有 POST 请求校验 CSRF 令牌；Cookie 设置 HttpOnly + SameSite=Strict
  - 空闲 30 分钟自动退出；同一 IP 登录失败 5 次锁定 5 分钟
  - 安全响应头（CSP 禁止内联脚本、禁止被 iframe 嵌入、禁止缓存）
  - 关闭 debug；默认只监听本机，需内网访问时设置环境变量 PMA_HOST=0.0.0.0
"""

import os
import re
import secrets
import time
from functools import wraps

import pymysql
from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.config.update(
    SECRET_KEY=secrets.token_hex(32),  # 每次启动随机生成，重启后需重新登录
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
)

PAGE_SIZE = 20                  # 每页行数
IDLE_TIMEOUT = 30 * 60          # 空闲超时（秒）
MAX_FAILS, LOCK_SECONDS = 5, 300
SYSTEM_DBS = {"information_schema", "mysql", "performance_schema", "sys"}
CHARSETS = ["utf8mb4", "utf8", "latin1", "gbk"]
DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

CONNS = {}  # token -> 连接信息（含密码，仅存在服务端内存）
FAILS = {}  # ip -> (失败次数, 首次失败时间)


# ══════════════════════════════════════════════
# 数据库工具函数
# ══════════════════════════════════════════════
def connect(info=None, database=None):
    info = info or g.info
    return pymysql.connect(
        host=info["host"], port=info["port"], user=info["user"],
        password=info["password"], database=database, charset="utf8mb4",
        connect_timeout=5, cursorclass=pymysql.cursors.DictCursor,
    )


def run(sql, args=(), write=False):
    """执行一条 SQL：读操作返回结果行，写操作提交并返回影响行数"""
    conn = connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute(sql, args)  # 始终传 args，配合 q() 中 % 的转义
            if write:
                conn.commit()
                return n
            return cur.fetchall()
    finally:
        conn.close()


def q(name):
    """转义标识符：反引号包裹，内部反引号加倍；% 加倍以适配 pymysql 的格式化"""
    return "`" + name.replace("`", "``").replace("%", "%%") + "`"


def check_db(db):
    if db not in [r["Database"] for r in run("SHOW DATABASES")]:
        abort(404, "数据库不存在")


def table_meta(db, table):
    """校验库和表是否存在，返回 (字段列表, 主键列表)"""
    check_db(db)
    tables = [list(r.values())[0] for r in run(f"SHOW TABLES FROM {q(db)}")]
    if table not in tables:
        abort(404, "数据表不存在")
    cols = run(f"SHOW COLUMNS FROM {q(db)}.{q(table)}")
    for c in cols:
        t = c["Type"].lower()
        c["binary"] = "blob" in t or "binary" in t
        c["auto"] = "auto_increment" in c["Extra"]
    keys = run(f"SHOW KEYS FROM {q(db)}.{q(table)} WHERE Key_name = 'PRIMARY'")
    pks = [k["Column_name"] for k in sorted(keys, key=lambda k: k["Seq_in_index"])]
    return cols, pks


def pk_where(pks):
    """根据 URL 中的主键参数生成 WHERE 子句"""
    if not pks:
        abort(400, "该表没有主键，无法定位单行数据")
    vals = [request.args.get(k) for k in pks]
    if None in vals:
        abort(400, "缺少主键参数")
    return " AND ".join(f"{q(k)} = %s" for k in pks), vals


def read_form(cols, is_insert):
    """读取表单：勾选 NULL 写入空值；新增时留空的字段交给数据库默认值"""
    data = {}
    for i, c in enumerate(cols):
        if c["binary"]:
            continue
        if request.form.get(f"n{i}"):
            data[c["Field"]] = None
            continue
        value = request.form.get(f"f{i}", "")
        if is_insert and value == "":
            continue
        data[c["Field"]] = value
    return data


# ══════════════════════════════════════════════
# 安全：登录校验、CSRF、响应头、登录限流
# ══════════════════════════════════════════════
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = session.get("token")
        info = CONNS.get(token)
        if not info or time.time() - info["last"] > IDLE_TIMEOUT:
            CONNS.pop(token, None)
            session.pop("token", None)
            flash("请先登录（或登录已超时）")
            return redirect(url_for("login"))
        info["last"] = time.time()
        g.info = info
        return view(*args, **kwargs)
    return wrapper


@app.before_request
def csrf_protect():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST":
        if not secrets.compare_digest(request.form.get("csrf", ""), session["csrf"]):
            abort(400, "CSRF 校验失败，请刷新页面后重试")


@app.after_request
def secure_headers(resp):
    resp.headers["Content-Security-Policy"] = "default-src 'self'"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def is_locked(ip):
    count, first = FAILS.get(ip, (0, 0))
    if time.time() - first > LOCK_SECONDS:
        FAILS.pop(ip, None)
        return False
    return count >= MAX_FAILS


def record_fail(ip):
    count, first = FAILS.get(ip, (0, time.time()))
    FAILS[ip] = (count + 1, first)


app.jinja_env.globals["csrf_token"] = lambda: session.get("csrf", "")


@app.template_filter("cell")
def cell(value):
    """表格单元格显示：二进制显示长度，长文本截断"""
    if isinstance(value, (bytes, bytearray)):
        return f"[二进制 {len(value)} 字节]"
    text = str(value)
    return text if len(text) <= 80 else text[:80] + "…"


@app.errorhandler(HTTPException)
@app.errorhandler(pymysql.MySQLError)
def show_error(e):
    if isinstance(e, HTTPException):
        code, msg = e.code, e.description
    else:
        code, msg = 500, f"数据库错误：{e.args[-1] if e.args else e}"
    ref = request.referrer or ""
    back = ref if ref.startswith(request.host_url) else url_for("databases")
    return render_template("error.html", code=code, msg=msg, back=back), code


# ══════════════════════════════════════════════
# 路由：登录 / 退出
# ══════════════════════════════════════════════
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", form={})

    ip = request.remote_addr
    if is_locked(ip):
        flash(f"登录失败次数过多，请 {LOCK_SECONDS // 60} 分钟后再试")
        return render_template("login.html", form=request.form)
    try:
        port = int(request.form.get("port") or 3306)
        if not 1 <= port <= 65535:
            raise ValueError("端口范围应为 1-65535")
        info = {"host": request.form.get("host", "").strip(), "port": port,
                "user": request.form.get("user", "").strip(),
                "password": request.form.get("password", "")}
        connect(info).close()  # 测试连接
    except (ValueError, pymysql.MySQLError) as e:
        record_fail(ip)
        msg = e.args[-1] if isinstance(e, pymysql.MySQLError) and e.args else e
        flash(f"连接失败：{msg}")
        return render_template("login.html", form=request.form)

    now = time.time()
    for t in [t for t, i in CONNS.items() if now - i["last"] > IDLE_TIMEOUT]:
        CONNS.pop(t, None)  # 顺便清理超时的连接信息
    FAILS.pop(ip, None)
    token = secrets.token_urlsafe(32)
    CONNS[token] = {**info, "last": now}
    session.clear()  # 防止会话固定
    session["token"] = token
    session["csrf"] = secrets.token_hex(16)
    return redirect(url_for("databases"))


@app.route("/logout", methods=["POST"])
def logout():
    CONNS.pop(session.get("token"), None)
    session.clear()
    return redirect(url_for("login"))


# ══════════════════════════════════════════════
# 路由：数据库与数据表
# ══════════════════════════════════════════════
@app.route("/")
@login_required
def databases():
    dbs = run("""
        SELECT s.SCHEMA_NAME AS name, s.DEFAULT_CHARACTER_SET_NAME AS charset,
               COUNT(t.TABLE_NAME) AS tables
        FROM information_schema.SCHEMATA s
        LEFT JOIN information_schema.TABLES t ON t.TABLE_SCHEMA = s.SCHEMA_NAME
        GROUP BY s.SCHEMA_NAME, s.DEFAULT_CHARACTER_SET_NAME
        ORDER BY s.SCHEMA_NAME
    """)
    return render_template("databases.html", dbs=dbs, charsets=CHARSETS, system=SYSTEM_DBS)


@app.route("/create_db", methods=["POST"])
@login_required
def create_db():
    name = request.form.get("name", "").strip()
    charset = request.form.get("charset", "")
    if not DB_NAME_RE.match(name):
        abort(400, "库名只能包含字母、数字、下划线，长度 1-64")
    if charset not in CHARSETS:
        abort(400, "不支持的字符集")
    run(f"CREATE DATABASE {q(name)} CHARACTER SET {charset}", write=True)
    flash(f"数据库 {name} 创建成功")
    return redirect(url_for("tables", db=name))


@app.route("/db/<db>")
@login_required
def tables(db):
    check_db(db)
    rows = run("""
        SELECT t.TABLE_NAME AS name, t.TABLE_TYPE AS type, t.ENGINE AS engine,
               t.TABLE_ROWS AS row_count, t.TABLE_COMMENT AS comment,
               EXISTS(SELECT 1 FROM information_schema.TABLE_CONSTRAINTS c
                      WHERE c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
                        AND c.CONSTRAINT_TYPE = 'PRIMARY KEY') AS has_pk
        FROM information_schema.TABLES t
        WHERE t.TABLE_SCHEMA = %s
        ORDER BY t.TABLE_NAME
    """, (db,))
    return render_template("tables.html", db=db, tables=rows)


# ══════════════════════════════════════════════
# 路由：表数据增删改查
# ══════════════════════════════════════════════
@app.route("/db/<db>/<table>")
@login_required
def browse(db, table):
    """查：分页浏览"""
    cols, pks = table_meta(db, table)
    page = max(request.args.get("page", 1, type=int), 1)
    total = run(f"SELECT COUNT(*) AS n FROM {q(db)}.{q(table)}")[0]["n"]
    order = "ORDER BY " + ", ".join(map(q, pks)) if pks else ""
    rows = run(f"SELECT * FROM {q(db)}.{q(table)} {order} LIMIT %s OFFSET %s",
               (PAGE_SIZE, (page - 1) * PAGE_SIZE))
    items = [{"row": r, "pk": {k: r[k] for k in pks}} for r in rows]
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    return render_template("rows.html", db=db, table=table, cols=cols, pks=pks,
                           items=items, total=total, page=page, pages=pages)


@app.route("/db/<db>/<table>/insert", methods=["GET", "POST"])
@login_required
def insert(db, table):
    """增"""
    cols, pks = table_meta(db, table)
    if request.method == "POST":
        data = read_form(cols, is_insert=True)
        fields = ", ".join(map(q, data))
        marks = ", ".join(["%s"] * len(data))
        run(f"INSERT INTO {q(db)}.{q(table)} ({fields}) VALUES ({marks})",
            list(data.values()), write=True)
        flash("新增成功")
        return redirect(url_for("browse", db=db, table=table))
    return render_template("form.html", db=db, table=table, cols=cols, pks=pks,
                           row={}, mode="insert")


@app.route("/db/<db>/<table>/edit", methods=["GET", "POST"])
@login_required
def edit(db, table):
    """改：按主键定位单行"""
    cols, pks = table_meta(db, table)
    where, keys = pk_where(pks)
    if request.method == "POST":
        data = read_form(cols, is_insert=False)
        if not data:
            abort(400, "没有可修改的字段")
        sets = ", ".join(f"{q(k)} = %s" for k in data)
        n = run(f"UPDATE {q(db)}.{q(table)} SET {sets} WHERE {where} LIMIT 1",
                list(data.values()) + keys, write=True)
        flash("修改成功" if n else "数据没有变化")
        return redirect(url_for("browse", db=db, table=table))
    rows = run(f"SELECT * FROM {q(db)}.{q(table)} WHERE {where} LIMIT 1", keys)
    if not rows:
        abort(404, "该行数据不存在")
    return render_template("form.html", db=db, table=table, cols=cols, pks=pks,
                           row=rows[0], mode="edit")


@app.route("/db/<db>/<table>/delete", methods=["POST"])
@login_required
def delete(db, table):
    """删：按主键删除单行"""
    cols, pks = table_meta(db, table)
    where, keys = pk_where(pks)
    n = run(f"DELETE FROM {q(db)}.{q(table)} WHERE {where} LIMIT 1", keys, write=True)
    flash("删除成功" if n else "该行数据不存在")
    return redirect(url_for("browse", db=db, table=table))


if __name__ == "__main__":
    # debug 必须关闭：Werkzeug 调试器可以在网页上执行任意代码
    app.run(host=os.environ.get("PMA_HOST", "127.0.0.1"), port=5000, debug=False)
