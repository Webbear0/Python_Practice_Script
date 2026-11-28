# ui_dashboard.py -- 监控总览、单机近 20 次自绘趋势图与远程安全重启面板
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from api_client import ApiWorker, parse_services


class TrendChartWidget(QWidget):
    """基于 QPainter 的轻量级自绘柱状图控件（含 80% 警戒线，无 matplotlib 依赖）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[dict] = []
        self._metric = "cpu"
        self.setMinimumHeight(250)

    def set_data(self, records: list[dict], metric: str):
        self._records = records[-20:]
        self._metric = metric
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 42, 16, 28, 34
        plot_w = max(w - pad_l - pad_r, 10)
        plot_h = max(h - pad_t - pad_b, 10)

        # 绘制背景与外框底线
        painter.fillRect(0, 0, w, h, QColor("#0f172a"))
        axis_pen = QPen(QColor("#334155"), 1)
        painter.setPen(axis_pen)
        painter.drawLine(pad_l, pad_t, pad_l, pad_t + plot_h)
        painter.drawLine(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h)

        # Y 轴刻度与水平参考线
        font = QFont("Microsoft YaHei", 8)
        painter.setFont(font)
        for pct in (0, 20, 40, 60, 80, 100):
            y = int(pad_t + plot_h * (1 - pct / 100.0))
            if pct > 0:
                grid_pen = QPen(QColor("#1e293b"), 1)
                painter.setPen(grid_pen)
                painter.drawLine(pad_l + 1, y, pad_l + plot_w, y)
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(2, y - 6, pad_l - 8, 14, Qt.AlignmentFlag.AlignRight, f"{pct}%")

        # 80% 红色虚线警戒线
        y_warn = int(pad_t + plot_h * 0.2)
        warn_pen = QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashLine)
        painter.setPen(warn_pen)
        painter.drawLine(pad_l + 1, y_warn, pad_l + plot_w, y_warn)
        painter.setPen(QColor("#f87171"))
        painter.drawText(pad_l + 6, y_warn - 14, 90, 14, Qt.AlignmentFlag.AlignLeft, "80% 警戒线")

        if not self._records:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.drawText(
                pad_l, pad_t, plot_w, plot_h,
                Qt.AlignmentFlag.AlignCenter, "请选择左侧主机或等待历史采集数据"
            )
            return

        # 绘制柱状条
        n = len(self._records)
        slot_w = plot_w / max(n, 1)
        bar_w = max(min(slot_w * 0.56, 26), 6)

        for idx, rec in enumerate(self._records):
            val = float(rec.get(self._metric, 0) or 0)
            clamped = max(0.0, min(val, 100.0))
            bar_h = max(int(plot_h * (clamped / 100.0)), 2)
            cx = pad_l + (idx + 0.5) * slot_w
            bx = int(cx - bar_w / 2)
            by = int(pad_t + plot_h - bar_h)

            color = QColor("#ef4444") if val > 80 else QColor("#60a5fa")
            painter.fillRect(bx, by, int(bar_w), bar_h, color)

            # 柱顶数值
            painter.setPen(QColor("#e2e8f0"))
            painter.setFont(QFont("Microsoft YaHei", 7))
            painter.drawText(
                int(cx - 18), max(by - 15, 2), 36, 14,
                Qt.AlignmentFlag.AlignCenter, f"{val:.0f}"
            )

            # 底部时间刻度（均匀抽样防相邻时间标签重叠）
            step = 1 if n <= 10 else 2
            if idx % step == 0:
                t_raw = str(rec.get("time", ""))
                t_short = t_raw.split(" ")[-1] if " " in t_raw else t_raw[-5:]
                painter.setPen(QColor("#94a3b8"))
                painter.drawText(
                    int(cx - 22), pad_t + plot_h + 4, 44, 16,
                    Qt.AlignmentFlag.AlignCenter, t_short
                )


class HostCard(QFrame):
    """左侧集群列表中的单台主机状态卡片。"""

    clicked = pyqtSignal(str)

    def __init__(self, host_data: dict, selected: bool = False, parent=None):
        super().__init__(parent)
        self.ip = host_data.get("ip", "")
        self.setObjectName("HostCardSelected" if selected else "HostCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui(host_data)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.ip)
        super().mousePressEvent(event)

    def _build_ui(self, d: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # 头部：主机名 + IP
        head = QHBoxLayout()
        name_lbl = QLabel(d.get("hostname") or self.ip)
        name_lbl.setObjectName("CardHostName")
        ip_lbl = QLabel(self.ip)
        ip_lbl.setObjectName("CardHostIp")
        head.addWidget(name_lbl)
        head.addStretch()
        head.addWidget(ip_lbl)
        layout.addLayout(head)

        # 资源进度条
        for key, label in (("cpu", "CPU"), ("mem", "内存"), ("disk", "磁盘")):
            val = float(d.get(key, 0) or 0)
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl = QLabel(label)
            lbl.setFixedWidth(36)
            lbl.setObjectName("MetricLabel")

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(min(max(val, 0), 100)))
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            bar.setProperty("danger", "true" if val > 80 else "false")

            val_lbl = QLabel(f"{val:.1f}%")
            val_lbl.setFixedWidth(48)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_lbl.setObjectName("ValWarn" if val > 80 else "ValNormal")

            row.addWidget(lbl)
            row.addWidget(bar, 1)
            row.addWidget(val_lbl)
            layout.addLayout(row)

        # 服务状态标签
        svcs = parse_services(d.get("services", ""))
        svc_row = QHBoxLayout()
        svc_row.setSpacing(6)
        for name, status in svcs:
            tag = QLabel(f"{name}: {status}")
            tag.setObjectName("TagOk" if status == "active" else "TagErr")
            svc_row.addWidget(tag)
        svc_row.addStretch()
        layout.addLayout(svc_row)


class DashboardPage(QWidget):
    """监控总览与详情控制主面板。"""

    session_expired = pyqtSignal()
    logout_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gateway = ""
        self.token = ""
        self.username = ""
        self.selected_ip = ""
        self.active_metric = "cpu"
        self._servers: list[dict] = []
        self._history_cache: list[dict] = []
        self._workers: list[ApiWorker] = []
        self._restarting = False

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # ── 1. 顶部控制栏 ──
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 10, 16, 10)

        title_lbl = QLabel("OPS Monitor · 桌面运维控制台")
        title_lbl.setObjectName("TopTitle")

        self.session_lbl = QLabel("")
        self.session_lbl.setObjectName("TopSub")

        self.status_hint = QLabel("就绪")
        self.status_hint.setObjectName("StatusHint")

        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.setObjectName("PrimaryBtn")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_all)

        logout_btn = QPushButton("退出登录")
        logout_btn.setObjectName("GhostBtn")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self._confirm_logout)

        top_layout.addWidget(title_lbl)
        top_layout.addSpacing(16)
        top_layout.addWidget(self.session_lbl)
        top_layout.addStretch()
        top_layout.addWidget(self.status_hint)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addWidget(logout_btn)
        root.addWidget(top_bar)

        # ── 2. 主体左右分栏 ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)

        # 左侧：集群摘要 + 主机卡片滚动区
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        summary_card = QFrame()
        summary_card.setObjectName("PanelCard")
        sum_layout = QHBoxLayout(summary_card)
        sum_layout.setContentsMargins(12, 12, 12, 12)
        self.total_num_lbl = self._add_summary_col(sum_layout, "总节点", "SumDefault")
        self.ok_num_lbl = self._add_summary_col(sum_layout, "正常", "SumOk")
        self.warn_num_lbl = self._add_summary_col(sum_layout, "告警", "SumWarn")
        left_layout.addWidget(summary_card)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()
        self.cards_scroll.setWidget(self.cards_container)
        left_layout.addWidget(self.cards_scroll, 1)

        # 右侧：单机详情（近 20 次趋势图 + 服务安全重启）
        right_panel = QFrame()
        right_panel.setObjectName("PanelCard")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 18, 20, 18)
        right_layout.setSpacing(14)

        detail_head = QHBoxLayout()
        self.detail_title = QLabel("单机监控详情")
        self.detail_title.setObjectName("SectionTitle")
        self.detail_time = QLabel("")
        self.detail_time.setObjectName("TopSub")
        detail_head.addWidget(self.detail_title)
        detail_head.addStretch()
        detail_head.addWidget(self.detail_time)
        right_layout.addLayout(detail_head)

        # 指标切换按钮组
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self.tab_buttons: dict[str, QPushButton] = {}
        for key, text in (("cpu", "CPU 趋势"), ("mem", "内存 趋势"), ("disk", "磁盘 趋势")):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("TabBtn")
            btn.clicked.connect(lambda _chk, m=key: self._switch_metric(m))
            self.tab_buttons[key] = btn
            tab_row.addWidget(btn)
        tab_row.addStretch()
        self.tab_buttons["cpu"].setChecked(True)
        right_layout.addLayout(tab_row)

        # 自绘柱状图
        self.chart = TrendChartWidget()
        right_layout.addWidget(self.chart, 3)

        # 服务管理与重启区
        svc_title = QLabel("服务管理与安全重启")
        svc_title.setObjectName("SectionTitle")
        right_layout.addWidget(svc_title)

        self.svc_container = QWidget()
        self.svc_layout = QVBoxLayout(self.svc_container)
        self.svc_layout.setContentsMargins(0, 0, 0, 0)
        self.svc_layout.setSpacing(8)
        right_layout.addWidget(self.svc_container)
        right_layout.addStretch(1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([380, 580])
        root.addWidget(splitter, 1)

    def _add_summary_col(self, parent_layout: QHBoxLayout, label: str, num_obj_name: str) -> QLabel:
        box = QVBoxLayout()
        num = QLabel("0")
        num.setObjectName(num_obj_name)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt = QLabel(label)
        txt.setObjectName("MetricLabel")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(num)
        box.addWidget(txt)
        parent_layout.addLayout(box)
        return num

    def set_session(self, gateway: str, token: str, username: str):
        self.gateway = gateway
        self.token = token
        self.username = username
        self.selected_ip = ""
        self._servers = []
        self._history_cache = []
        self.session_lbl.setText(f"管理员: {username}  |  网关: {gateway}")
        self.chart.set_data([], self.active_metric)

    def _start_api(self, method: str, path: str, callback, json_data=None, timeout=10):
        worker = ApiWorker(
            method, f"{self.gateway}{path}", token=self.token, json_data=json_data, timeout=timeout
        )
        self._workers.append(worker)
        worker.finished.connect(
            lambda ok, code, data, err, w=worker: self._handle_finish(w, callback, ok, code, data, err)
        )
        worker.start()

    def _handle_finish(self, worker: ApiWorker, callback, ok: bool, code: int, data: object, err: str):
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

        if ok and code == 401:
            self.token = ""
            QMessageBox.warning(self, "登录失效", "Token 已过期或无效，请重新登录")
            self.session_expired.emit()
            return
        callback(ok, code, data, err)

    def refresh_all(self):
        if not self.token:
            return
        self.status_hint.setText("正在采集刷新...")
        self.refresh_btn.setEnabled(False)
        self._start_api("GET", "/api/status", self._on_status_loaded)

    def _on_status_loaded(self, ok: bool, code: int, data: object, err: str):
        self.refresh_btn.setEnabled(True)
        if not ok:
            self.status_hint.setText(f"异常: {err}")
            return
        if code != 200 or not isinstance(data, list):
            msg = data.get("error", "获取状态失败") if isinstance(data, dict) else "返回格式错误"
            self.status_hint.setText(msg)
            return

        self._servers = data
        self._update_summary_and_cards()
        self.status_hint.setText("状态已同步 (每30秒自动刷新)")

        # 默认或保持选中主机刷新历史趋势
        ips = [s.get("ip") for s in self._servers if s.get("ip")]
        if ips:
            if self.selected_ip not in ips:
                self.selected_ip = ips[0]
            self._render_cards()
            self.fetch_history(self.selected_ip)

    def _update_summary_and_cards(self):
        total = len(self._servers)
        ok_cnt = 0
        warn_cnt = 0
        for s in self._servers:
            svcs = parse_services(s.get("services", ""))
            if svcs and all(st == "active" for _, st in svcs):
                ok_cnt += 1
            if (
                float(s.get("cpu", 0) or 0) > 80
                or float(s.get("mem", 0) or 0) > 80
                or float(s.get("disk", 0) or 0) > 80
                or any(st != "active" for _, st in svcs)
            ):
                warn_cnt += 1

        self.total_num_lbl.setText(str(total))
        self.ok_num_lbl.setText(str(ok_cnt))
        self.warn_num_lbl.setText(str(warn_cnt))
        self._render_cards()

    def _render_cards(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for s in self._servers:
            ip = s.get("ip", "")
            card = HostCard(s, selected=(ip == self.selected_ip))
            card.clicked.connect(self._on_select_host)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _on_select_host(self, ip: str):
        self.selected_ip = ip
        self._render_cards()
        self.fetch_history(ip)

    def fetch_history(self, ip: str):
        if not self.token or not ip:
            return
        self._start_api("GET", f"/api/history/{ip}", lambda ok, c, d, e: self._on_history_loaded(ip, ok, c, d, e))

    def _on_history_loaded(self, ip: str, ok: bool, code: int, data: object, err: str):
        if ip != self.selected_ip:
            return
        if not ok:
            self.status_hint.setText(f"历史查询失败: {err}")
            return
        if code != 200 or not isinstance(data, list):
            return

        self._history_cache = data
        self.chart.set_data(data, self.active_metric)

        host_info = next((s for s in self._servers if s.get("ip") == ip), None)
        hostname = (data[-1].get("hostname") if data else None) or (host_info.get("hostname") if host_info else ip)
        self.detail_title.setText(f"{hostname} ({ip}) · 近 20 次趋势")
        latest_time = data[-1].get("time", "") if data else (host_info.get("time", "") if host_info else "")
        self.detail_time.setText(f"最新采集: {latest_time}" if latest_time else "")

        svc_str = (data[-1].get("services") if data else None) or (host_info.get("services") if host_info else "")
        self._render_service_rows(ip, parse_services(svc_str))

    def _switch_metric(self, metric: str):
        self.active_metric = metric
        for k, btn in self.tab_buttons.items():
            btn.setChecked(k == metric)
        self.chart.set_data(self._history_cache, metric)

    def _render_service_rows(self, ip: str, svcs: list[tuple[str, str]]):
        while self.svc_layout.count():
            item = self.svc_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not svcs:
            empty = QLabel("该主机暂未配置监控服务")
            empty.setObjectName("TopSub")
            self.svc_layout.addWidget(empty)
            return

        for name, status in svcs:
            row_frame = QFrame()
            row_frame.setObjectName("ServiceRow")
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(12, 8, 12, 8)

            name_lbl = QLabel(name)
            name_lbl.setObjectName("SvcName")
            tag = QLabel(status)
            tag.setObjectName("TagOk" if status == "active" else "TagErr")

            btn = QPushButton("重启服务")
            btn.setObjectName("DangerBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(not self._restarting)
            btn.clicked.connect(lambda _chk, h=ip, s=name: self._confirm_restart(h, s))

            row.addWidget(name_lbl)
            row.addSpacing(10)
            row.addWidget(tag)
            row.addStretch()
            row.addWidget(btn)
            self.svc_layout.addWidget(row_frame)

    def _set_restarting(self, busy: bool):
        self._restarting = busy
        for i in range(self.svc_layout.count()):
            w = self.svc_layout.itemAt(i).widget()
            if w:
                for btn in w.findChildren(QPushButton):
                    btn.setEnabled(not busy)

    def _confirm_restart(self, ip: str, service: str):
        if self._restarting:
            return
        reply = QMessageBox.question(
            self,
            "确认重启",
            f"确定要远程重启 {ip} 上的 {service} 服务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._set_restarting(True)
        self.status_hint.setText(f"正在重启 {ip} -> {service} ...")
        self._start_api(
            "POST",
            "/api/restart",
            lambda ok, c, d, e: self._on_restart_done(ip, ok, c, d, e),
            json_data={"ip": ip, "service": service},
            timeout=20,
        )

    def _on_restart_done(self, ip: str, ok: bool, code: int, data: object, err: str):
        self._set_restarting(False)
        if not ok:
            self.status_hint.setText("重启请求失败")
            QMessageBox.critical(self, "网络错误", err)
            return

        msg = data.get("message", "执行完成") if isinstance(data, dict) else "响应异常"
        success = isinstance(data, dict) and bool(data.get("success"))
        if success:
            self.status_hint.setText(f"已执行重启：{msg}")
            QMessageBox.information(self, "操作成功", f"{msg}\n（监控数据将在后台采集周期内同步更新）")
            QTimer.singleShot(3000, self.refresh_all)
        else:
            self.status_hint.setText(f"重启失败：{msg}")
            QMessageBox.warning(self, "重启失败", msg)

    def _confirm_logout(self):
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出当前登录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.token = ""
            self.logout_requested.emit()

    def wait_workers(self):
        """等待所有未结束的请求线程退出，避免关闭窗口时崩溃。"""
        for w in list(self._workers):
            w.wait(1000)
