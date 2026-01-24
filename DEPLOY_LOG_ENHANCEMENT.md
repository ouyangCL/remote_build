# 部署脚本执行日志输出增强

## 概述

本次修改增强了 DevOps 部署平台的部署脚本执行日志输出，完整记录脚本的 stdout 和 stderr，并提供实时流式输出。

## 修改的文件

### 1. `backend/app/core/ssh.py`

**新增方法：`execute_command_streaming`**

```python
def execute_command_streaming(
    self,
    command: str,
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
) -> tuple[int, str, str]:
```

**功能说明：**
- 执行远程命令并提供实时流式输出
- 通过回调函数逐行处理 stdout 和 stderr
- 返回退出码、完整的 stdout 和 stderr

**技术实现：**
- 使用 Paramiko 的 `exec_command` 执行命令
- 使用 `readline()` 逐行读取输出
- 对于每一行输出，调用对应的回调函数
- 同时收集完整的输出用于返回值

### 2. `backend/app/services/deploy_service.py`

**修改方法：`_deploy_to_server`**

**增强的日志输出：**

#### 解压过程
```
开始解压到 {deploy_path}
解压命令: {unzip_command}
[stdout] {output_line}
[stderr] {error_line}
解压完成，退出码: {exit_code}
```

#### 脚本执行
```
准备执行部署脚本: {script_name}
脚本路径: {script_path}
工作目录: {working_dir}
执行命令: {command}
[stdout] {output_line}
[stderr] {error_line}
脚本执行完成，退出码: {exit_code}
```

**技术实现：**
- 使用 `execute_command_streaming` 替代 `execute_command`
- 通过 lambda 回调函数实时记录输出
- 使用 `asyncio.create_task` 异步记录日志，避免阻塞命令执行
- 区分 stdout 和 stderr 输出
- 根据退出码使用不同的日志级别（INFO/ERROR）

## 日志格式示例

### 成功的部署脚本执行

```
INFO  准备执行部署脚本: restart.sh
INFO  脚本路径: /opt/app/scripts/restart.sh
INFO  工作目录: /opt/app
INFO  执行命令: cd /opt/app && bash /opt/app/scripts/restart.sh
INFO  [stdout] Stopping application...
INFO  [stdout] Application stopped
INFO  [stdout] Starting application...
INFO  [stdout] Application started successfully
INFO  脚本执行完成，退出码: 0
INFO  部署脚本执行成功
```

### 失败的部署脚本执行

```
INFO  准备执行部署脚本: restart.sh
INFO  脚本路径: /opt/app/scripts/restart.sh
INFO  工作目录: /opt/app
INFO  执行命令: cd /opt/app && bash /opt/app/scripts/restart.sh
INFO  [stdout] Stopping application...
ERROR [stderr] Error: Application not running
ERROR [stderr] Failed to stop application
ERROR 脚本执行完成，退出码: 1
ERROR 部署脚本执行失败
```

## 使用示例

```python
# 在部署服务中使用流式输出
exit_code, stdout, stderr = conn.execute_command_streaming(
    "npm install",
    on_stdout=lambda line: asyncio.create_task(
        self.logger.info(f"[stdout] {line}")
    ),
    on_stderr=lambda line: asyncio.create_task(
        self.logger.info(f"[stderr] {line}")
    ),
)

if exit_code != 0:
    await self.logger.error(f"脚本执行完成，退出码: {exit_code}")
else:
    await self.logger.info(f"脚本执行完成，退出码: {exit_code}")
```

## 测试

运行单元测试验证功能：

```bash
cd backend
PYTHONPATH=/path/to/backend python3 tests/test_ssh_streaming.py
```

## 注意事项

1. **异步日志记录**：使用 `asyncio.create_task` 异步记录日志，避免阻塞命令执行
2. **字符编码**：使用 UTF-8 解码，错误时使用 `errors="replace"` 替换非法字符
3. **行尾处理**：使用 `rstrip("\n\r")` 移除行尾的换行符
4. **超时设置**：命令执行超时设置为 300 秒（5分钟）
5. **回调函数**：回调函数在同步上下文中调用，需要注意异步操作的处理

## 后续改进建议

1. 支持取消正在执行的命令
2. 添加命令执行超时配置
3. 支持更细粒度的日志级别控制
4. 添加输出行的行号信息
5. 支持输出高亮和过滤
