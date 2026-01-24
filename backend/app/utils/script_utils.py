"""Script execution utilities."""
from pathlib import Path
from typing import Dict


def get_script_execution_info(script_path: str) -> Dict[str, str]:
    """解析脚本路径，返回执行信息。

    Args:
        script_path: 脚本路径（绝对路径或相对路径）

    Returns:
        包含工作目录、执行命令和脚本名称的字典

    Raises:
        ValueError: 当 script_path 为空或包含非法字符时
    """
    if not script_path or not script_path.strip():
        raise ValueError("script_path cannot be empty")

    # 安全检查：防止命令注入
    dangerous_chars = [';', '|', '&', '$', '`', '(', ')', '\n', '\r', '\t']
    if any(char in script_path for char in dangerous_chars):
        raise ValueError("script_path contains potentially dangerous characters")

    path = Path(script_path)
    script_name = path.name

    if path.is_absolute():
        working_dir = str(path.parent)
    else:
        working_dir = str(path.parent) or '.'

    # 使用引号保护路径中的空格
    command = f'cd "{working_dir}" && bash "./{script_name}"'

    return {
        "working_dir": working_dir,
        "command": command,
        "script_name": script_name
    }
