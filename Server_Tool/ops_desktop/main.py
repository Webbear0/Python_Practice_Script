# main.py -- PyQt6 桌面运维客户端主入口
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from ui_dashboard import DashboardPage
from ui_login import LoginPage

DARK_QSS = """
QMainWindow, LoginPage, DashboardPage {
    background-color: #0f172a;
}
QWidget {
    color: #e2e8f0;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
}
QLabel {
    background-color: transparent;
}
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
#LogoIcon { font-size: 32px; font-weight: 800; color: #60a5fa; letter-spacing: 4px; }
#LogoTitle { font-size: 24px; font-weight: 700; color: #f1f5f9; margin-top: 4px; }
#LogoDesc { font-size: 13px; color: #64748b; }
#FooterText { font-size: 12px; color: #475569; }
#FieldLabel { font-size: 12px; color: #94a3b8; }
#ErrorHint { color: #f87171; font-size: 12px; }

#LoginCard, #PanelCard, #TopBar {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
}
#HostCard {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
}
#HostCard:hover {
    border: 1px solid #60a5fa;
}
#HostCardSelected {
    background-color: #1e293b;
    border: 2px solid #3b82f6;
    border-radius: 10px;
}
#ServiceRow {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
}

QLineEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e2e8f0;
}
QLineEdit:focus { border: 1px solid #3b82f6; }

#PrimaryBtn {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}
#PrimaryBtn:hover { background-color: #2563eb; }
#PrimaryBtn:disabled { background-color: #334155; color: #94a3b8; }

#GhostBtn {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 14px;
}
#GhostBtn:hover { border-color: #94a3b8; color: #f1f5f9; }

#DangerBtn {
    background-color: rgba(239, 68, 68, 0.16);
    color: #f87171;
    border: 1px solid #7f1d1d;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 600;
}
#DangerBtn:hover { background-color: #dc2626; color: #ffffff; }
#DangerBtn:disabled { opacity: 0.5; color: #64748b; border-color: #334155; }

#TabBtn {
    background-color: #0f172a;
    color: #94a3b8;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
}
#TabBtn:checked {
    background-color: #3b82f6;
    color: #ffffff;
    border-color: #3b82f6;
    font-weight: 600;
}

#TopTitle { font-size: 16px; font-weight: 700; color: #f1f5f9; }
#TopSub, #StatusHint, #CardHostIp, #MetricLabel { font-size: 12px; color: #94a3b8; }
#SectionTitle { font-size: 14px; font-weight: 600; color: #f1f5f9; }
#CardHostName, #SvcName { font-size: 14px; font-weight: 600; color: #f8fafc; }

#SumDefault { font-size: 22px; font-weight: 700; color: #f1f5f9; }
#SumOk { font-size: 22px; font-weight: 700; color: #22c55e; }
#SumWarn { font-size: 22px; font-weight: 700; color: #ef4444; }
#ValNormal { font-size: 12px; font-weight: 600; color: #cbd5e1; }
#ValWarn { font-size: 12px; font-weight: 600; color: #ef4444; }

#TagOk {
    background-color: rgba(34, 197, 94, 0.15);
    color: #4ade80;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
}
#TagErr {
    background-color: rgba(239, 68, 68, 0.18);
    color: #f87171;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
}

QProgressBar {
    background-color: #0f172a;
    border: none;
    border-radius: 5px;
}
QProgressBar::chunk {
    background-color: #22c55e;
    border-radius: 5px;
}
QProgressBar[danger="true"]::chunk {
    background-color: #ef4444;
}
QScrollArea { background-color: transparent; }
QSplitter::handle { background-color: #0f172a; }
QMessageBox { background-color: #1e293b; color: #e2e8f0; }
QMessageBox QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    min-width: 68px;
}
QMessageBox QPushButton:hover { background-color: #2563eb; }
"""


class MainWindow(QMainWindow):
    """主窗口：负责在登录页与监控主面板间切换，并管理 30 秒自动轮询定时器。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OPS Monitor -- 桌面运维控制台")
        self.resize(1020, 660)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = LoginPage()
        self.dash_page = DashboardPage()
        self.stack.addWidget(self.login_page)  # 索引 0
        self.stack.addWidget(self.dash_page)   # 索引 1

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.dash_page.refresh_all)

        self.login_page.login_succeeded.connect(self._on_login_success)
        self.dash_page.session_expired.connect(self._on_logout)
        self.dash_page.logout_requested.connect(self._on_logout)

    def _on_login_success(self, gateway: str, token: str, username: str):
        self.dash_page.set_session(gateway, token, username)
        self.stack.setCurrentIndex(1)
        self.dash_page.refresh_all()
        self.poll_timer.start(30000)

    def _on_logout(self):
        self.poll_timer.stop()
        self.login_page.reset_state()
        self.stack.setCurrentIndex(0)

    def closeEvent(self, event):
        self.poll_timer.stop()
        self.login_page.wait_workers()
        self.dash_page.wait_workers()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
