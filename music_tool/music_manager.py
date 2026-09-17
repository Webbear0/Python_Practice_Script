#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
music_manager.py — 多功能音乐文件夹管理工具
=============================================
整合了以下功能模块：
    1. 从音频元数据批量创建歌曲文件夹并整理
    2. FLAC → MP3 批量转换（需要 ffmpeg）
    3. 批量重命名图片为 cover
    4. 批量重命名音乐文件为文件夹名

依赖安装：
    pip install mutagen    （功能 1 必须）
    系统需要安装 ffmpeg     （功能 2 需要）

用法：
    # 交互式菜单
    python music_manager.py

    # 命令行模式
    python music_manager.py create-folders <目录>
    python music_manager.py convert <输入目录> [-q 质量等级]
    python music_manager.py rename-images <目录>
    python music_manager.py rename-music <目录>
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
#  日志系统配置
# ============================================================

def setup_logger(log_dir=None):
    """
    配置日志系统：同时输出到终端和日志文件。

    :param log_dir: 日志文件保存目录，默认为脚本所在目录下的 logs 文件夹
    :return: 配置好的 logger 实例
    """
    logger = logging.getLogger('music_manager')
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # 终端 Handler：INFO 及以上，简洁格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)

    # 文件 Handler：DEBUG 及以上，含时间戳
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'music_manager_{timestamp}.log')

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
_logger = None


def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


# ============================================================
#  MusicManager — 核心管理器
# ============================================================

class MusicManager:
    """
    音乐文件夹管理器，整合创建文件夹、格式转换、文件重命名等功能。
    """

    # 支持的音乐文件扩展名
    MUSIC_EXTENSIONS = ('.flac', '.mp3')
    # 支持的图片文件扩展名
    IMAGE_EXTENSIONS = ('.jpg', '.png', '.jpeg', '.bmp', '.webp')

    def __init__(self, target_path):
        """
        :param target_path: 目标目录路径
        """
        self.target_path = target_path
        self.log = get_logger()

    # ---- 通用工具方法 ----

    def _print_header(self, title):
        self.log.info(f"\n{'='*60}")
        self.log.info(f"  {title}")
        self.log.info(f"{'='*60}\n")

    def _print_summary(self, success, skip=0, failed=0):
        self.log.info(f"\n{'='*60}")
        self.log.info(f"  处理完成！")
        self.log.info(f"  成功: {success} 个")
        if skip > 0:
            self.log.info(f"  跳过: {skip} 个")
        if failed > 0:
            self.log.info(f"  失败: {failed} 个")
        self.log.info(f"{'='*60}\n")

    def _validate_directory(self):
        """验证目标目录是否存在。"""
        if not os.path.isdir(self.target_path):
            self.log.error(f"错误：目录 '{self.target_path}' 不存在或不是有效目录。")
            return False
        return True

    # Windows 文件名非法字符
    _ILLEGAL_CHARS_RE = re.compile(r'[\\/*?:"<>|]')

    @staticmethod
    def _sanitize_filename(name):
        """清理文件名中的非法字符（Windows 兼容）。"""
        return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

    @classmethod
    def _sanitize_title(cls, title):
        """清理标题：非法字符替换为空格，合并多余空格。"""
        result = cls._ILLEGAL_CHARS_RE.sub(' ', title)
        return re.sub(r' +', ' ', result).strip()

    @classmethod
    def _sanitize_artist(cls, artist):
        """清理艺术家名：非法字符替换为下划线。"""
        return cls._ILLEGAL_CHARS_RE.sub('_', artist).strip()

    # ================================================================
    #  功能 1：从音频文件元数据批量创建歌曲文件夹
    # ================================================================

    def create_folders(self):
        """
        功能 1：扫描目录中的音频文件，使用 mutagen 读取标签，
        创建 "标题-艺术家" 格式的文件夹，并将音频文件移入。
        """
        self._print_header("功能 1：从音频元数据批量创建文件夹并整理")

        if not self._validate_directory():
            return

        try:
            import mutagen
        except ImportError:
            self.log.error("✗ 未安装 mutagen，请运行: pip install mutagen")
            return

        self.log.info(f"扫描目录: {self.target_path}\n")

        # 收集目录下（非递归）所有音频文件
        audio_files = [
            f for f in os.listdir(self.target_path)
            if os.path.isfile(os.path.join(self.target_path, f))
            and f.lower().endswith(self.MUSIC_EXTENSIONS)
        ]

        if not audio_files:
            self.log.warning("未找到音频文件。")
            return

        self.log.info(f"找到 {len(audio_files)} 个音频文件\n")

        created = 0
        moved = 0
        skipped = 0
        failed = 0

        for filename in audio_files:
            filepath = os.path.join(self.target_path, filename)

            # 读取音频元数据
            try:
                audio = mutagen.File(filepath, easy=True)
            except Exception as e:
                self.log.error(f"  ✗ 无法读取: {filename} - {e}")
                failed += 1
                continue

            if audio is None:
                self.log.error(f"  ✗ 无法识别格式: {filename}")
                failed += 1
                continue

            # 提取标题和艺术家
            title = (audio.get('title') or [None])[0]
            artist = (audio.get('artist') or [None])[0]

            if not title:
                self.log.warning(f"  ⚠ 缺少标题标签，跳过: {filename}")
                skipped += 1
                continue
            if not artist:
                self.log.warning(f"  ⚠ 缺少艺术家标签，跳过: {filename}")
                skipped += 1
                continue

            # 构建文件夹名：标题-艺术家
            safe_title = self._sanitize_title(title)
            safe_artist = self._sanitize_artist(artist)
            folder_name = f"{safe_title} - {safe_artist}"

            folder_path = os.path.join(self.target_path, folder_name)

            # 创建文件夹
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                self.log.info(f"  ✔ 创建文件夹: {folder_name}")
                created += 1

            # 移动音频文件到文件夹
            dest = os.path.join(folder_path, filename)
            if os.path.exists(dest):
                self.log.debug(f"  已存在，跳过移动: {filename}")
                skipped += 1
                continue

            try:
                shutil.move(filepath, dest)
                self.log.info(f"  ✔ 移动: {filename} → {folder_name}/")
                moved += 1
            except Exception as e:
                self.log.error(f"  ✗ 移动失败: {filename} - {e}")
                failed += 1

        self.log.info(f"\n{'='*60}")
        self.log.info(f"  处理完成！")
        self.log.info(f"  创建文件夹: {created} 个")
        self.log.info(f"  移动文件:   {moved} 个")
        if skipped > 0:
            self.log.info(f"  跳过: {skipped} 个")
        if failed > 0:
            self.log.info(f"  失败: {failed} 个")
        self.log.info(f"{'='*60}\n")

    # ================================================================
    #  功能 2：FLAC → MP3 批量转换
    # ================================================================

    @staticmethod
    def _check_ffmpeg():
        """检查 ffmpeg 是否可用。"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True, text=True, check=True,
                encoding='utf-8', errors='ignore'
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _find_flac_files(self):
        """递归查找目录下所有 FLAC 文件。"""
        flac_files = []
        for root, _, files in os.walk(self.target_path):
            for f in files:
                if f.lower().endswith('.flac'):
                    flac_files.append(os.path.join(root, f))
        return flac_files

    @staticmethod
    def _convert_single_file(input_file, output_file, quality=None):
        """
        使用 ffmpeg 将单个 FLAC 文件转换为 MP3。

        :param quality: None=320kbps CBR, 0-9=VBR 级别
        :return: (success: bool, error_msg: str)
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-map', '0:a',
            '-map', '0:v?',
            '-codec:a', 'libmp3lame',
            '-c:v', 'copy',
            '-id3v2_version', '3'
        ]

        if quality is None:
            cmd.extend(['-b:a', '320k'])
        else:
            cmd.extend(['-q:a', str(quality)])

        cmd.extend(['-y', output_file])

        try:
            subprocess.run(
                cmd, capture_output=True, text=True, check=True,
                encoding='utf-8', errors='ignore'
            )
            return True, ""
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def _copy_existing_mp3(self, output_dir):
        """复制源目录中已有的 MP3 文件到输出目录。"""
        copied = 0
        for root, _, files in os.walk(self.target_path):
            for f in files:
                if f.lower().endswith('.mp3'):
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, self.target_path)
                    dst = os.path.join(output_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    try:
                        shutil.copy2(src, dst)
                        copied += 1
                    except Exception as e:
                        self.log.warning(f"  ⚠ 复制 MP3 失败: {rel} - {e}")
        return copied

    def convert_flac_to_mp3(self, quality=None, output_suffix='_output'):
        """
        功能 2：批量 FLAC → MP3 转换。

        :param quality: None=320kbps CBR, 0-9=VBR 级别
        :param output_suffix: 输出目录后缀
        """
        self._print_header("功能 2：FLAC → MP3 批量转换")

        if not self._validate_directory():
            return

        # 检查 ffmpeg
        if not self._check_ffmpeg():
            self.log.error("✗ 未找到 ffmpeg，请确保 ffmpeg 已安装并在 PATH 中。")
            return

        self.log.info("✓ FFmpeg 已检测到")

        input_dir = Path(self.target_path).resolve()
        output_dir = input_dir.parent / (input_dir.name + output_suffix)

        quality_display = "320kbps (CBR 固定码率)" if quality is None else f"VBR {quality} 级"
        self.log.info(f"输入目录: {input_dir}")
        self.log.info(f"输出目录: {output_dir}")
        self.log.info(f"转换音质: {quality_display}")
        self.log.info(f"标签处理: 保留封面图与 ID3v2.3 标签\n")

        # 查找 FLAC 文件
        flac_files = self._find_flac_files()
        if not flac_files:
            self.log.warning("未找到 FLAC 文件。")
            return

        self.log.info(f"找到 {len(flac_files)} 个 FLAC 文件\n")

        # 复制已有 MP3
        copied = self._copy_existing_mp3(str(output_dir))
        if copied > 0:
            self.log.info(f"✓ 复制了 {copied} 个已有 MP3 文件\n")

        # 批量转换
        success_count, failed_count, skip_count = 0, 0, 0

        for i, flac_file in enumerate(flac_files, 1):
            rel_path = os.path.relpath(flac_file, str(input_dir))
            mp3_name = os.path.splitext(rel_path)[0] + '.mp3'
            output_file = str(output_dir / mp3_name)

            # 已存在则跳过
            if os.path.exists(output_file):
                self.log.info(f"[{i}/{len(flac_files)}] 跳过: {rel_path} (已存在)")
                skip_count += 1
                continue

            self.log.info(f"[{i}/{len(flac_files)}] 转换: {rel_path}")

            ok, err = self._convert_single_file(flac_file, output_file, quality)
            if ok:
                in_size = os.path.getsize(flac_file)
                out_size = os.path.getsize(output_file)
                ratio = (1 - out_size / in_size) * 100 if in_size > 0 else 0
                self.log.info(
                    f"  ✓ 成功 ({in_size//1024//1024}MB → "
                    f"{out_size//1024//1024}MB, 压缩 {ratio:.1f}%)"
                )
                success_count += 1
            else:
                self.log.error(f"  ✗ 失败: {err[:200]}")
                failed_count += 1

        # 总体统计
        self._print_summary(success_count, skip_count, failed_count)

        if success_count > 0:
            in_total = sum(os.path.getsize(f) for f in flac_files)
            out_files = [
                str(output_dir / (os.path.splitext(os.path.relpath(f, str(input_dir)))[0] + '.mp3'))
                for f in flac_files
            ]
            out_total = sum(os.path.getsize(f) for f in out_files if os.path.exists(f))
            if out_total > 0:
                total_ratio = (1 - out_total / in_total) * 100
                saved = (in_total - out_total) // 1024 // 1024
                self.log.info(f"  总体压缩比: {total_ratio:.1f}%")
                self.log.info(f"  节省空间:   {saved} MB\n")

    # ================================================================
    #  功能 3：批量重命名图片为 cover
    # ================================================================

    def rename_images(self):
        """功能 3：将目录下所有图片文件重命名为 cover.ext（避免冲突）。"""
        self._print_header("功能 3：批量重命名图片 → cover")

        if not self._validate_directory():
            return

        self.log.info(f"扫描目录: {self.target_path}\n")

        renamed = 0
        skipped = 0

        for root, _, files in os.walk(self.target_path):
            for filename in files:
                if not filename.lower().endswith(self.IMAGE_EXTENSIONS):
                    continue

                # 已经是 cover 开头的跳过
                if filename.lower().startswith('cover'):
                    self.log.debug(f"  跳过 (已命名): {os.path.join(root, filename)}")
                    skipped += 1
                    continue

                old_path = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1]

                # 寻找不冲突的文件名
                new_name = f"cover{ext}"
                new_path = os.path.join(root, new_name)
                counter = 1
                while os.path.exists(new_path):
                    new_name = f"cover_{counter}{ext}"
                    new_path = os.path.join(root, new_name)
                    counter += 1

                try:
                    os.rename(old_path, new_path)
                    rel_old = os.path.relpath(old_path, self.target_path)
                    self.log.info(f"  ✔ {rel_old} → {new_name}")
                    renamed += 1
                except Exception as e:
                    self.log.error(f"  ⚠ 重命名失败: {old_path} - {e}")

        self._print_summary(renamed, skipped)

    # ================================================================
    #  功能 4：批量重命名音乐文件为文件夹名
    # ================================================================

    def rename_music(self):
        """功能 4：将音乐文件重命名为其父文件夹的名称。"""
        self._print_header("功能 4：批量重命名音乐文件 → 文件夹名")

        if not self._validate_directory():
            return

        self.log.info(f"扫描目录: {self.target_path}\n")

        renamed = 0
        skipped = 0

        for root, _, files in os.walk(self.target_path):
            folder_name = os.path.basename(root)
            if not folder_name:
                continue

            music_files = [f for f in files if f.lower().endswith(self.MUSIC_EXTENSIONS)]

            for filename in music_files:
                old_path = os.path.join(root, filename)
                ext = os.path.splitext(filename)[1]
                new_name = f"{folder_name}{ext}"
                new_path = os.path.join(root, new_name)

                # 已经是正确名字
                if filename == new_name:
                    skipped += 1
                    continue

                # 处理重名冲突
                counter = 1
                while os.path.exists(new_path):
                    # Windows 文件名大小写不敏感，检查是否实际是同一文件
                    if os.path.normcase(old_path) == os.path.normcase(new_path):
                        break
                    new_name = f"{folder_name}_{counter}{ext}"
                    new_path = os.path.join(root, new_name)
                    counter += 1

                # 不是同一文件才执行重命名
                if os.path.normcase(old_path) != os.path.normcase(new_path):
                    try:
                        os.rename(old_path, new_path)
                        rel_old = os.path.relpath(old_path, self.target_path)
                        self.log.info(f"  ✔ {rel_old} → {new_name}")
                        renamed += 1
                    except Exception as e:
                        self.log.error(f"  ⚠ 重命名失败: {old_path} - {e}")
                else:
                    skipped += 1

        self._print_summary(renamed, skipped)


# ============================================================
#  命令行参数解析（argparse）
# ============================================================

def build_parser():
    parser = argparse.ArgumentParser(
        prog='music_manager',
        description='多功能音乐文件夹管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例:\n'
            '  python music_manager.py                                    # 交互式菜单\n'
            '  python music_manager.py create-folders "E:\\music\\ボカロ"    # 读取音频标签创建文件夹\n'
            '  python music_manager.py convert "E:\\music\\ボカロ"          # FLAC→MP3 (320kbps)\n'
            '  python music_manager.py convert "E:\\music" -q 2           # FLAC→MP3 (VBR 2级)\n'
            '  python music_manager.py rename-images "E:\\music"          # 图片→cover\n'
            '  python music_manager.py rename-music "E:\\music"           # 音乐→文件夹名\n'
        )
    )

    subparsers = parser.add_subparsers(dest='command', help='功能子命令')

    # create-folders
    p_cf = subparsers.add_parser('create-folders', help='从音频元数据创建文件夹并整理')
    p_cf.add_argument('path', help='包含音频文件的目录路径')

    # convert
    p_conv = subparsers.add_parser('convert', help='FLAC → MP3 批量转换')
    p_conv.add_argument('path', help='包含 FLAC 文件的输入目录')
    p_conv.add_argument(
        '-q', '--quality', type=int, default=None, choices=range(0, 10),
        help='MP3 质量级别 (0-9 VBR)，不指定则为 320kbps CBR'
    )
    p_conv.add_argument('--output-suffix', default='_output', help='输出目录后缀 (默认: _output)')

    # rename-images
    p_ri = subparsers.add_parser('rename-images', help='批量重命名图片为 cover')
    p_ri.add_argument('path', help='目标目录路径')

    # rename-music
    p_rm = subparsers.add_parser('rename-music', help='批量重命名音乐文件为文件夹名')
    p_rm.add_argument('path', help='目标目录路径')

    return parser


# ============================================================
#  交互式菜单
# ============================================================

MENU = """
══════════════════════════════════════
      音乐文件夹管理工具 v1.0
══════════════════════════════════════
  1. 从音频元数据创建文件夹并整理
  2. FLAC → MP3 批量转换
  3. 批量重命名图片 → cover
  4. 批量重命名音乐文件 → 文件夹名
  0. 退出
══════════════════════════════════════
"""


def get_target_path(default=None):
    if default:
        path = input(f"请输入目标路径 [默认: {default}]: ").strip().strip('"\'') or default
    else:
        path = input("请输入目标路径: ").strip().strip('"\'')
    return path


def interactive_mode():
    logger = get_logger()
    logger.info("已启动交互式模式")
    default_path = None

    while True:
        print(MENU)
        choice = input("请选择功能编号: ").strip()

        if choice == '0':
            print("\n再见！\n")
            break

        if choice not in ('1', '2', '3', '4'):
            print("无效选项，请重新选择。\n")
            continue

        target = get_target_path(default_path)
        if not target:
            print("未输入路径，取消操作。\n")
            continue

        manager = MusicManager(target)

        if choice == '1':
            manager.create_folders()
        elif choice == '2':
            q_input = input("请输入质量级别 (0-9 VBR，直接回车使用默认 320kbps CBR): ").strip()
            quality = None
            if q_input:
                try:
                    quality = int(q_input)
                    if quality < 0 or quality > 9:
                        print("质量级别应在 0-9 之间，使用默认 320kbps。\n")
                        quality = None
                except ValueError:
                    print("输入无效，使用默认 320kbps。\n")

            suffix = input("输出目录后缀 [默认: _output]: ").strip() or '_output'
            manager.convert_flac_to_mp3(quality=quality, output_suffix=suffix)
        elif choice == '3':
            manager.rename_images()
        elif choice == '4':
            manager.rename_music()

        default_path = target


def cli_mode(args):
    logger = get_logger()
    logger.info(f"命令行模式: {args.command} -> {args.path}")

    manager = MusicManager(args.path)

    if args.command == 'create-folders':
        manager.create_folders()
    elif args.command == 'convert':
        manager.convert_flac_to_mp3(quality=args.quality, output_suffix=args.output_suffix)
    elif args.command == 'rename-images':
        manager.rename_images()
    elif args.command == 'rename-music':
        manager.rename_music()


# ============================================================
#  入口
# ============================================================

def main():
    parser = build_parser()

    if len(sys.argv) == 1:
        interactive_mode()
        return

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli_mode(args)


if __name__ == '__main__':
    main()
