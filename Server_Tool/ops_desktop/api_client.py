# api_client.py -- 桌面端异步网络请求与本地配置持久化封装
import json
from pathlib import Path
import requests
from PyQt6.QtCore import QThread, pyqtSignal

CONFIG_FILE = Path.home() / ".ops_desktop.json"


def normalize_gateway(url: str) -> str:
    """规范化网关地址：自动补全 http:// 协议头并去除末尾斜杠。"""
    gw = (url or "").strip()
    if not gw:
        return ""
    if not gw.startswith(("http://", "https://")):
        gw = "http://" + gw
    return gw.rstrip("/")


def load_saved_gateway() -> str:
    """从用户主目录读取上次登录保存的网关地址（兼容 PyInstaller 单文件模式）。"""
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return data.get("gateway", "")
    except Exception:
        pass
    return ""


def save_gateway(gateway: str) -> None:
    """将网关地址持久化到用户主目录配置文件。"""
    try:
        CONFIG_FILE.write_text(
            json.dumps({"gateway": gateway}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def parse_services(svc_str: str) -> list[tuple[str, str]]:
    """解析后端返回的服务状态字符串（如 'apache2=active, mariadb=active'）。"""
    if not svc_str or svc_str.strip() == "-":
        return []
    result = []
    for item in svc_str.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            name, status = item.split("=", 1)
            result.append((name.strip(), status.strip()))
        else:
            result.append((item, "unknown"))
    return result


class ApiWorker(QThread):
    """后台异步 HTTP 请求线程，防止网络等待阻塞 PyQt 主界面事件循环。"""

    # 信号参数：(是否网络请求成功, HTTP状态码, 响应JSON对象, 错误说明)
    finished = pyqtSignal(bool, int, object, str)

    def __init__(
        self,
        method: str,
        url: str,
        token: str = "",
        json_data: dict | None = None,
        timeout: int = 10,
    ):
        super().__init__()
        self.method = method.upper()
        self.url = url
        self.token = token
        self.json_data = json_data
        self.timeout = timeout

    def run(self):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            resp = requests.request(
                self.method,
                self.url,
                headers=headers,
                json=self.json_data,
                timeout=self.timeout,
            )
            try:
                data = resp.json()
            except ValueError:
                data = {"raw": resp.text}
            self.finished.emit(True, resp.status_code, data, "")
        except requests.exceptions.Timeout:
            self.finished.emit(False, 0, None, "请求超时，请检查网关网络连通性")
        except requests.exceptions.ConnectionError:
            self.finished.emit(False, 0, None, "无法连接网关服务器，请核对地址与端口")
        except Exception as exc:
            self.finished.emit(False, 0, None, f"请求异常: {exc}")
