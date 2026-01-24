"""Tests for script_utils."""
import pytest
from app.utils.script_utils import get_script_execution_info


def test_get_script_execution_info_absolute_path():
    """测试绝对路径解析"""
    info = get_script_execution_info("/app/dir/script.sh")
    assert info["working_dir"] == "/app/dir"
    assert info["command"] == 'cd "/app/dir" && bash "./script.sh"'
    assert info["script_name"] == "script.sh"


def test_get_script_execution_info_relative_path_with_dot():
    """测试带 ./ 的相对路径"""
    info = get_script_execution_info("./scripts/restart.sh")
    assert info["working_dir"] == "scripts"
    assert info["command"] == 'cd "scripts" && bash "./restart.sh"'
    assert info["script_name"] == "restart.sh"


def test_get_script_execution_info_simple_name():
    """测试仅文件名"""
    info = get_script_execution_info("restart.sh")
    assert info["working_dir"] == "."
    assert info["command"] == 'cd "." && bash "./restart.sh"'
    assert info["script_name"] == "restart.sh"


def test_get_script_execution_info_nested_path():
    """测试嵌套目录的绝对路径"""
    info = get_script_execution_info("/application/back/charge-back/restartFromTemp.sh")
    assert info["working_dir"] == "/application/back/charge-back"
    assert info["command"] == 'cd "/application/back/charge-back" && bash "./restartFromTemp.sh"'
    assert info["script_name"] == "restartFromTemp.sh"


def test_get_script_execution_info_empty_string():
    """测试空字符串输入"""
    with pytest.raises(ValueError, match="script_path cannot be empty"):
        get_script_execution_info("")


def test_get_script_execution_info_whitespace_only():
    """测试仅包含空白字符的输入"""
    with pytest.raises(ValueError, match="script_path cannot be empty"):
        get_script_execution_info("   ")


def test_get_script_execution_info_path_with_spaces():
    """测试包含空格的路径"""
    info = get_script_execution_info("/app/my dir/script.sh")
    assert info["working_dir"] == "/app/my dir"
    assert info["command"] == 'cd "/app/my dir" && bash "./script.sh"'
    assert info["script_name"] == "script.sh"
