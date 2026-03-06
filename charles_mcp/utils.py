"""
工具函数模块。

提供日志配置、Windows 平台兼容性处理、文件操作等通用功能。
"""

import io
import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_file: str = "debug.log",
    level: int = logging.DEBUG,
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    配置项目日志系统。

    使用 RotatingFileHandler 避免日志文件过大，同时保留历史日志。

    Args:
        log_file: 日志文件路径
        level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量

    Returns:
        logging.Logger: 配置好的根日志记录器

    Example:
        >>> logger = setup_logging("app.log", logging.INFO)
        >>> logger.info("Application started")
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除已有的 handlers（避免重复添加）
    root_logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 创建 RotatingFileHandler
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # 如果无法创建文件 handler，回退到 stderr
        print(f"Warning: Cannot create log file '{log_file}': {e}", file=sys.stderr)

    return root_logger


def setup_windows_stdio() -> None:
    """
    配置 Windows 平台的标准输入/输出。

    解决 Windows 下 MCP 协议的以下问题：
    - 自动换行符转换 (\\r\\n vs \\n)
    - UTF-8 编码问题导致的连接中断
    - 中文字符乱码

    Note:
        仅在 Windows 平台生效，其他平台调用此函数无效果。

    Example:
        >>> setup_windows_stdio()  # 在程序入口调用
    """
    if sys.platform != "win32":
        return

    try:
        import msvcrt

        # 设置文件描述符为二进制模式，防止 Windows 自动转换换行符
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except (ImportError, OSError) as e:
        logging.warning(f"无法设置二进制模式: {e}")

    # 将流重新包装为 UTF-8 编码
    try:
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", write_through=True
        )
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception as e:
        logging.warning(f"无法包装 UTF-8 流: {e}")


def ensure_directory(path: str) -> bool:
    """
    确保目录存在，如不存在则创建。

    Args:
        path: 目录路径

    Returns:
        bool: 目录是否存在或成功创建

    Example:
        >>> ensure_directory("/tmp/myapp/data")
        True
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        logging.error(f"无法创建目录 '{path}': {e}")
        return False


def safe_copy_file(src: str, dst: str) -> bool:
    """
    安全地复制文件。

    Args:
        src: 源文件路径
        dst: 目标文件路径

    Returns:
        bool: 是否复制成功

    Example:
        >>> safe_copy_file("/tmp/source.txt", "/tmp/backup/source.txt")
        True
    """
    try:
        # 确保目标目录存在
        dst_dir = os.path.dirname(dst)
        if dst_dir:
            ensure_directory(dst_dir)

        shutil.copy2(src, dst)
        logging.debug(f"文件复制成功: {src} -> {dst}")
        return True
    except (OSError, shutil.Error) as e:
        logging.error(f"文件复制失败 '{src}' -> '{dst}': {e}")
        return False


def safe_copy_tree(src: str, dst: str, remove_existing: bool = True) -> bool:
    """
    安全地复制目录树。

    Args:
        src: 源目录路径
        dst: 目标目录路径
        remove_existing: 是否先删除已存在的目标目录

    Returns:
        bool: 是否复制成功

    Example:
        >>> safe_copy_tree("/tmp/source_dir", "/tmp/backup_dir")
        True
    """
    try:
        if remove_existing and os.path.exists(dst):
            shutil.rmtree(dst)

        shutil.copytree(src, dst)
        logging.debug(f"目录复制成功: {src} -> {dst}")
        return True
    except (OSError, shutil.Error) as e:
        logging.error(f"目录复制失败 '{src}' -> '{dst}': {e}")
        return False


def safe_remove_tree(path: str) -> bool:
    """
    安全地删除目录树。

    Args:
        path: 要删除的目录路径

    Returns:
        bool: 是否删除成功

    Example:
        >>> safe_remove_tree("/tmp/to_delete")
        True
    """
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            logging.debug(f"目录删除成功: {path}")
        return True
    except (OSError, shutil.Error) as e:
        logging.error(f"目录删除失败 '{path}': {e}")
        return False


def get_latest_file(directory: str, extension: str = ".chlsj") -> Optional[str]:
    """
    获取目录中指定扩展名的最新文件。

    Args:
        directory: 目录路径
        extension: 文件扩展名 (包含点号)

    Returns:
        Optional[str]: 最新文件的完整路径，未找到则返回 None

    Example:
        >>> get_latest_file("/tmp/packages", ".chlsj")
        '/tmp/packages/20260111000741.chlsj'
    """
    try:
        if not os.path.exists(directory):
            return None

        files = [
            f for f in os.listdir(directory) if f.endswith(extension)
        ]

        if not files:
            return None

        # 按文件名排序（假设文件名包含时间戳）
        sorted_files = sorted(files)
        return os.path.join(directory, sorted_files[-1])
    except OSError as e:
        logging.error(f"获取最新文件失败 '{directory}': {e}")
        return None


def list_files_with_extension(directory: str, extension: str) -> list[str]:
    """
    列出目录中指定扩展名的所有文件。

    Args:
        directory: 目录路径
        extension: 文件扩展名 (包含点号)

    Returns:
        list[str]: 文件名列表 (不包含路径)

    Example:
        >>> list_files_with_extension("/tmp/packages", ".chlsj")
        ['20260110235654.chlsj', '20260111000222.chlsj']
    """
    try:
        if not os.path.exists(directory):
            return []

        return [f for f in os.listdir(directory) if f.endswith(extension)]
    except OSError as e:
        logging.error(f"列出文件失败 '{directory}': {e}")
        return []


def format_bytes(size: int) -> str:
    """
    将字节数格式化为人类可读的字符串。

    Args:
        size: 字节数

    Returns:
        str: 格式化后的字符串

    Example:
        >>> format_bytes(1536)
        '1.50 KB'
        >>> format_bytes(1048576)
        '1.00 MB'
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def validate_regex(pattern: str) -> tuple[bool, Optional[str]]:
    """
    验证正则表达式是否有效且安全。

    检查语法有效性，并拒绝可能导致 ReDoS 的危险模式。

    Args:
        pattern: 正则表达式字符串

    Returns:
        tuple[bool, Optional[str]]: (是否有效, 错误信息)

    Example:
        >>> validate_regex(r"\\d+")
        (True, None)
        >>> validate_regex(r"[invalid")
        (False, 'unterminated character set at position 0')
    """
    import re

    # 限制正则表达式长度，防止过度复杂的模式
    max_pattern_length = 500
    if len(pattern) > max_pattern_length:
        return (False, f"正则表达式过长（最大 {max_pattern_length} 字符）")

    # 检测可能导致灾难性回溯的危险模式
    dangerous_patterns = [
        r'\(.*[+*].*\)[+*]',       # 嵌套量词，如 (a+)+
        r'\(.*\|.*\)[+*]{2,}',     # 交替分支 + 重复量词
    ]
    for dp in dangerous_patterns:
        if re.search(dp, pattern):
            return (False, "正则表达式包含可能导致性能问题的嵌套量词")

    try:
        re.compile(pattern)
        return (True, None)
    except re.error as e:
        return (False, str(e))
