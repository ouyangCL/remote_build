# 仅重启部署模式实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增"仅重启"部署模式，允许跳过克隆、构建、上传步骤，直接在服务器上执行重启脚本并进行进程健康检查。

**Architecture:** 扩展现有 Deployment 模型和 Service 层，通过 DeploymentType 枚举区分完整部署和仅重启模式，在 deploy() 方法中根据类型分发到不同执行路径。

**Tech Stack:** Python/FastAPI (后端), SQLAlchemy (ORM), TypeScript/Vue (前端), SSH (远程执行)

---

### Task 1: 添加 DeploymentType 枚举

**Files:**
- Modify: `backend/app/models/deployment.py`

**Step 1: 添加枚举定义**

在 `DeploymentStatus` 枚举之前添加：

```python
class DeploymentType(str, enum.Enum):
    """Deployment type."""

    FULL = "full"  # Full deployment with clone, build, upload
    RESTART_ONLY = "restart_only"  # Restart only, no build
```

**Step 2: 在 DeploymentStatus 中添加 RESTARTING 状态**

在现有状态中添加：

```python
RESTARTING = "restarting"  # For restart_only mode
```

**Step 3: 在 Deployment 模型中添加 deployment_type 字段**

在 `environment` 字段后添加：

```python
deployment_type: Mapped[DeploymentType] = mapped_column(
    String(20), default=DeploymentType.FULL, nullable=False
)
```

**Step 4: 创建数据库迁移**

```bash
cd backend
alembic revision --autogenerate -m "add deployment_type"
```

检查生成的迁移文件，确认包含 `deployment_type` 列。

**Step 5: 应用迁移**

```bash
alembic upgrade head
```

**Step 6: 提交**

```bash
git add backend/app/models/deployment.py backend/alembic/versions/
git commit -m "feat: 添加 DeploymentType 枚举和 deployment_type 字段"
```

---

### Task 2: 更新 Schema

**Files:**
- Modify: `backend/app/schemas/deployment.py`

**Step 1: 导入 DeploymentType**

```python
from app.models.deployment import DeploymentType
```

**Step 2: 修改 DeploymentCreate schema**

```python
class DeploymentCreate(BaseModel):
    """Deployment creation schema."""

    project_id: int = Field(..., ge=1)
    branch: str = Field(..., min_length=1, max_length=100)
    server_group_ids: list[int] = Field(..., min_length=1)
    deployment_type: DeploymentType = Field(default=DeploymentType.FULL)
```

**Step 3: 更新 DeploymentResponse schema**

```python
class DeploymentResponse(BaseModel):
    """Deployment response schema."""

    id: int
    project_id: int
    branch: str
    status: str
    deployment_type: DeploymentType  # 新增
    commit_hash: str | None = None
    commit_message: str | None = None
    error_message: str | None = None
    created_at: datetime
    created_by: int | None = None
    rollback_from: int | None = None
    environment: str = "development"

    model_config = {"from_attributes": True}
```

**Step 4: 提交**

```bash
git add backend/app/schemas/deployment.py
git commit -m "feat: 更新 deployment schema 支持 deployment_type"
```

---

### Task 3: API 层支持 deployment_type

**Files:**
- Modify: `backend/app/api/deployments.py`

**Step 1: 更新 create_deployment 函数**

在创建 deployment 对象时传入 deployment_type：

```python
# Create deployment - inherit environment from project
deployment = Deployment(
    project_id=deployment_data.project_id,
    branch=deployment_data.branch,
    status=DeploymentStatus.PENDING,
    created_by=current_user.id,
    server_groups=server_groups,
    environment=project.environment,
    deployment_type=deployment_data.deployment_type,  # 新增
)
```

**Step 2: 提交**

```bash
git add backend/app/api/deployments.py
git commit -m "feat: API 支持 deployment_type 参数"
```

---

### Task 4: Service 层添加仅重启方法

**Files:**
- Modify: `backend/app/services/deploy_service.py`

**Step 1: 修改 deploy() 方法支持分支**

将现有的 `deploy()` 方法重构为：

```python
async def deploy(self) -> None:
    """Execute deployment process.

    Raises:
        DeploymentError: If deployment fails
    """
    try:
        project = self.deployment.project

        if self.deployment.deployment_type == DeploymentType.RESTART_ONLY:
            await self._restart_only_deploy()
        else:
            await self._full_deploy()

    except Exception as e:
        await self._update_status(DeploymentStatus.FAILED, str(e))
        await self.logger.error(f"Deployment failed: {e}")
        raise DeploymentError(f"Deployment failed: {e}") from e
```

**Step 2: 将原有 deploy 逻辑重命名为 _full_deploy**

将原 `deploy()` 方法体移到新方法 `_full_deploy()` 中：

```python
async def _full_deploy(self) -> None:
    """Execute full deployment process (clone, build, deploy).

    Raises:
        DeploymentError: If deployment fails
    """
    project = self.deployment.project
    await self.logger.info(f"Starting full deployment: {project.name} ({self.deployment.branch})")

    # Step 1: Clone repository
    await self._update_status(DeploymentStatus.CLONING)
    await self._clone_repo()

    if self._cancelled:
        await self._handle_cancel()
        return

    # Step 2: Build project
    await self._update_status(DeploymentStatus.BUILDING)
    artifact_info = await self._build_project()

    if self._cancelled:
        await self._handle_cancel()
        return

    # Step 3: Deploy to servers
    await self._update_status(DeploymentStatus.DEPLOYING)
    await self._deploy_to_servers(artifact_info["path"])

    # Step 4: Success
    await self._update_status(DeploymentStatus.SUCCESS)
    await self.logger.info("Deployment completed successfully")
```

**Step 3: 实现 _restart_only_deploy 方法**

在 `_full_deploy` 方法后添加：

```python
async def _restart_only_deploy(self) -> None:
    """Execute restart-only deployment (no clone, no build).

    Raises:
        DeploymentError: If deployment fails
    """
    project = self.deployment.project
    await self.logger.info(f"Starting restart-only deployment: {project.name}")

    # Update status to restarting
    await self._update_status(DeploymentStatus.RESTARTING)

    if self._cancelled:
        await self._handle_cancel()
        return

    # Restart servers
    await self._restart_servers()

    if self._cancelled:
        await self._handle_cancel()
        return

    # Success
    await self._update_status(DeploymentStatus.SUCCESS)
    await self.logger.info("Restart-only deployment completed successfully")
```

**Step 4: 实现 _restart_servers 方法**

```python
async def _restart_servers(self) -> None:
    """Restart services on all servers.

    Raises:
        DeploymentError: If restart fails
    """
    server_groups = self.deployment.server_groups

    await self.logger.info(f"Restarting on {len(server_groups)} server group(s)")

    failed_servers = []

    for group in server_groups:
        await self.logger.info(f"Restarting in server group: {group.name}")

        for server in group.servers:
            if not server.is_active:
                await self.logger.warning(f"Skipping inactive server: {server.name}")
                continue

            try:
                await self._restart_server(server)
            except DeploymentError as e:
                await self.logger.error(f"Failed to restart {server.name}: {e}")
                failed_servers.append(server.name)

    if failed_servers:
        await self._update_status(
            DeploymentStatus.FAILED,
            f"Failed to restart servers: {', '.join(failed_servers)}"
        )
        raise DeploymentError(f"Failed to restart servers: {', '.join(failed_servers)}")
```

**Step 5: 实现 _restart_server 方法**

```python
async def _restart_server(self, server: Server) -> None:
    """Restart service on a single server.

    Args:
        server: Server to restart

    Raises:
        DeploymentError: If restart fails
    """
    await self.logger.info(f"Restarting on server: {server.name} ({server.host})")

    # Check if project has restart script configured
    if not self.deployment.project.deploy_script_path:
        raise DeploymentError(
            f"Project {self.deployment.project.name} has no deploy_script_path configured"
        )

    try:
        conn = create_ssh_connection(server)

        with conn:
            # Execute restart script
            await self.logger.info(
                f"Executing restart script: {self.deployment.project.deploy_script_path}"
            )
            exit_code, stdout, stderr = conn.execute_command(
                f"bash {self.deployment.project.deploy_script_path}"
            )

            if exit_code != 0:
                raise DeploymentError(f"Restart script failed: {stderr}")

            await self.logger.info("Restart script executed successfully")

            # Health check - verify process is running
            await self._health_check(conn, server)

            await self.logger.info(f"Successfully restarted on {server.name}")

    except DeploymentError:
        raise
    except Exception as e:
        raise DeploymentError(f"Failed to restart on {server.name}: {e}") from e
```

**Step 6: 实现 _health_check 方法**

```python
async def _health_check(self, conn: SSHConnection, server: Server) -> None:
    """Check if service process is running after restart.

    Args:
        conn: SSH connection
        server: Server being checked

    Raises:
        DeploymentError: If health check fails
    """
    await self.logger.info("Performing health check...")

    # Get project name for process matching
    process_name = self.deployment.project.name.lower().replace(" ", "").replace("-", "")

    # Check if process is running
    exit_code, stdout, stderr = conn.execute_command(
        f"ps aux | grep -E '{process_name}|python|node|java' | grep -v grep | head -1"
    )

    if exit_code == 0 and stdout.strip():
        await self.logger.info(f"Health check passed: Process running")
    else:
        await self.logger.warning(f"Health check inconclusive: Could not verify process status")
        # Don't fail deployment, just warn
```

**Step 7: 提交**

```bash
git add backend/app/services/deploy_service.py
git commit -m "feat: 实现仅重启部署模式"
```

---

### Task 5: 前端 API 更新

**Files:**
- Modify: `frontend/src/api/deployments.ts`

**Step 1: 更新 create 函数类型**

```typescript
create: (data: {
  project_id: number
  branch?: string  // 仅重启时可选
  server_group_ids: number[]
  deployment_type?: 'full' | 'restart_only'
}): Promise<Deployment> => api.post('/deployments', data),
```

**Step 2: 提交**

```bash
git add frontend/src/api/deployments.ts
git commit -m "feat: 前端 API 支持 deployment_type 参数"
```

---

### Task 6: 前端类型定义

**Files:**
- Modify: `frontend/src/types/index.ts` (或相应的类型文件)

**Step 1: 更新 Deployment 类型**

```typescript
export interface Deployment {
  id: number
  project_id: number
  branch: string
  status: string
  deployment_type?: 'full' | 'restart_only'  // 新增
  commit_hash?: string
  commit_message?: string
  error_message?: string
  created_at: string
  created_by?: number
  rollback_from?: number
  environment: string
  project?: {
    id: number
    name: string
    project_type: string
  }
  server_groups?: Array<{
    id: number
    name: string
  }>
  logs?: Array<{
    id: number
    level: string
    content: string
    timestamp: string
  }>
}
```

**Step 2: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: 更新 Deployment 类型定义"
```

---

### Task 7: 测试完整流程

**Step 1: 启动后端服务**

```bash
cd backend
python -m uvicorn app.main:app --reload
```

**Step 2: 启动前端服务**

```bash
cd frontend
npm run dev
```

**Step 3: 测试完整部署（确保现有功能正常）**

- 创建一个完整部署
- 验证克隆、构建、上传流程正常

**Step 4: 测试仅重启部署**

- 创建一个仅重启部署
- 验证只执行重启脚本
- 验证健康检查日志

**Step 5: 提交**

```bash
git add .
git commit -m "test: 验证仅重启部署模式"
```

---

### Task 8: 文档更新

**Files:**
- Modify: `README.md` (如果需要)

**Step 1: 更新部署相关文档**

添加关于仅重启模式的说明：

```markdown
## 部署模式

系统支持两种部署模式：

1. **完整部署 (full)**: 克隆代码 → 构建 → 上传 → 重启
2. **仅重启 (restart_only)**: 直接执行重启脚本，跳过克隆和构建

仅重启模式适用于：
- 配置更新后重启服务
- 快速回滚
- 不需要构建的部署场景
```

**Step 2: 提交**

```bash
git add README.md
git commit -m "docs: 添加仅重启模式说明"
```
