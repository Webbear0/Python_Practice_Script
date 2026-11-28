# ui_login.py -- 管理员登录与网关配置页面
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from api_client import ApiWorker, load_saved_gateway, normalize_gateway, save_gateway


class LoginPage(QWidget):
    """居中卡片式登录页面（网关地址 + 管理员凭据），登录成功后发射凭据信号。"""

    # 信号参数：(gateway, token, username)
    login_succeeded = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: list[ApiWorker] = []
        self._logging = False
        self._init_ui()
        self._load_defaults()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 顶部标识区
        logo = QLabel("OPS")
        logo.setObjectName("LogoIcon")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("掌上运维桌面端")
        title.setObjectName("LogoTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel("集群监控与远程管理控制台")
        desc.setObjectName("LogoDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 登录表单卡片
        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(400)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 30, 32, 30)
        card_layout.setSpacing(14)

        self.gw_input = self._add_field(
            card_layout, "网关地址", "如 http://192.168.1.254 或 http://www.test.com"
        )
        self.user_input = self._add_field(card_layout, "管理员账号", "请输入账号 (默认 admin)")
        self.pass_input = self._add_field(
            card_layout, "登录密码", "请输入密码", is_password=True
        )
        self.pass_input.returnPressed.connect(self._do_login)

        self.err_label = QLabel("")
        self.err_label.setObjectName("ErrorHint")
        self.err_label.setWordWrap(True)
        self.err_label.hide()
        card_layout.addWidget(self.err_label)

        self.login_btn = QPushButton("登  录")
        self.login_btn.setObjectName("PrimaryBtn")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setMinimumHeight(42)
        self.login_btn.clicked.connect(self._do_login)
        card_layout.addWidget(self.login_btn)

        footer = QLabel("OPS Monitor | Nginx + Gunicorn + Flask + PyQt6")
        footer.setObjectName("FooterText")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        root.addStretch()
        root.addWidget(logo)
        root.addWidget(title)
        root.addWidget(desc)
        root.addSpacing(24)

        card_row = QHBoxLayout()
        card_row.addStretch()
        card_row.addWidget(card)
        card_row.addStretch()
        root.addLayout(card_row)

        root.addSpacing(28)
        root.addWidget(footer)
        root.addStretch()

    def _add_field(
        self, layout: QVBoxLayout, label_text: str, placeholder: str, is_password: bool = False
    ) -> QLineEdit:
        lbl = QLabel(label_text)
        lbl.setObjectName("FieldLabel")
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(38)
        if is_password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(lbl)
        layout.addWidget(edit)
        return edit

    def _load_defaults(self):
        saved = load_saved_gateway()
        if saved:
            self.gw_input.setText(saved)

    def reset_state(self):
        """切回登录页时重置密码输入和错误提示。"""
        self.pass_input.clear()
        self.err_label.hide()
        self._set_loading(False)

    def _set_loading(self, busy: bool):
        self._logging = busy
        self.login_btn.setEnabled(not busy)
        self.login_btn.setText("登录中..." if busy else "登  录")

    def _show_error(self, msg: str):
        self.err_label.setText(msg)
        self.err_label.show()

    def _do_login(self):
        if self._logging:
            return
        gw = normalize_gateway(self.gw_input.text())
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()

        if not gw:
            return self._show_error("请输入网关地址")
        if not user or not pwd:
            return self._show_error("请输入管理员账号和密码")

        self.err_label.hide()
        self._set_loading(True)

        worker = ApiWorker(
            "POST",
            f"{gw}/api/login",
            json_data={"username": user, "password": pwd},
            timeout=10,
        )
        self._workers.append(worker)
        worker.finished.connect(
            lambda ok, code, data, err, w=worker, g=gw: self._on_login_done(w, g, ok, code, data, err)
        )
        worker.start()

    def _on_login_done(
        self, worker: ApiWorker, gateway: str, ok: bool, code: int, data: object, err: str
    ):
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()
        self._set_loading(False)

        if not ok:
            return self._show_error(err)

        if code == 200 and isinstance(data, dict) and data.get("success"):
            token = data.get("token", "")
            username = data.get("username", "admin")
            save_gateway(gateway)
            self.gw_input.setText(gateway)
            self.login_succeeded.emit(gateway, token, username)
        else:
            msg = data.get("message", "账号或密码错误") if isinstance(data, dict) else "登录失败"
            self._show_error(msg)

    def wait_workers(self):
        """等待所有未结束的请求线程退出，避免关闭窗口时崩溃。"""
        for w in list(self._workers):
            w.wait(1000)
