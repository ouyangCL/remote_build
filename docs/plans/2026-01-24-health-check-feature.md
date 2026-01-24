# 健康检查功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 为 DevOps 部署平台实现健康检查功能，在部署完成后自动验证服务状态

**架构：**
- 在 Project 模型中添加健康检查配置字段
- 创建独立的 HealthCheckService 处理三种检查类型（HTTP/TCP/Command）
- 在部署流程中集成健康检查步骤
- 支持重试机制和详细日志记录

**技术栈：**
- SQLAlchemy 2.0（数据库模型）
- Alembic（数据库迁移）
- httpx 0.26.0（HTTP 异步请求）
- asyncio（异步操作）
- paramiko（SSH 命令执行）

---

## Task 1: 添加健康检查字段到 Project 模型

**文件：**
- 修改: `backend/app/models/project.py`

**Step 1: 添加健康检查相关字段**

在 `Project` 类的 `environment` 字段后添加以下字段：

```python
# Health check configuration
health_check_enabled: Mapped[bool] = mapped_column(
    Boolean, default=False, nullable=False
)
health_check_type: Mapped[str] = mapped_column(
    String(20), default="http", nullable=False
)
health_check_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
health_check_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
health_check_command: Mapped[str | None] = mapped_column(Text, nullable=True)
health_check_timeout: Mapped[int] = mapped_column(
    Integer, default=30, nullable=False
)
health_check_retries: Mapped[int] = mapped_column(
    Integer, default=3, nullable=False
)
health_check_interval: Mapped[int] = mapped_column(
    Integer, default=5, nullable=False
)
```

需要确保在文件顶部导入 `Boolean` 类型。

**Step 2: 验证模型字段**

运行: `python -c "from app.models.project import Project; print('Model loaded successfully')"`
预期: 无错误输出

**Step 3: 提交模型更改**

```bash
git add backend/app/models/project.py
git commit -m "feat: 添加健康检查配置字段到 Project 模型"
```

---

## Task 2: 创建数据库迁移文件

**文件：**
- 创建: `backend/alembic/versions/007_add_health_check.py`

**Step 1: 创建新的迁移文件**

创建文件 `backend/alembic/versions/007_add_health_check.py`：

```python
"""Add health check configuration to projects table

Revision ID: 007_add_health_check
Revises: 006_add_git_ssh_key
Create Date: 2026-01-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_health_check'
down_revision: Union[str, None] = '006_add_git_ssh_key'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add health check configuration columns."""
    op.add_column('projects', sa.Column('health_check_enabled', sa.Boolean, nullable=False, server_default='false'))
    op.add_column('projects', sa.Column('health_check_type', sa.String(20), nullable=False, server_default='http'))
    op.add_column('projects', sa.Column('health_check_url', sa.String(500), nullable=True))
    op.add_column('projects', sa.Column('health_check_port', sa.Integer, nullable=True))
    op.add_column('projects', sa.Column('health_check_command', sa.Text, nullable=True))
    op.add_column('projects', sa.Column('health_check_timeout', sa.Integer, nullable=False, server_default='30'))
    op.add_column('projects', sa.Column('health_check_retries', sa.Integer, nullable=False, server_default='3'))
    op.add_column('projects', sa.Column('health_check_interval', sa.Integer, nullable=False, server_default='5'))


def downgrade() -> None:
    """Remove health check configuration columns."""
    op.drop_column('projects', 'health_check_interval')
    op.drop_column('projects', 'health_check_retries')
    op.drop_column('projects', 'health_check_timeout')
    op.drop_column('projects', 'health_check_command')
    op.drop_column('projects', 'health_check_port')
    op.drop_column('projects', 'health_check_url')
    op.drop_column('projects', 'health_check_type')
    op.drop_column('projects', 'health_check_enabled')
```

**Step 2: 验证迁移文件语法**

运行: `python -m py_compile backend/alembic/versions/007_add_health_check.py`
预期: 无输出（表示语法正确）

**Step 3: 提交迁移文件**

```bash
git add backend/alembic/versions/007_add_health_check.py
git commit -m "feat: 添加健康检查配置数据库迁移"
```

---

## Task 3: 创建健康检查服务 - 基础框架和异常类

**文件：**
- 创建: `backend/app/services/health_check_service.py`

**Step 1: 创建健康检查服务基础结构**

创建文件 `backend/app/services/health_check_service.py`：

```python
"""Health check service for verifying deployment status."""
import asyncio
import socket
from enum import Enum
from typing import TYPE_CHECKING

import httpx

from app.services.log_service import DeploymentLogger

if TYPE_CHECKING:
    from app.models.project import Project
    from app.core.ssh import SSHConnection


class HealthCheckType(str, Enum):
    """Health check types."""

    HTTP = "http"
    TCP = "tcp"
    COMMAND = "command"


class HealthCheckError(Exception):
    """Health check error."""

    pass
```

**Step 2: 验证基础结构导入**

运行: `python -c "from app.services.health_check_service import HealthCheckType, HealthCheckError; print('Import successful')"`
预期: `Import successful`

**Step 3: 提交基础结构**

```bash
git add backend/app/services/health_check_service.py
git commit -m "feat: 创建健康检查服务基础结构"
```

---

## Task 4: 实现 HTTP 健康检查

**文件：**
- 修改: `backend/app/services/health_check_service.py`

**Step 1: 添加 HTTP 健康检查方法**

在 `HealthCheckError` 类后添加 `HealthCheckService` 类和 HTTP 检查方法：

```python
class HealthCheckService:
    """Service for performing health checks."""

    def __init__(
        self,
        project: "Project",
        ssh_connection: "SSHConnection",
        logger: DeploymentLogger,
    ) -> None:
        """Initialize health check service.

        Args:
            project: Project model with health check configuration
            ssh_connection: SSH connection for command execution
            logger: Deployment logger for logging results
        """
        self.project = project
        self.ssh = ssh_connection
        self.logger = logger

    async def _check_http(self, url: str, timeout: int) -> bool:
        """Perform HTTP health check.

        Args:
            url: Health check URL
            timeout: Request timeout in seconds

        Returns:
            True if health check passes

        Raises:
            HealthCheckError: If health check fails
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
                if 200 <= response.status_code < 400:
                    await self.logger.info(f"HTTP 健康检查成功: {url} (状态码: {response.status_code})")
                    return True
                else:
                    raise HealthCheckError(
                        f"HTTP 健康检查失败: {url} (状态码: {response.status_code})"
                    )
        except httpx.TimeoutException:
            raise HealthCheckError(f"HTTP 健康检查超时: {url}")
        except httpx.RequestError as e:
            raise HealthCheckError(f"HTTP 健康检查请求失败: {e}")
```

**Step 2: 验证 HTTP 检查方法**

运行: `python -c "from app.services.health_check_service import HealthCheckService; print('HTTP check method added')"`
预期: `HTTP check method added`

**Step 3: 提交 HTTP 检查实现**

```bash
git add backend/app/services/health_check_service.py
git commit -m "feat: 实现 HTTP 健康检查方法"
```

---

## Task 5: 实现 TCP 健康检查

**文件：**
- 修改: `backend/app/services/health_check_service.py`

**Step 1: 添加 TCP 健康检查方法**

在 `_check_http` 方法后添加 TCP 检查方法：

```python
    async def _check_tcp(self, host: str, port: int, timeout: int) -> bool:
        """Perform TCP port health check.

        Args:
            host: Target host
            port: Target port
            timeout: Connection timeout in seconds

        Returns:
            True if health check passes

        Raises:
            HealthCheckError: If health check fails
        """
        try:
            # Try to connect via SSH to test TCP port
            # Use SSH connection to execute netcat command
            command = f"nc -z -w {timeout} {host} {port}"
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code == 0:
                await self.logger.info(f"TCP 健康检查成功: {host}:{port}")
                return True
            else:
                raise HealthCheckError(
                    f"TCP 健康检查失败: {host}:{port} - 端口不可达"
                )

        except HealthCheckError:
            raise
        except Exception as e:
            raise HealthCheckError(f"TCP 健康检查失败: {e}")
```

**Step 2: 验证 TCP 检查方法**

运行: `python -c "from app.services.health_check_service import HealthCheckService; print('TCP check method added')"`
预期: `TCP check method added`

**Step 3: 提交 TCP 检查实现**

```bash
git add backend/app/services/health_check_service.py
git commit -m "feat: 实现 TCP 健康检查方法"
```

---

## Task 6: 实现自定义命令健康检查

**文件：**
- 修改: `backend/app/services/health_check_service.py`

**Step 1: 添加命令健康检查方法**

在 `_check_tcp` 方法后添加命令检查方法：

```python
    async def _check_command(self, command: str, timeout: int) -> bool:
        """Perform custom command health check.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            True if health check passes

        Raises:
            HealthCheckError: If health check fails
        """
        try:
            await self.logger.info(f"执行自定义检查命令: {command}")
            exit_code, stdout, stderr = self.ssh.execute_command(command)

            if exit_code == 0:
                await self.logger.info(f"命令健康检查成功: 退出码 0")
                if stdout.strip():
                    await self.logger.info(f"命令输出: {stdout.strip()}")
                return True
            else:
                error_msg = f"命令健康检查失败: 退出码 {exit_code}"
                if stderr.strip():
                    error_msg += f"\n错误输出: {stderr.strip()}"
                raise HealthCheckError(error_msg)

        except HealthCheckError:
            raise
        except Exception as e:
            raise HealthCheckError(f"命令健康检查执行失败: {e}")
```

**Step 2: 验证命令检查方法**

运行: `python -c "from app.services.health_check_service import HealthCheckService; print('Command check method added')"`
预期: `Command check method added`

**Step 3: 提交命令检查实现**

```bash
git add backend/app/services/health_check_service.py
git commit -m "feat: 实现自定义命令健康检查方法"
```

---

## Task 7: 实现带重试的统一检查接口

**文件：**
- 修改: `backend/app/services/health_check_service.py`

**Step 1: 添加统一的检查方法**

在 `_check_command` 方法后添加统一的检查接口：

```python
    async def check(self) -> bool:
        """Perform health check with retry logic.

        Returns:
            True if health check passes

        Raises:
            HealthCheckError: If health check fails after all retries
        """
        if not self.project.health_check_enabled:
            await self.logger.info("健康检查未启用，跳过")
            return True

        check_type = HealthCheckType(self.project.health_check_type)
        max_retries = self.project.health_check_retries
        interval = self.project.health_check_interval
        timeout = self.project.health_check_timeout

        # Determine check target
        if check_type == HealthCheckType.HTTP:
            if not self.project.health_check_url:
                raise HealthCheckError("HTTP 健康检查需要配置 health_check_url")
            target = self.project.health_check_url
        elif check_type == HealthCheckType.TCP:
            if not self.project.health_check_port:
                raise HealthCheckError("TCP 健康检查需要配置 health_check_port")
            # Use SSH host for TCP check
            target = f"{self.ssh.config.host}:{self.project.health_check_port}"
        else:  # COMMAND
            if not self.project.health_check_command:
                raise HealthCheckError("命令健康检查需要配置 health_check_command")
            target = self.project.health_check_command[:50]

        await self.logger.info(f"开始健康检查: {check_type.value.upper()} - {target}")

        # Retry loop
        for attempt in range(1, max_retries + 1):
            try:
                if check_type == HealthCheckType.HTTP:
                    success = await self._check_http(
                        self.project.health_check_url, timeout
                    )
                elif check_type == HealthCheckType.TCP:
                    success = await self._check_tcp(
                        self.ssh.config.host,
                        self.project.health_check_port,
                        timeout,
                    )
                else:  # COMMAND
                    success = await self._check_command(
                        self.project.health_check_command, timeout
                    )

                if success:
                    await self.logger.info("健康检查成功: 服务状态正常")
                    return True

            except HealthCheckError as e:
                if attempt < max_retries:
                    await self.logger.warning(
                        f"健康检查失败，等待 {interval} 秒后重试 ({attempt}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(interval)
                else:
                    await self.logger.error(
                        f"健康检查失败，已达最大重试次数 ({max_retries}): {e}"
                    )
                    raise

        return False
```

**Step 2: 验证检查方法**

运行: `python -c "from app.services.health_check_service import HealthCheckService; print('Check method added')"`
预期: `Check method added`

**Step 3: 提交统一检查接口**

```bash
git add backend/app/services/health_check_service.py
git commit -m "feat: 实现带重试的统一健康检查接口"
```

---

## Task 8: 在部署流程中集成健康检查

**文件：**
- 修改: `backend/app/services/deploy_service.py`

**Step 1: 添加健康检查导入**

在文件顶部的 import 区域添加：

```python
from app.services.health_check_service import HealthCheckError, HealthCheckService
```

**Step 2: 在 _deploy_to_server 方法中集成健康检查**

在 `_deploy_to_server` 方法中，找到脚本执行成功后的部分（约第 295 行），在 `await self.logger.info(f"Successfully deployed to {server.name}")` 之前添加健康检查逻辑：

```python
                # Perform health check if enabled
                if self.deployment.project.health_check_enabled:
                    await self.logger.info("开始执行健康检查...")
                    try:
                        health_check_service = HealthCheckService(
                            project=self.deployment.project,
                            ssh_connection=conn,
                            logger=self.logger,
                        )
                        await health_check_service.check()
                    except HealthCheckError as e:
                        await self.logger.error(f"健康检查失败: {e}")
                        raise DeploymentError(f"健康检查失败: {e}")
                else:
                    await self.logger.info("健康检查未启用，跳过")
```

**Step 3: 验证集成**

运行: `python -c "from app.services.deploy_service import DeploymentService; print('Import successful')"`
预期: `Import successful`

**Step 4: 提交集成更改**

```bash
git add backend/app/services/deploy_service.py
git commit -m "feat: 在部署流程中集成健康检查"
```

---

## Task 9: 修复 Project 模型导入

**文件：**
- 修改: `backend/app/models/project.py`

**Step 1: 添加 Boolean 类型导入**

确保在文件顶部的导入中包含 Boolean：

```python
from sqlalchemy import Boolean, String, Text
```

如果已经存在其他导入，只需添加 Boolean。

**Step 2: 验证模型导入**

运行: `python -c "from app.models.project import Project; print('Model imported successfully')"`
预期: `Model imported successfully`

**Step 3: 提交修复**

```bash
git add backend/app/models/project.py
git commit -m "fix: 添加 Boolean 类型导入"
```

---

## Task 10: 运行数据库迁移

**Step 1: 应用数据库迁移**

运行: `cd backend && alembic upgrade head`
预期: `Running upgrade 006_add_git_ssh_key -> 007_add_health_check`

**Step 2: 验证数据库迁移**

运行: `cd backend && python -c "from app.models.project import Project; p = Project(health_check_enabled=True); print(f'Field exists: {hasattr(p, \"health_check_enabled\")}')"`
预期: `Field exists: True`

**Step 3: 提交迁移记录**

```bash
git add backend/alembic/versions/007_add_health_check.py
git commit -m "chore: 应用健康检查数据库迁移"
```

---

## Task 11: 创建健康检查功能测试

**文件：**
- 创建: `backend/tests/services/test_health_check_service.py`

**Step 1: 创建测试文件基础结构**

创建测试文件：

```python
"""Tests for health check service."""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.health_check_service import (
    HealthCheckService,
    HealthCheckType,
    HealthCheckError,
)
from app.services.log_service import DeploymentLogger


@pytest.fixture
def mock_project():
    """Create mock project with health check config."""
    project = Mock()
    project.health_check_enabled = True
    project.health_check_type = "http"
    project.health_check_url = "http://localhost:8080/health"
    project.health_check_port = 8080
    project.health_check_command = "systemctl status nginx"
    project.health_check_timeout = 30
    project.health_check_retries = 3
    project.health_check_interval = 5
    return project


@pytest.fixture
def mock_ssh_connection():
    """Create mock SSH connection."""
    ssh = Mock()
    ssh.config = Mock()
    ssh.config.host = "localhost"
    return ssh


@pytest.fixture
def mock_logger():
    """Create mock deployment logger."""
    logger = Mock(spec=DeploymentLogger)
    logger.info = AsyncMock()
    logger.warning = AsyncMock()
    logger.error = AsyncMock()
    return logger


@pytest.mark.asyncio
async def test_health_check_http_success(mock_project, mock_ssh_connection, mock_logger):
    """Test successful HTTP health check."""
    service = HealthCheckService(mock_project, mock_ssh_connection, mock_logger)

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await service.check()
        assert result is True
        await mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_health_check_http_failure(mock_project, mock_ssh_connection, mock_logger):
    """Test failed HTTP health check."""
    service = HealthCheckService(mock_project, mock_ssh_connection, mock_logger)

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(HealthCheckError):
            await service.check()


@pytest.mark.asyncio
async def test_health_check_disabled(mock_project, mock_ssh_connection, mock_logger):
    """Test health check when disabled."""
    mock_project.health_check_enabled = False
    service = HealthCheckService(mock_project, mock_ssh_connection, mock_logger)

    result = await service.check()
    assert result is True
```

**Step 2: 运行测试**

运行: `cd backend && pytest tests/services/test_health_check_service.py -v`
预期: 测试通过

**Step 3: 提交测试**

```bash
git add backend/tests/services/test_health_check_service.py
git commit -m "test: 添加健康检查服务单元测试"
```

---

## 测试指南

### 手动测试步骤

1. **更新项目配置**
   ```python
   # 在数据库或 API 中更新项目配置
   project.health_check_enabled = True
   project.health_check_type = "http"
   project.health_check_url = "http://your-server:8080/health"
   ```

2. **触发部署**
   - 通过 API 触发部署
   - 观察日志输出中的健康检查信息

3. **验证健康检查**
   - 成功场景：服务正常启动，健康检查通过
   - 失败场景：服务未启动，健康检查重试后失败
   - TCP 检查：配置端口号验证端口可达性
   - 命令检查：配置自定义命令验证服务状态

### 日志输出示例

```
INFO 开始执行健康检查...
INFO 开始健康检查: HTTP - http://localhost:8080/health
INFO HTTP 健康检查成功: http://localhost:8080/health (状态码: 200)
INFO 健康检查成功: 服务状态正常
```

---

## 注意事项

1. **网络连接**：HTTP 健康检查需要部署服务器能够访问健康检查 URL
2. **防火墙规则**：TCP 检查需要确保目标端口可访问
3. **命令安全**：自定义命令检查需要谨慎使用，避免执行危险命令
4. **超时配置**：根据服务启动时间合理配置超时和重试参数
5. **日志监控**：通过部署日志实时监控健康检查状态

---

## 完成检查清单

- [ ] Project 模型添加健康检查字段
- [ ] 创建并应用数据库迁移
- [ ] 实现 HealthCheckService
- [ ] 实现 HTTP 健康检查
- [ ] 实现 TCP 健康检查
- [ ] 实现命令健康检查
- [ ] 实现重试机制
- [ ] 集成到部署流程
- [ ] 添加单元测试
- [ ] 手动测试验证
