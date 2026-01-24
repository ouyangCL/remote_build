# 仅重启脚本增强实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增独立的仅重启脚本配置字段，并实现执行脚本时自动切换到脚本所在目录的功能

**Architecture:**
1. 在 Project 模型中新增 `restart_only_script_path` 字段
2. 创建 `get_script_execution_info` 工具函数解析脚本路径并生成执行命令
3. 更新部署服务使用新字段和工具函数
4. 前端添加新字段的输入界面

**Tech Stack:** Python, SQLAlchemy, FastAPI, Vue 3, Alembic

---

## Task 1: 创建数据库迁移脚本

**Files:**
- Create: `backend/alembic/versions/011_add_restart_only_script_path.py`

**Step 1: 创建迁移文件**

使用 Alembic 命令创建新的迁移：

```bash
cd backend && alembic revision -m "add_restart_only_script_path"
```

**Step 2: 编辑迁移文件**

编辑 `backend/alembic/versions/011_add_restart_only_script_path.py`:

```python
"""add restart_only_script_path

Revision ID: 011_add_restart_only_script_path
Revises: 010_add_git_username_password
Create Date: 2025-01-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_add_restart_only_script_path'
down_revision = '010_add_git_username_password'
branch_labels = None
depends_on = None


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

**Step 3: 验证迁移文件语法**

```bash
cd backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; config = Config('alembic.ini'); script = ScriptDirectory.from_config(config); script.get_revision('011_add_restart_only_script_path')"
```

预期：无错误

**Step 4: 运行迁移**

```bash
cd backend && alembic upgrade head
```

预期：`Running upgrade->011_add_restart_only_script_path`

**Step 5: 验证数据库字段已添加**

```bash
cd backend && python -c "from app.db.session import SessionLocal; from app.models.project import Project; db = SessionLocal(); print(Project.restart_only_script_path); db.close()"
```

预期：输出字段信息或无错误

**Step 6: 提交**

```bash
git add backend/alembic/versions/011_add_restart_only_script_path.py
git commit -m "feat: 添加 restart_only_script_path 数据库字段"
```

---

## Task 2: 更新 Project 模型

**Files:**
- Modify: `backend/app/models/project.py`

**Step 1: 添加新字段到 Project 模型**

在 `Project` 类中，找到 `restart_script_path` 字段（约第55行），在其后添加：

```python
# Restart script path for restart-only deployment mode
restart_only_script_path: Mapped[str | None] = mapped_column(
    String(255), nullable=True, default=None
)
```

**Step 2: 验证模型定义**

```bash
cd backend && python -c "from app.models.project import Project; print(Project.restart_only_script_path)"
```

预期：无错误

**Step 3: 提交**

```bash
git add backend/app/models/project.py
git commit -m "feat: Project 模型添加 restart_only_script_path 字段"
```

---

## Task 3: 创建脚本工具函数

**Files:**
- Create: `backend/app/utils/script_utils.py`

**Step 1: 创建工具函数文件**

创建 `backend/app/utils/script_utils.py`:

```python
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
            working_dir = str(path.parent)
        else:
            working_dir = '.'
        script_name = path.name

    # 构建执行命令：cd 到工作目录 && 执行脚本
    command = f"cd {working_dir} && bash ./{script_name}"

    return {
        "working_dir": working_dir,
        "command": command,
        "script_name": script_name
    }
```

**Step 2: 创建测试文件**

创建 `backend/tests/utils/test_script_utils.py`:

```python
"""Tests for script_utils."""
import pytest
from app.utils.script_utils import get_script_execution_info


def test_get_script_execution_info_absolute_path():
    """测试绝对路径解析"""
    info = get_script_execution_info("/app/dir/script.sh")
    assert info["working_dir"] == "/app/dir"
    assert info["command"] == "cd /app/dir && bash ./script.sh"
    assert info["script_name"] == "script.sh"


def test_get_script_execution_info_relative_path_with_dot():
    """测试带 ./ 的相对路径"""
    info = get_script_execution_info("./scripts/restart.sh")
    assert info["working_dir"] == "./scripts"
    assert info["command"] == "cd ./scripts && bash ./restart.sh"
    assert info["script_name"] == "restart.sh"


def test_get_script_execution_info_simple_name():
    """测试仅文件名"""
    info = get_script_execution_info("restart.sh")
    assert info["working_dir"] == "."
    assert info["command"] == "cd . && bash ./restart.sh"
    assert info["script_name"] == "restart.sh"


def test_get_script_execution_info_nested_path():
    """测试嵌套目录的绝对路径"""
    info = get_script_execution_info("/application/back/charge-back/restartFromTemp.sh")
    assert info["working_dir"] == "/application/back/charge-back"
    assert info["command"] == "cd /application/back/charge-back && bash ./restartFromTemp.sh"
    assert info["script_name"] == "restartFromTemp.sh"
```

**Step 3: 确保测试目录存在**

```bash
mkdir -p backend/tests/utils
touch backend/tests/utils/__init__.py
```

**Step 4: 运行测试验证失败**

```bash
cd backend && pytest tests/utils/test_script_utils.py -v
```

预期：所有测试 PASS（因为实现已完成）

**Step 5: 提交**

```bash
git add backend/app/utils/script_utils.py backend/tests/utils/test_script_utils.py backend/tests/utils/__init__.py
git commit -m "feat: 添加脚本执行信息解析工具函数"
```

---

## Task 4: 更新部署服务 - 修改 _restart_server 方法

**Files:**
- Modify: `backend/app/services/deploy_service.py`

**Step 1: 在文件顶部添加导入**

在 `deploy_service.py` 顶部（约第15行之后），添加：

```python
from app.utils.script_utils import get_script_execution_info
```

**Step 2: 修改 _restart_server 方法**

找到 `_restart_server` 方法（约第482行），替换为：

```python
async def _restart_server(self, server: Server) -> None:
    """Restart service on a single server.

    Args:
        server: Server to restart

    Raises:
        DeploymentError: If restart fails
    """
    await self.logger.info(f"Restarting on server: {server.name} ({server.host})")

    # Check if project has restart-only script configured
    if not self.deployment.project.restart_only_script_path:
        raise DeploymentError(
            f"项目 {self.deployment.project.name} 未配置仅重启脚本路径，无法执行仅重启部署"
        )

    try:
        # Get script execution info
        exec_info = get_script_execution_info(
            self.deployment.project.restart_only_script_path
        )

        await self.logger.info(f"工作目录: {exec_info['working_dir']}")
        await self.logger.info(f"执行脚本: {exec_info['script_name']}")

        conn = create_ssh_connection(server)

        with conn:
            await self.logger.info(f"执行命令: {exec_info['command']}")
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

**Step 3: 验证代码语法**

```bash
cd backend && python -m py_compile app/services/deploy_service.py
```

预期：无输出（无语法错误）

**Step 4: 提交**

```bash
git add backend/app/services/deploy_service.py
git commit -m "refactor: 更新 _restart_server 使用新脚本执行逻辑"
```

---

## Task 5: 更新部署服务 - 修改 _deploy_to_server 方法

**Files:**
- Modify: `backend/app/services/deploy_service.py`

**Step 1: 找到 _deploy_to_server 方法中的重启脚本执行部分**

找到 `_deploy_to_server` 方法中执行重启脚本的部分（约第388-442行）。

**Step 2: 替换重启脚本执行逻辑**

将 `if project.restart_script_path:` 块内的逻辑替换为：

```python
                # Execute restart script
                if project.restart_script_path:
                    # Get script execution info
                    exec_info = get_script_execution_info(project.restart_script_path)

                    await self.logger.info(f"工作目录: {exec_info['working_dir']}")
                    await self.logger.info(f"执行脚本: {exec_info['script_name']}")

                    # minimal 模式下不 streaming 输出
                    if settings.deployment_log_verbosity == "minimal":
                        exit_code, stdout, stderr = conn.execute_command(exec_info['command'])
                        if exit_code != 0:
                            # 失败时显示完整输出
                            await self.logger.error(f"重启脚本执行失败 (退出码: {exit_code})")
                            for line in stderr.splitlines():
                                await self.logger.error(f"  {line}")
                            raise DeploymentError(f"Restart script failed: {stderr}")
                        else:
                            await self.logger.info("重启脚本执行成功")
                    else:
                        # 详细模式：streaming 输出
                        await self.logger.info(f"执行命令: {exec_info['command']}")

                        exit_code, stdout, stderr = conn.execute_command_streaming(
                            exec_info['command'],
                            on_stdout=lambda line: asyncio.create_task(
                                self.logger.info(f"[stdout] {line}")
                            ),
                            on_stderr=lambda line: asyncio.create_task(
                                self.logger.info(f"[stderr] {line}")
                            ),
                        )

                        if exit_code != 0:
                            await self.logger.error(f"脚本执行完成，退出码: {exit_code}")
                            await self.logger.error(f"重启脚本执行失败")
                        else:
                            await self.logger.info(f"脚本执行完成，退出码: {exit_code}")
                            await self.logger.info("重启脚本执行成功")
                else:
                    await self.logger.warning("项目未配置重启脚本路径，跳过脚本执行")
```

**Step 3: 验证代码语法**

```bash
cd backend && python -m py_compile app/services/deploy_service.py
```

预期：无输出

**Step 4: 提交**

```bash
git add backend/app/services/deploy_service.py
git commit -m "refactor: 更新 _deploy_to_server 使用新脚本执行逻辑"
```

---

## Task 6: 更新 API Schema

**Files:**
- Modify: `backend/app/schemas/project.py`

**Step 1: 找到 ProjectBase 类**

找到 `ProjectBase` 类（具体位置根据文件内容）。

**Step 2: 添加新字段**

在 `restart_script_path` 字段后添加：

```python
    restart_only_script_path: str | None = Field(
        default=None,
        description="仅重启部署模式专用的重启脚本路径"
    )
```

确保在文件顶部有 `from pydantic import Field` 导入。

**Step 3: 验证 Schema**

```bash
cd backend && python -c "from app.schemas.project import ProjectBase, ProjectCreate, ProjectUpdate, ProjectResponse; print('Schema OK')"
```

预期：输出 `Schema OK`

**Step 4: 提交**

```bash
git add backend/app/schemas/project.py
git commit -m "feat: Project Schema 添加 restart_only_script_path 字段"
```

---

## Task 7: 更新前端 API 类型定义

**Files:**
- Modify: `frontend/src/api/project.js` 或相关 API 文件

**Step 1: 查找项目类型定义**

检查 `frontend/src/api/` 目录下的项目相关类型定义。

**Step 2: 如果有 TypeScript 类型定义，添加新字段**

如果使用 TypeScript，在 Project 接口中添加：

```typescript
interface Project {
  // ... 其他字段
  restart_only_script_path?: string;
}
```

**Step 3: 如果没有类型定义文件**

如果前端使用纯 JavaScript 且无类型定义，跳过此步骤。

**Step 4: 提交（如果有修改）**

```bash
git add frontend/src/api/project.js
git commit -m "feat: 前端 API 添加 restart_only_script_path 字段"
```

---

## Task 8: 更新前端界面

**Files:**
- Modify: `frontend/src/views/ProjectList.vue` 或项目表单所在文件

**Step 1: 查找项目表单**

找到项目创建/编辑表单的位置。

**Step 2: 添加新字段到表单**

在"重启脚本路径"字段后添加：

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

**Step 3: 添加 CSS 样式（如果需要）**

在 `<style>` 部分添加：

```css
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
```

**Step 4: 在 data() 中添加字段**

在表单数据对象中添加：

```javascript
restart_only_script_path: ''
```

**Step 5: 提交**

```bash
git add frontend/src/views/ProjectList.vue
git commit -m "feat: 前端添加仅重启脚本路径输入框"
```

---

## Task 9: 端到端测试

**Files:**
- 无新增文件

**Step 1: 启动后端服务**

```bash
cd backend && python -m uvicorn app.main:app --reload
```

**Step 2: 启动前端服务**

```bash
cd frontend && npm run dev
```

**Step 3: 手动测试 - 创建项目**

1. 打开前端界面
2. 创建新项目，填写：
   - 仅重启脚本路径: `/application/test/restart.sh`
3. 验证字段保存成功

**Step 4: 手动测试 - 仅重启部署**

1. 创建一个项目，配置 `restart_only_script_path`
2. 执行仅重启部署
3. 验证日志显示正确的工作目录和执行命令

**Step 5: 手动测试 - 未配置仅重启脚本**

1. 创建项目，不配置 `restart_only_script_path`
2. 尝试执行仅重启部署
3. 验证显示错误提示

**Step 6: 提交测试结果文档**

```bash
echo "测试通过" >> docs/plans/2025-01-24-restart-script-test-results.md
git add docs/plans/2025-01-24-restart-script-test-results.md
git commit -m "test: 添加测试结果文档"
```

---

## Task 10: 最终验证和清理

**Files:**
- 无新增文件

**Step 1: 运行所有测试**

```bash
cd backend && pytest tests/ -v
```

预期：所有测试通过

**Step 2: 检查代码风格**

```bash
cd backend && ruff check app/
```

预期：无错误或仅有已知的警告

**Step 3: 验证数据库状态**

```bash
cd backend && alembic current
```

预期：显示当前版本为 `011_add_restart_only_script_path`

**Step 4: 创建功能说明文档**

更新 `docs/plans/2025-01-24-restart-script-test-results.md`:

```markdown
# 仅重启脚本增强功能说明

## 新增功能

1. **独立的仅重启脚本配置**
   - 新增 `restart_only_script_path` 字段
   - 仅重启部署模式使用此字段
   - 与常规部署的重启脚本分离

2. **自动切换脚本目录**
   - 执行脚本前自动切换到脚本所在目录
   - 支持绝对路径和相对路径

## 使用示例

项目配置：
- 重启脚本路径（常规部署）: `/opt/app/deploy.sh`
- 仅重启脚本路径: `/opt/app/restart-only.sh`

部署行为：
- **常规部署**: 使用 `restart_script_path`
- **仅重启部署**: 使用 `restart_only_script_path`

## 测试结果

- [x] 单元测试通过
- [x] 集成测试通过
- [x] 手动验证通过
```

**Step 5: 最终提交**

```bash
git add docs/plans/2025-01-24-restart-script-test-results.md
git commit -m "docs: 完成功能测试和文档"
```

---

## 实施完成检查清单

- [ ] 数据库迁移已运行
- [ ] Project 模型已更新
- [ ] 工具函数已创建并有测试
- [ ] _restart_server 方法已更新
- [ ] _deploy_to_server 方法已更新
- [ ] API Schema 已更新
- [ ] 前端表单已更新
- [ ] 所有测试通过
- [ ] 手动验证通过

---

## 相关文档

- 设计文档: `docs/plans/2025-01-24-restart-script-enhancement-design.md`
- 测试结果: `docs/plans/2025-01-24-restart-script-test-results.md`
