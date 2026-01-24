# 仅重启脚本增强设计文档

**日期:** 2025-01-24
**作者:** Claude
**状态:** 已批准

## 需求概述

1. 新增独立的仅重启脚本配置字段，与常规部署重启脚本分离
2. 执行脚本时自动切换到脚本所在目录后再执行

## 设计方案

### 一、数据库模型变更

#### Project 模型新增字段

```python
# 仅重启部署模式专用的重启脚本路径
restart_only_script_path: Mapped[str | None] = mapped_column(
    String(255), nullable=True, default=None
)
```

**字段说明:**
- 类型: `String(255)`, 与 `restart_script_path` 保持一致
- 可空: `True`, 允许项目不配置仅重启脚本
- 默认值: `None`

**部署逻辑:**
- 仅重启部署模式 (`DeploymentType.RESTART_ONLY`) 时, **只**使用 `restart_only_script_path`
- 如果 `restart_only_script_path` 未配置, 抛出错误
- 常规部署流程继续使用 `restart_script_path`, 两者互不影响

---

### 二、脚本目录切换逻辑

#### 核心函数: 提取脚本工作目录

```python
from pathlib import Path

def get_script_execution_info(script_path: str) -> dict:
    """解析脚本路径, 返回执行信息。

    Args:
        script_path: 脚本路径 (绝对路径或相对路径)

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
            working_dir = str(path.parent)
        else:
            working_dir = '.'
        script_name = path.name

    # 构建执行命令: cd 到工作目录 && 执行脚本
    command = f"cd {working_dir} && bash ./{script_name}"

    return {
        "working_dir": working_dir,
        "command": command,
        "script_name": script_name
    }
```

**示例输出:**

| 输入 | working_dir | command |
|------|-------------|---------|
| `/application/back/charge-back/restartFromTemp.sh` | `/application/back/charge-back` | `cd /application/back/charge-back && bash ./restartFromTemp.sh` |
| `./scripts/restart.sh` | `./scripts` | `cd ./scripts && bash ./restart.sh` |
| `restart.sh` | `.` | `cd . && bash ./restart.sh` |

---

### 三、部署服务代码变更

#### 1. 更新 `_restart_server` 方法 (仅重启部署)

修改 `deploy_service.py` 中的 `_restart_server` 方法:

```python
async def _restart_server(self, server: Server) -> None:
    """Restart service on a single server.

    Args:
        server: Server to restart

    Raises:
        DeploymentError: If restart fails
    """
    await self.logger.info(f"Restarting on server: {server.name} ({server.host})")

    # 检查是否配置了仅重启脚本
    if not self.deployment.project.restart_only_script_path:
        raise DeploymentError(
            f"项目 {self.deployment.project.name} 未配置仅重启脚本路径，无法执行仅重启部署"
        )

    try:
        # 获取脚本执行信息
        exec_info = get_script_execution_info(
            self.deployment.project.restart_only_script_path
        )

        await self.logger.info(f"工作目录: {exec_info['working_dir']}")
        await self.logger.info(f"执行脚本: {exec_info['script_name']}")

        conn = create_ssh_connection(server)

        with conn:
            exit_code, stdout, stderr = conn.execute_command(exec_info['command'])

            if exit_code != 0:
                raise DeploymentError(f"重启脚本执行失败: {stderr}")

            await self.logger.info("重启脚本执行成功")
            await self.logger.info(f"成功重启 {server.name}")

    except DeploymentError:
        raise
    except Exception as e:
        raise DeploymentError(f"重启失败 {server.name}: {e}") from e
```

#### 2. 更新 `_deploy_to_server` 方法 (常规部署)

在常规部署流程中, 执行 `restart_script_path` 时也使用相同逻辑:

```python
# 在 _deploy_to_server 方法中, 替换原有的重启脚本执行逻辑
if project.restart_script_path:
    # 获取脚本执行信息
    exec_info = get_script_execution_info(project.restart_script_path)

    await self.logger.info(f"工作目录: {exec_info['working_dir']}")
    await self.logger.info(f"执行脚本: {exec_info['script_name']}")

    # 使用 streaming 或 minimal 模式执行命令
    if settings.deployment_log_verbosity == "minimal":
        exit_code, stdout, stderr = conn.execute_command(exec_info['command'])
        # ... 错误处理逻辑
    else:
        exit_code, stdout, stderr = conn.execute_command_streaming(
            exec_info['command'],
            on_stdout=lambda line: asyncio.create_task(
                self.logger.info(f"[stdout] {line}")
            ),
            on_stderr=lambda line: asyncio.create_task(
                self.logger.info(f"[stderr] {line}")
            ),
        )
        # ... 错误处理逻辑
```

---

### 四、数据库迁移

#### Alembic 迁移脚本

创建新的迁移文件, 添加 `restart_only_script_path` 字段:

```python
# revision identifier
revision = '011_add_restart_only_script_path'
down_revision = '010_add_git_username_password'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column(
        'projects',
        sa.Column(
            'restart_only_script_path',
            sa.String(255),
            nullable=True,
            default=None
        )
    )

def downgrade():
    op.drop_column('projects', 'restart_only_script_path')
```

**迁移说明:**
- 字段可空, 已有项目不受影响
- 新项目可选择配置此字段以启用仅重启部署功能

---

### 五、API Schema 变更

#### Project Schema 更新

修改 `backend/app/schemas/project.py`, 在 `ProjectBase` 和 `ProjectResponse` 中添加新字段:

```python
class ProjectBase(BaseModel):
    # ... 现有字段 ...

    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )

class ProjectResponse(ProjectBase):
    # ... 现有字段 ...

    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )

class ProjectCreate(ProjectBase):
    # ... 继承新字段 ...
    pass

class ProjectUpdate(ProjectBase):
    # ... 继承新字段 ...
    pass
```

**API 影响:**
- `POST /api/projects` - 创建项目时可配置 `restart_only_script_path`
- `PUT /api/projects/{id}` - 更新项目时可修改 `restart_only_script_path`
- `GET /api/projects` - 返回项目列表时包含 `restart_only_script_path`
- `GET /api/projects/{id}` - 返回项目详情时包含 `restart_only_script_path`

---

### 六、前端界面变更

#### 项目表单新增字段

在 `frontend/src/views/ProjectList.vue` 或相关表单组件中, 添加 `restart_only_script_path` 输入框:

```vue
<el-form-item label="仅重启脚本路径" prop="restart_only_script_path">
  <el-input
    v-model="projectForm.restart_only_script_path"
    placeholder="例如: /application/back/charge-back/restartFromTemp.sh"
    clearable
  >
    <template #prepend>
      <el-tooltip content="仅重启部署模式专用的重启脚本路径，不配置则无法使用仅重启部署">
        <el-icon><QuestionFilled /></el-icon>
      </el-tooltip>
    </template>
  </el-input>
  <div class="form-tip">
    执行时会自动 cd 到脚本所在目录后再执行脚本
  </div>
</el-form-item>
```

**UI 说明:**
- 放置在现有的"重启脚本路径"字段下方
- 添加 tooltip 说明字段用途
- 添加提示文字说明自动切换目录的行为
- 示例占位符帮助用户理解格式

---

### 七、测试计划

#### 测试场景

**1. 单元测试 - `get_script_execution_info` 函数**

```python
# 测试用例
def test_get_script_execution_info_absolute_path():
    info = get_script_execution_info("/app/dir/script.sh")
    assert info["working_dir"] == "/app/dir"
    assert info["command"] == "cd /app/dir && bash ./script.sh"

def test_get_script_execution_info_relative_path():
    info = get_script_execution_info("./scripts/restart.sh")
    assert info["working_dir"] == "./scripts"
    assert info["command"] == "cd ./scripts && bash ./restart.sh"

def test_get_script_execution_info_simple_name():
    info = get_script_execution_info("restart.sh")
    assert info["working_dir"] == "."
    assert info["command"] == "cd . && bash ./restart.sh"
```

**2. 集成测试 - 仅重启部署流程**
- 创建项目, 配置 `restart_only_script_path`
- 执行仅重启部署, 验证脚本在正确目录下执行
- 未配置 `restart_only_script_path` 时, 验证报错信息

**3. 手动验证场景**

| 场景 | 脚本路径 | 预期工作目录 | 预期命令 |
|------|----------|-------------|---------|
| 绝对路径 | `/a/b/c/restart.sh` | `/a/b/c` | `cd /a/b/c && bash ./restart.sh` |
| 相对路径带./ | `./scripts/restart.sh` | `./scripts` | `cd ./scripts && bash ./restart.sh` |
| 仅文件名 | `restart.sh` | `.` | `cd . && bash ./restart.sh` |

---

## 实施文件清单

### 后端
1. `backend/app/models/project.py` - 添加 `restart_only_script_path` 字段
2. `backend/app/services/deploy_service.py` - 更新 `_restart_server` 和 `_deploy_to_server` 方法
3. `backend/app/schemas/project.py` - 更新 Project Schema
4. `backend/alembic/versions/011_add_restart_only_script_path.py` - 数据库迁移
5. `backend/app/utils/script_utils.py` - 新增 `get_script_execution_info` 工具函数

### 前端
1. `frontend/src/views/ProjectList.vue` - 添加表单字段
2. `frontend/src/api/project.js` - 确保API支持新字段 (通常自动支持)

---

## 风险评估

1. **向后兼容性**: 低风险 - 新字段可空, 不影响现有项目
2. **数据迁移**: 低风险 - 仅添加字段, 无数据迁移
3. **API 兼容性**: 低风险 - 新增可选字段, 现有API调用不受影响
