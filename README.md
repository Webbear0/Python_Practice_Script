#  Python_Practice_Script

本项目收录了学习 Python 期间编写的 **24 个**实战脚本，涵盖数据库应用、网络爬虫、多媒体处理、桌面 GUI、数据可视化、自动化运维以及 Web API 调用等多个领域。

所有代码均已在 **Python 3.12+** 环境下测试通过。

---

##  目录结构

```
Python_Script/
├── BiliBili_tool/          # B站数据工具集
├── SQL/                    # 数据库应用
├── Tool/                   # 实用工具箱
├── Web_Spider/             # 网络爬虫
├── music_tool/             # 音乐处理工具
├── requirements.txt        # 项目依赖
└── README.md
```

---

##  BiliBili_tool — B站数据工具集

| 脚本 | 功能说明 | 核心技术 |
|------|---------|---------|
| [`bilibili_cleaner.py`](BiliBili_tool/bilibili_cleaner.py) | B站历史评论 / 弹幕 / 通知批量清理工具，支持二维码扫码登录、第三方 API 深层检索、交互式撤回与 JSON 导出 | `requests` · `qrcode` · `curl_cffi` · `dataclasses` |
| [`bilibili_tools.py`](BiliBili_tool/bilibili_tools.py) | B站综合查询工具 —— BV 号查视频数据、UID 查用户资料并导出历史评论 | `requests` · B站 API · aicu.cc API |
| [`bilibili_user_range_search.py`](BiliBili_tool/bilibili_user_range_search.py) | UID 区间批量扫描有效用户并导出 Excel 表格 | `requests` · `xlwt` |
| [`bilibili_duration_chart.py`](BiliBili_tool/bilibili_duration_chart.py) | 抓取热门视频，统计时长区间分布并生成饼图 | `requests` · `matplotlib` |
| [`bilibili_publish_hours.py`](BiliBili_tool/bilibili_publish_hours.py) | 分析热门视频发布时段，生成 24h 柱状图 + 时段饼图双图表 | `requests` · `matplotlib` |
| [`bilibili_ranking_chart.py`](BiliBili_tool/bilibili_ranking_chart.py) | 查询 12 个分区排行榜，生成播放量水平柱状图 + 占比饼图 | `requests` · `matplotlib` |
| [`bilibili_hot_wordcloud.py`](BiliBili_tool/bilibili_hot_wordcloud.py) | 获取实时热搜词并生成热度权重词云图 | `requests` · `wordcloud` |

---

##  SQL — 数据库应用

| 脚本 | 功能说明 | 核心技术 |
|------|---------|---------|
| [`bank_os.py`](SQL/bank_os.py) | 基于 MySQL 的控制台银行系统 —— 开户、销户、存取款、余额查询，自动建库建表，参数化防注入 | `pymysql` · MySQL |
| [`bank_os_sqlserver.py`](SQL/bank_os_sqlserver.py) | 基于 SQL Server 的高级银行系统 —— 引入事务回滚、T-SQL 存储过程，保障资金原子性 | `pyodbc` · SQL Server |
| [`campus_network.py`](SQL/campus_network.py) | 数字校园网络身份认证系统 —— 用户注册 / 登录校验，输入合法性前置判断 | `pymysql` · MySQL |

---

##  Tool — 实用工具箱

| 脚本 | 功能说明 | 核心技术 |
|------|---------|---------|
| [`train_ticket_query.py`](Tool/train_ticket_query.py) | 12306 火车票余票查询 —— 站名编码双向转换，PrettyTable 表格展示全席别余票 | `requests` · `prettytable` · `re` |
| [`weather_line_chart.py`](Tool/weather_line_chart.py) | 7 日气温趋势图 —— 调用 Open-Meteo API，绘制双色折线 + 温差区间填充 | `requests` · `matplotlib` |
| [`qrcode_generator.py`](Tool/qrcode_generator.py) | Tkinter 图形化二维码生成器 —— 即时预览与自动保存 PNG | `tkinter` · `qrcode` · `Pillow` |
| [`word_cloud.py`](Tool/word_cloud.py) | 中文人名词云图生成 —— jieba 词性标注提取人名，Tkinter 弹窗展示 | `jieba` · `wordcloud` · `tkinter` |
| [`remote_command.py`](Tool/remote_command.py) | SSH 远程运维工具 —— 交互式命令执行 + SFTP 文件上传 / 下载 / 改名 | `paramiko` |
| [`mc_server_query.py`](Tool/mc_server_query.py) | Minecraft 服务器状态查询 + IP 地理位置追踪 | `requests` |

---

##  Web_Spider — 网络爬虫

| 脚本 | 功能说明 | 核心技术 |
|------|---------|---------|
| [`Bing_wallpaper.py`](Web_Spider/Bing_wallpaper.py) | Bing 每日壁纸自动下载 —— 调用官方接口获取中国区高清壁纸 | `requests` |
| [`meituan.py`](Web_Spider/meituan.py) | 美团商户信息采集 —— 搜索结果 + 店铺详情穿透，导出 CSV | `requests` · `re` · `csv` |
| [`qianchengwuyou.py`](Web_Spider/qianchengwuyou.py) | 前程无忧招聘数据采集 —— 职位关键词检索，结构化 CSV 导出 | `requests` · `re` · `csv` |
| [`qidian_text.py`](Web_Spider/qidian_text.py) | 起点中文网小说章节下载 —— 目录解析 + 正文清洗 + 按章保存 | `requests` · `re` |
| [`qingtingfm.py`](Web_Spider/qingtingfm.py) | 蜻蜓 FM 音频下载 —— 逆向 HMAC-MD5 签名鉴权，批量下载 MP3 | `hmac` · `requests` |
| [`ximalaya.py`](Web_Spider/ximalaya.py) | 喜马拉雅专辑音频下载 —— 解析播放 API 获取真实音频流 | `requests` · `re` |

---

##  music_tool — 音乐处理工具

| 脚本 | 功能说明 | 核心技术 |
|------|---------|---------|
| [`lrc_editor.py`](music_tool/lrc_editor.py) | 多功能 LRC 歌词编辑器 —— 双语拆分、行顺序智能重排、时间轴偏移微调、音频元数据同步写入，支持交互式菜单与 CLI 子命令 | `mutagen` · `re` · `argparse` |
| [`music_manager.py`](music_tool/music_manager.py) | 音乐库自动化管理 —— 元数据归档整理、FLAC→MP3 批量转码（FFmpeg）、封面重命名、文件规范化 | `mutagen` · `subprocess` · `pathlib` |

---

##  快速开始

### 环境要求

- Python **3.12+**
- 部分脚本需要额外服务：MySQL（`bank_os.py` / `campus_network.py`）、SQL Server（`bank_os_sqlserver.py`）、FFmpeg（`music_manager.py`）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行示例

```bash
# 下载 Bing 每日壁纸
python Web_Spider/Bing_wallpaper.py

# 查询火车票余票
python Tool/train_ticket_query.py

# 生成 7 日气温趋势图
python Tool/weather_line_chart.py

# 启动 LRC 歌词编辑器
python music_tool/lrc_editor.py
```

---

##  依赖一览

| 类别 | 依赖包 |
|------|--------|
| 数据库 | `pymysql` · `pyodbc` |
| 网络请求 | `requests` |
| 数据展示 | `prettytable` · `xlwt` |
| 多媒体 | `mutagen` |
| 桌面 GUI | `qrcode` · `Pillow` |
| 数据可视化 | `matplotlib` · `jieba` · `wordcloud` |
| 远程运维 | `paramiko` |
| Web 框架 | `flask` |
| 可选 | `curl_cffi`（B站反爬降级备选） |

---

##  License

本项目仅供学习交流使用。
