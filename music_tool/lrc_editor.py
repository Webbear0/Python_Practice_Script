#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lrc_editor.py — 多功能 LRC 歌词编辑工具
==========================================
整合了以下功能模块：
    1. 同步音频元数据到 LRC（支持 FLAC / MP3）
    2. 调整歌词时间轴偏移
    3. 分离双语歌词（原文 + 译文拆为两行）
    4. 调整歌词行顺序（原文在上、译文在下）
    5. 分离 + 调序 + 同步 一键连续操作

依赖安装：
    pip install mutagen

用法：
    # 交互式菜单
    python lrc_editor.py

    # 命令行模式（直接执行，无需交互）
    python lrc_editor.py sync <目录路径>
    python lrc_editor.py offset <目录路径> --seconds 1.5
    python lrc_editor.py split <目录路径>
    python lrc_editor.py reorder <目录路径>
    python lrc_editor.py split-reorder-sync <目录路径>
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime

from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3


# ============================================================
#  日志系统配置
# ============================================================

def setup_logger(log_dir=None):
    """
    配置日志系统：同时输出到终端和日志文件。

    终端输出保留简洁的用户友好格式，日志文件记录更详细的信息（含时间戳）。

    :param log_dir: 日志文件保存目录，默认为脚本所在目录下的 logs 文件夹
    :return: 配置好的 logger 实例
    """
    logger = logging.getLogger('lrc_editor')
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（交互模式下多次调用时）
    if logger.handlers:
        return logger

    # ---- 终端 Handler：仅输出 INFO 及以上，简洁格式 ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)

    # ---- 文件 Handler：DEBUG 及以上，含时间戳的详细格式 ----
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'lrc_editor_{timestamp}.log')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)-7s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(file_handler)

    logger.debug(f"日志文件: {log_file}")
    return logger


# 全局 logger（延迟初始化）
log = None


def get_logger():
    """获取全局 logger，首次调用时自动初始化。"""
    global log
    if log is None:
        log = setup_logger()
    return log


# ============================================================
#  LrcFile — LRC 文件数据模型
# ============================================================

class LrcFile:
    """
    表示一个 LRC 歌词文件，提供读取、写入、ID 标签管理等基础操作。
    所有读写均强制使用 UTF-8 编码。
    """

    # 匹配 LRC ID 标签行（如 [al:xxx]、[ar:xxx]、[ti:xxx]、[by:xxx]）
    ID_TAG_RE = re.compile(r'^\[(?:al|ar|ti|by):.*\]\s*$', re.IGNORECASE)

    # 匹配带时间戳的歌词行（如 [00:12.34]歌词内容）
    TIMESTAMP_RE = re.compile(r'^(\[\d{2}:\d{2}\.\d{2,3}\])(.*)$')

    def __init__(self, filepath):
        self.filepath = filepath
        self.id_tags = []        # ID 标签行（纯文本，含换行符）
        self.content_lines = []  # 其余内容行（歌词 + 空行等）

    def read(self):
        """读取 LRC 文件，自动将内容分离为 ID 标签和歌词内容。"""
        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()

        self.id_tags = []
        self.content_lines = []
        for line in lines:
            if self.ID_TAG_RE.match(line.strip()):
                self.id_tags.append(line)
            else:
                self.content_lines.append(line)
        return self

    def write(self):
        """将当前的 ID 标签 + 歌词内容写回文件（UTF-8，无 BOM）。"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.writelines(self.id_tags + self.content_lines)

    def remove_id_tags(self):
        """清除所有已有的 ID 标签行。返回被清除的数量。"""
        count = len(self.id_tags)
        self.id_tags = []
        return count

    def insert_id_tags(self, metadata: dict):
        """
        根据元数据字典插入 ID 标签行（会先清除旧标签）。

        :param metadata: 如 {'ti': '...', 'ar': '...', 'al': '...', 'by': '...'}
        """
        self.remove_id_tags()
        order = ['ti', 'ar', 'al', 'by']
        self.id_tags = [f'[{k}:{metadata[k]}]\n' for k in order if k in metadata]

    @property
    def basename(self):
        return os.path.basename(self.filepath)

    @property
    def stem(self):
        """文件名（不含扩展名）"""
        return os.path.splitext(self.basename)[0]

    @property
    def directory(self):
        return os.path.dirname(self.filepath)


# ============================================================
#  LrcEditor — 核心编辑器（整合全部功能）
# ============================================================

class LrcEditor:
    """
    LRC 歌词编辑器，支持批量操作指定目录下（含子目录）的所有 .lrc 文件。
    """

    # 支持的音频格式及优先级
    AUDIO_EXTENSIONS = ['.flac', '.mp3']

    def __init__(self, target_path):
        """
        :param target_path: 目标目录或单个文件路径
        """
        self.target_path = target_path
        self.log = get_logger()

    # ---- 通用工具方法 ----

    def _collect_lrc_files(self):
        """
        收集目标路径下所有 .lrc 文件，支持单文件或目录（递归）。

        :return: 排序后的 .lrc 文件路径列表
        """
        if os.path.isfile(self.target_path):
            if self.target_path.lower().endswith('.lrc'):
                return [self.target_path]
            else:
                self.log.error("错误：指定的文件不是 .lrc 格式。")
                return []

        if not os.path.isdir(self.target_path):
            self.log.error(f"错误：路径 '{self.target_path}' 不存在。")
            return []

        lrc_files = []
        for root, _, files in os.walk(self.target_path):
            for f in files:
                if f.lower().endswith('.lrc'):
                    lrc_files.append(os.path.join(root, f))

        if not lrc_files:
            self.log.warning("未找到任何 .lrc 文件。")
        else:
            self.log.info(f"找到 {len(lrc_files)} 个 .lrc 文件\n")

        return sorted(lrc_files)

    def _find_audio_file(self, lrc_dir, lrc_stem):
        """按优先级（.flac > .mp3）查找同名音频文件。"""
        for ext in self.AUDIO_EXTENSIONS:
            audio_path = os.path.join(lrc_dir, lrc_stem + ext)
            if os.path.isfile(audio_path):
                return audio_path
        return None

    def _print_header(self, title):
        self.log.info(f"\n{'='*60}")
        self.log.info(f"  {title}")
        self.log.info(f"{'='*60}\n")

    def _print_summary(self, success, skip):
        self.log.info(f"\n{'='*60}")
        self.log.info(f"  处理完成！")
        self.log.info(f"  成功: {success} 个文件")
        self.log.info(f"  跳过: {skip} 个文件")
        self.log.info(f"{'='*60}\n")

    # ================================================================
    #  功能 1：同步音频元数据到 LRC
    # ================================================================

    def _load_audio_tags(self, audio_path):
        """加载音频文件的标签对象（FLAC VorbisComment / MP3 EasyID3）。"""
        ext = os.path.splitext(audio_path)[1].lower()
        try:
            if ext == '.flac':
                return FLAC(audio_path).tags
            elif ext == '.mp3':
                return MP3(audio_path, ID3=EasyID3).tags
        except Exception as e:
            self.log.warning(f"  ⚠ 无法读取音频文件: {e}")
        return None

    def _extract_metadata(self, audio_path):
        """
        从音频文件提取元数据，映射为 LRC ID 标签字典。

        :return: dict 或 None
        """
        tags = self._load_audio_tags(audio_path)
        if tags is None:
            self.log.warning(f"  ⚠ 无元数据标签: {os.path.basename(audio_path)}")
            return {}

        metadata = {}

        # [al] <- Album
        album = tags.get('album') or tags.get('ALBUM')
        if album:
            metadata['al'] = album[0]
        else:
            self.log.info("  ℹ 缺少 Album 标签，跳过 [al]")

        # [ar] <- Artist
        artist = tags.get('artist') or tags.get('ARTIST')
        if artist:
            metadata['ar'] = artist[0]
        else:
            self.log.info("  ℹ 缺少 Artist 标签，跳过 [ar]")


        # [ti] <- Title
        title = tags.get('title') or tags.get('TITLE')
        if title:
            metadata['ti'] = title[0]
        else:
            self.log.info("  ℹ 缺少 Title 标签，跳过 [ti]")

        # [by] <- 默认值
        metadata['by'] = '全民制作人'

        self.log.debug(f"  提取到元数据: {metadata}")
        return metadata

    def sync_metadata(self):
        """功能 1：同步音频元数据到 LRC 的 ID 标签。"""
        self._print_header("功能 1：同步音频元数据 → LRC")
        lrc_files = self._collect_lrc_files()
        if not lrc_files:
            return

        success, skip = 0, 0
        for path in lrc_files:
            lrc = LrcFile(path)
            self.log.info(f"[处理] {lrc.basename}")

            audio_path = self._find_audio_file(lrc.directory, lrc.stem)
            if audio_path is None:
                exts = ' / '.join(self.AUDIO_EXTENSIONS)
                self.log.warning(f"  ⚠ 未找到对应的音频文件（{exts}），跳过")
                skip += 1
                self.log.info("")
                continue

            audio_ext = os.path.splitext(audio_path)[1].upper()
            self.log.info(f"  ℹ 匹配到: {os.path.basename(audio_path)} ({audio_ext})")

            metadata = self._extract_metadata(audio_path)
            if not metadata:
                skip += 1
                self.log.info("")
                continue

            try:
                lrc.read()
                removed = len(lrc.id_tags)
                lrc.insert_id_tags(metadata)
                if removed > 0:
                    self.log.info(f"  ℹ 已清除 {removed} 个旧 ID 标签")
                lrc.write()
                self.log.info("  ✔ 同步完成")
                success += 1
            except Exception as e:
                self.log.error(f"  ⚠ 处理失败: {e}")
                skip += 1
            self.log.info("")

        self._print_summary(success, skip)

    # ================================================================
    #  功能 2：调整歌词时间轴偏移
    # ================================================================

    @staticmethod
    def _adjust_timestamp(match, offset):
        """
        正则替换回调：将时间戳偏移指定秒数。

        :param match: 正则匹配对象，包含分、秒、百分之一秒
        :param offset: 偏移秒数（正数延后，负数提前）
        """
        m = int(match.group(1))
        s = int(match.group(2))
        ms = int(match.group(3))

        total = m * 60 + s + ms / 100.0 + offset
        total = max(total, 0)  # 不允许负时间

        new_m = int(total // 60)
        new_s = int(total % 60)
        remaining = total - (new_m * 60 + new_s)
        new_ms = int(round(remaining * 100))

        # 处理四舍五入进位
        if new_ms >= 100:
            new_ms -= 100
            new_s += 1
            if new_s >= 60:
                new_s -= 60
                new_m += 1

        return f'[{new_m:02d}:{new_s:02d}.{new_ms:02d}]'

    def adjust_time(self, offset_seconds):
        """
        功能 2：批量调整所有 LRC 文件的时间戳偏移。

        :param offset_seconds: 偏移秒数（正数延后，负数提前）
        """
        self._print_header(f"功能 2：调整时间轴（偏移 {offset_seconds:+.2f} 秒）")
        lrc_files = self._collect_lrc_files()
        if not lrc_files:
            return

        ts_pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2})\]')
        success, skip = 0, 0

        for path in lrc_files:
            self.log.info(f"[处理] {os.path.basename(path)}")
            try:
                with open(path, 'r', encoding='utf-8-sig') as f:
                    text = f.read()

                result = ts_pattern.sub(
                    lambda m: self._adjust_timestamp(m, offset_seconds), text
                )

                with open(path, 'w', encoding='utf-8') as f:
                    f.write(result)

                self.log.info(f"  ✔ 偏移 {offset_seconds:+.2f} 秒完成")
                success += 1
            except Exception as e:
                self.log.error(f"  ⚠ 处理失败: {e}")
                skip += 1
            self.log.info("")

        self._print_summary(success, skip)

    # ================================================================
    #  功能 3：分离双语歌词
    # ================================================================

    @staticmethod
    def _split_bilingual_text(text):
        """
        将一行包含原文和译文的歌词文本拆分为两部分。

        规则：
          - 含日文假名：以最后一个含假名的词为界，其后为译文
          - 不含假名：以第一个含汉字的词为界，其前为原文

        :return: (原文, 译文) 元组；无法拆分时译文为空字符串
        """
        has_kana = re.search(r'[\u3040-\u30ff]', text)
        parts = text.split(' ')
        if len(parts) == 1:
            return text, ""

        split_idx = -1
        if has_kana:
            # 有日文假名，寻找最后一个含假名的 token
            last_kana_idx = -1
            for i, p in enumerate(parts):
                if re.search(r'[\u3040-\u30ff]', p):
                    last_kana_idx = i
            if last_kana_idx != -1 and last_kana_idx + 1 < len(parts):
                split_idx = last_kana_idx + 1
        else:
            # 没有假名（外文原文），寻找第一个含汉字的 token
            for i, p in enumerate(parts):
                if re.search(r'[\u4e00-\u9fa5]', p):
                    split_idx = i
                    break

        if split_idx != -1 and split_idx > 0:
            return ' '.join(parts[:split_idx]), ' '.join(parts[split_idx:])
        return text, ""

    def split_bilingual(self):
        """功能 3：将同一行中的双语歌词拆分为两行（同时间戳）。"""
        self._print_header("功能 3：分离双语歌词")
        lrc_files = self._collect_lrc_files()
        if not lrc_files:
            return

        success, skip = 0, 0
        for path in lrc_files:
            self.log.info(f"[处理] {os.path.basename(path)}")
            try:
                lrc = LrcFile(path).read()
                new_lines = []
                changed = False

                for line in lrc.content_lines:
                    stripped = line.strip()
                    if not stripped:
                        new_lines.append('\n')
                        continue

                    m = LrcFile.TIMESTAMP_RE.match(stripped)
                    if m:
                        ts = m.group(1)
                        text = m.group(2).strip()
                        part1, part2 = self._split_bilingual_text(text)
                        if part2:
                            new_lines.append(f"{ts}{part1}\n")
                            new_lines.append(f"{ts}{part2}\n")
                            changed = True
                        else:
                            new_lines.append(f"{stripped}\n")
                    else:
                        new_lines.append(f"{stripped}\n")

                if changed:
                    lrc.content_lines = new_lines
                    lrc.write()
                    self.log.info("  ✔ 分离完成")
                    success += 1
                else:
                    self.log.info("  ℹ 无需分离或未匹配到可分离内容")
                    skip += 1
            except Exception as e:
                self.log.error(f"  ⚠ 处理失败: {e}")
                skip += 1
            self.log.info("")

        self._print_summary(success, skip)

    # ================================================================
    #  功能 4：调整歌词行顺序（原文在上、译文在下）
    # ================================================================

    @staticmethod
    def _has_japanese_kana(text):
        """检查是否含日文假名（平假名 + 片假名）"""
        return any('\u3040' <= c <= '\u30ff' for c in text)

    @staticmethod
    def _has_chinese_chars(text):
        """检查是否含中文汉字"""
        return any('\u4e00' <= c <= '\u9fff' for c in text)

    @staticmethod
    def _has_latin_chars(text):
        """检查是否含拉丁字母"""
        return any('a' <= c.lower() <= 'z' for c in text)

    @staticmethod
    def _is_likely_japanese_kanji(text):
        """检查是否含日语特有汉字"""
        jp_specific = set('気駅桜働悪様咲歩広帰絵遅読売買変楽歩教円々〆〇')
        return any(c in jp_specific for c in text)

    @classmethod
    def _detect_language(cls, text):
        """
        判断一行歌词的语言类别。
        优先级：japanese > chinese > latin > other
        """
        if cls._has_japanese_kana(text):
            return 'japanese'
        if cls._has_chinese_chars(text) and cls._is_likely_japanese_kanji(text):
            return 'japanese'
        if cls._has_chinese_chars(text):
            return 'chinese'
        if cls._has_latin_chars(text):
            return 'latin'
        return 'other'

    def reorder_lines(self):
        """功能 4：调整同时间戳的歌词行顺序（原文在上、译文在下）。"""
        self._print_header("功能 4：调整歌词行顺序（原文在上）")
        lrc_files = self._collect_lrc_files()
        if not lrc_files:
            return

        ts_re = LrcFile.TIMESTAMP_RE
        success, skip = 0, 0

        for path in lrc_files:
            self.log.info(f"[处理] {os.path.basename(path)}")
            try:
                lrc = LrcFile(path).read()
                lines = lrc.content_lines
                new_lines = []
                modified = False
                i = 0

                while i < len(lines):
                    if i + 1 < len(lines):
                        line1 = lines[i].strip()
                        line2 = lines[i + 1].strip()
                        m1 = ts_re.match(line1)
                        m2 = ts_re.match(line2)

                        # 两行时间戳相同时判断是否需要交换
                        if m1 and m2 and m1.group(1) == m2.group(1):
                            lang1 = self._detect_language(m1.group(2))
                            lang2 = self._detect_language(m2.group(2))

                            self.log.debug(
                                f"  比较: [{lang1}] {m1.group(2)[:20]}... "
                                f"vs [{lang2}] {m2.group(2)[:20]}..."
                            )

                            # 第一行是中文（译文），第二行是日文/英文（原文）→ 交换
                            if lang1 == 'chinese' and lang2 in ('japanese', 'latin'):
                                new_lines.append(line2 + '\n')
                                new_lines.append(line1 + '\n')
                                modified = True
                                i += 2
                                continue

                    new_lines.append(lines[i])
                    i += 1

                if modified:
                    lrc.content_lines = new_lines
                    lrc.write()
                    self.log.info("  ✔ 顺序调整完成")
                    success += 1
                else:
                    self.log.info("  ℹ 顺序已正确，无需调整")
                    skip += 1
            except Exception as e:
                self.log.error(f"  ⚠ 处理失败: {e}")
                skip += 1
            self.log.info("")

        self._print_summary(success, skip)

    # ================================================================
    #  功能 5：分离 + 调序 + 同步（连续操作）
    # ================================================================

    def split_reorder_sync(self):
        """功能 5：一键先分离双语歌词，再调整行顺序，最后同步音频元数据。"""
        self._print_header("功能 5：分离 + 调序 + 同步")
        self.log.info(">>> 第一步：分离双语歌词 <<<\n")
        self.split_bilingual()
        self.log.info(">>> 第二步：调整歌词行顺序 <<<\n")
        self.reorder_lines()
        self.log.info(">>> 第三步：同步音频元数据 <<<\n")
        self.sync_metadata()


# ============================================================
#  命令行参数解析（argparse）
# ============================================================

def build_parser():
    """构建 argparse 命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog='lrc_editor',
        description='多功能 LRC 歌词编辑工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例:\n'
            '  python lrc_editor.py                              # 交互式菜单\n'
            '  python lrc_editor.py sync "E:\\music\\某目录"       # 同步元数据\n'
            '  python lrc_editor.py offset "E:\\music" -s 1.5     # 时间轴延后 1.5 秒\n'
            '  python lrc_editor.py split-reorder-sync "E:\\music" # 分离 + 调序 + 同步\n'
        )
    )

    subparsers = parser.add_subparsers(dest='command', help='功能子命令')

    # ---- sync: 同步音频元数据 ----
    p_sync = subparsers.add_parser('sync', help='同步音频元数据到 LRC')
    p_sync.add_argument('path', help='目标目录或 .lrc 文件路径')

    # ---- offset: 调整时间轴 ----
    p_offset = subparsers.add_parser('offset', help='调整歌词时间轴偏移')
    p_offset.add_argument('path', help='目标目录或 .lrc 文件路径')
    p_offset.add_argument(
        '-s', '--seconds', type=float, required=True,
        help='偏移秒数（正数延后，负数提前，如 1.5 或 -0.5）'
    )

    # ---- split: 分离双语歌词 ----
    p_split = subparsers.add_parser('split', help='分离双语歌词')
    p_split.add_argument('path', help='目标目录或 .lrc 文件路径')

    # ---- reorder: 调整行顺序 ----
    p_reorder = subparsers.add_parser('reorder', help='调整歌词行顺序（原文在上）')
    p_reorder.add_argument('path', help='目标目录或 .lrc 文件路径')

    # ---- split-reorder-sync: 分离 + 调序 + 同步 ----
    p_sr = subparsers.add_parser('split-reorder-sync', help='分离 + 调序 + 同步元数据')
    p_sr.add_argument('path', help='目标目录或 .lrc 文件路径')

    return parser


# ============================================================
#  交互式菜单
# ============================================================

MENU = """
══════════════════════════════════════
       LRC 歌词编辑工具 v3.0
══════════════════════════════════════
  1. 同步音频元数据到 LRC
  2. 调整歌词时间轴
  3. 分离双语歌词
  4. 调整歌词行顺序（原文在上）
  5. 分离 + 调序 + 同步（连续操作）
  0. 退出
══════════════════════════════════════
"""


def get_target_path(default=None):
    """获取目标路径（支持默认值）。"""
    if default:
        path = input(f"请输入目标路径 [默认: {default}]: ").strip().strip('"\'') or default
    else:
        path = input("请输入目标路径（文件或目录）: ").strip().strip('"\'')
    return path


def interactive_mode():
    """交互式菜单主循环。"""
    logger = get_logger()
    logger.info("已启动交互式模式")
    default_path = None

    while True:
        print(MENU)
        choice = input("请选择功能编号: ").strip()

        if choice == '0':
            print("\n再见！\n")
            break

        if choice not in ('1', '2', '3', '4', '5'):
            print("无效选项，请重新选择。\n")
            continue

        target = get_target_path(default_path)
        if not target:
            print("未输入路径，取消操作。\n")
            continue

        editor = LrcEditor(target)

        if choice == '1':
            editor.sync_metadata()
        elif choice == '2':
            offset_input = input("请输入偏移秒数（正数延后，负数提前，如 1.5 或 -0.5）: ").strip()
            try:
                offset = float(offset_input)
            except ValueError:
                print("输入的秒数无效，请输入数字。\n")
                continue
            editor.adjust_time(offset)
        elif choice == '3':
            editor.split_bilingual()
        elif choice == '4':
            editor.reorder_lines()
        elif choice == '5':
            editor.split_reorder_sync()

        # 记住上次使用的路径
        default_path = target


def cli_mode(args):
    """命令行模式：根据 argparse 解析结果执行对应功能。"""
    logger = get_logger()
    logger.info(f"命令行模式: {args.command} -> {args.path}")

    editor = LrcEditor(args.path)

    if args.command == 'sync':
        editor.sync_metadata()
    elif args.command == 'offset':
        editor.adjust_time(args.seconds)
    elif args.command == 'split':
        editor.split_bilingual()
    elif args.command == 'reorder':
        editor.reorder_lines()
    elif args.command == 'split-reorder-sync':
        editor.split_reorder_sync()


# ============================================================
#  入口
# ============================================================

def main():
    parser = build_parser()

    # 无参数时进入交互式模式
    if len(sys.argv) == 1:
        interactive_mode()
        return

    args = parser.parse_args()

    # 有参数但无子命令时（不应该发生，但兜底处理）
    if not args.command:
        parser.print_help()
        return

    # 初始化日志并执行
    cli_mode(args)


if __name__ == '__main__':
    main()
