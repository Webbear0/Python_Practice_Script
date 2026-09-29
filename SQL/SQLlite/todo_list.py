#coding=utf-8
"""SQLite 待办事项清单"""

import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "todo.db")


def init():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT    NOT NULL,
        done    INTEGER DEFAULT 0,
        created TEXT    DEFAULT (datetime('now','localtime'))
    )""")
    conn.commit()
    return conn


def show(conn):
    """展示所有任务"""
    rows = conn.execute("SELECT id, content, done, created FROM tasks ORDER BY done, id").fetchall()
    if not rows:
        print("\n  (空空如也，快添加一条任务吧)")
        return
    print(f"\n {'ID':>4}  {'状态':<4} {'内容':<20} {'创建时间'}")
    print(" " + "-" * 55)
    for r in rows:
        status = "[OK]" if r[2] else "[  ]"
        print(f" {r[0]:>4}  {status:<4} {r[1]:<20} {r[3]}")
    total = len(rows)
    done = sum(1 for r in rows if r[2])
    print(f"\n  共 {total} 条，已完成 {done} 条，未完成 {total - done} 条")


def add(conn):
    text = input("  输入任务内容: ").strip()
    if not text:
        print("  内容不能为空"); return
    conn.execute("INSERT INTO tasks (content) VALUES (?)", (text,))
    conn.commit()
    print(f"  >> 已添加: {text}")


def done(conn):
    tid = input("  输入要完成的任务ID: ").strip()
    cur = conn.execute("UPDATE tasks SET done = 1 WHERE id = ? AND done = 0", (tid,))
    conn.commit()
    print("  >> 已标记完成" if cur.rowcount else "  >> 任务不存在或已完成")


def delete(conn):
    tid = input("  输入要删除的任务ID: ").strip()
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
    conn.commit()
    print("  >> 已删除" if cur.rowcount else "  >> 任务不存在")


def clear_done(conn):
    cur = conn.execute("DELETE FROM tasks WHERE done = 1")
    conn.commit()
    print(f"  >> 已清除 {cur.rowcount} 条已完成任务")


if __name__ == "__main__":
    db = init()
    MENU = """
===== Todo List =====
 1. 查看任务
 2. 添加任务
 3. 完成任务
 4. 删除任务
 5. 清除已完成
 0. 退出
====================="""
    while True:
        print(MENU)
        ch = input(" 请选择: ").strip()
        if   ch == "1": show(db)
        elif ch == "2": add(db)
        elif ch == "3": done(db)
        elif ch == "4": delete(db)
        elif ch == "5": clear_done(db)
        elif ch == "0": print(" 再见!"); break
        else: print(" 无效选项")
    db.close()