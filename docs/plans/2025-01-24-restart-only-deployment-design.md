# 仅重启部署模式设计

## 概述

新增"仅重启"部署模式，允许用户跳过克隆、构建、上传步骤，直接在服务器上执行重启脚本。

## 部署模式对比

| 模式 | 克隆 | 构建 | 上传 | 重启 | 健康检查 |
|------|------|------|------|------|----------|
| 完整部署 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 仅重启 | ❌ | ❌ | ❌ | ✅ | ✅ |

## 数据模型变更

### 1. 新增 DeploymentType 枚举

```python
class DeploymentType(str, enum.Enum):
    FULL = "full"           # 完整部署（默认）
    RESTART_ONLY = "restart_only"  # 仅重启
```

### 2. Deployment 模型扩展

```python
deployment_type: Mapped[DeploymentType] = mapped_column(
    String(20),
    default=DeploymentType.FULL,
    nullable=False
)
```

### 3. DeploymentStatus 新增状态

```python
RESTARTING = "restarting"  # 仅重启模式专用状态
```

### 4. Schema 变更

```python
class DeploymentCreate(BaseModel):
    # ... 现有字段 ...
    deployment_type: DeploymentType = DeploymentType.FULL
```

## Service 层重构

### deploy() 方法分流

```python
async def deploy(self):
    if self.deployment.deployment_type == DeploymentType.RESTART_ONLY:
        await self._restart_only()
    else:
        await self._full_deploy()
```

### _restart_only() 方法流程

```python
async def _restart_only(self) -> None:
    await self._update_status(DeploymentStatus.RESTARTING)

    for group in self.deployment.server_groups:
        for server in group.servers:
            await self._restart_server(server)

    await self._update_status(DeploymentStatus.SUCCESS)
```

### _restart_server() 方法

1. SSH 连接服务器
2. 执行重启脚本 (`project.deploy_script_path`)
3. 进程健康检查 (`ps aux | grep <process>`)
4. 记录结果

## 错误处理

- 重启脚本执行失败 → 记录警告，继续下一台服务器
- 进程健康检查失败 → 标记部署为 FAILED
- 部分服务器失败 → 在 error_message 中说明

## 前端变更

```typescript
create: (data: {
  project_id: number
  branch?: string  // 仅重启时可选
  server_group_ids: number[]
  deployment_type?: 'full' | 'restart_only'
}) => Promise<Deployment>
```

## 状态流转

**完整部署**：
```
PENDING → CLONING → BUILDING → DEPLOYING → SUCCESS
```

**仅重启**：
```
PENDING → RESTARTING → SUCCESS
         ↓ (失败)
       FAILED
```
