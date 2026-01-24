"""Script execution utilities."""
from pathlib import Path


def get_script_execution_info(script_path: str) -> dict:
    """解析脚本路径，返回执行信息。

    Args:
        script_path: 脚本路径（绝对路径或相对路径）

    Returns:
        dict: 包含工作目录、执行命令和脚本名称
            - working_dir (str): 工作目录
            - command (str): 执行命令
            - script_name (str): 脚本名称

    Raises:
        ValueError: 当 script_path 为空字符串时
    """
    if not script_path or not script_path.strip():
        raise ValueError("script_path cannot be empty")

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
