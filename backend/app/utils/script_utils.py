"""Script execution utilities."""
from pathlib import Path


def get_script_execution_info(script_path: str) -> dict:
    """解析脚本路径，返回执行信息。

    Args:
        script_path: 脚本路径（绝对路径或相对路径）

    Returns:
        dict: {
            "working_dir": str,  # 工作目录
            "command": str,      # 执行命令
            "script_name": str   # 脚本名称
        }
    """
    path = Path(script_path)

    # 判断是否为绝对路径
    if path.is_absolute():
        working_dir = str(path.parent)
        script_name = path.name
    else:
        # 相对路径
        if script_path.startswith('./'):
            # 保持原始的 ./ 前缀
            working_dir = script_path.rsplit('/', 1)[0] if '/' in script_path else '.'
        else:
            working_dir = str(path.parent) if path.parent != Path('.') else '.'
        script_name = path.name

    # 构建执行命令：cd 到工作目录 && 执行脚本
    command = f"cd {working_dir} && bash ./{script_name}"

    return {
        "working_dir": working_dir,
        "command": command,
        "script_name": script_name
    }
