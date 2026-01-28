# 上传部署包功能设计

## 概述

新增第三种部署方式「上传部署包」，允许用户直接上传已构建好的部署包：
- **Java项目**：上传 `.jar` 文件
- **前端项目**：上传 `dist` 目录的 `.zip` 压缩包

部署流程：**上传文件 → 传输到服务器 → 解压/部署 → 执行重启脚本**

## 部署类型枚举

```python
class DeploymentType(str, enum.Enum):
    FULL = "full"              # 完整部署（克隆+构建+上传）
    RESTART_ONLY = "restart_only"  # 仅重启
    UPLOAD = "upload"          # 上传部署包（新增）
```

## 数据库变更

复用现有字段，无需数据库迁移：

| 字段 | 上传部署包的值 |
|------|---------------|
| `deployment_type` | `"upload"` |
| `branch` | `"upload"`（自动填充） |
| `commit_hash` | `NULL` |
| `commit_message` | `NULL` |

## 后端API

### 新增路由

`POST /api/deployments/upload`

**请求格式**：`multipart/form-data`
- `project_id`: 项目ID
- `server_group_ids`: 服务器组ID列表
- `file`: 上传的文件

**响应**：
```json
{
  "deployment_id": 123,
  "status": "pending"
}
```

### 文件验证

- Java项目：必须是 `.jar` 文件
- 前端项目：必须是 `.zip` 文件
- 无文件大小限制

### 临时文件存储

路径：`/tmp/deployments/{deployment_id}/{filename}`

部署完成后自动清理。

## 部署流程

### 步骤

1. **UPLOADING**：获取已上传文件路径
2. **DEPLOYING**：传输到服务器并部署
3. **HEALTH_CHECKING**：健康检查（如果启用）
4. **清理临时文件**
5. **SUCCESS**

### 服务器部署策略

- **Java项目**：上传 `.jar` 到 `upload_path`，不需要解压
- **前端项目**：上传 `.zip` 到父目录，解压到 `upload_path`（带备份机制）

## 前端UI

### 部署模式选项

```vue
<el-radio label="upload">
  <div class="radio-option">
    <span class="radio-label">上传部署包</span>
    <span class="radio-desc">直接上传构建好的部署包</span>
  </div>
</el-radio>
```

### 文件上传组件

- 支持拖拽上传
- 限制单个文件
- 根据项目类型显示不同提示

### 分支字段

上传模式下隐藏分支输入框（自动填充为 "upload"）

## 错误处理

| 场景 | 处理 |
|------|------|
| 文件格式错误 | 400错误，提示正确格式 |
| 上传失败 | 500错误，记录日志 |
| 解压失败 | 前端项目触发备份回滚 |
| 部署失败 | 清理临时文件 |

## 实施清单

| 序号 | 文件 | 修改内容 |
|------|------|---------|
| 1 | `backend/app/models/deployment.py` | 新增 `DeploymentType.UPLOAD` |
| 2 | `backend/app/schemas/deployment.py` | 新增上传请求Schema |
| 3 | `backend/app/api/deployments.py` | 新增 `/upload` 路由 |
| 4 | `backend/app/services/deploy_service.py` | 新增 `_upload_deploy()` 方法 |
| 5 | `frontend/src/views/DeploymentConsole.vue` | 新增上传模式UI |
| 6 | `frontend/src/api/deployments.ts` | 新增上传API调用 |
