# 上传部署包功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增「上传部署包」部署方式，允许用户直接上传已构建好的 jar 包或 zip 压缩包进行部署

**Architecture:**
- 后端新增 `UPLOAD` 部署类型和文件上传 API
- 部署服务复用现有传输和重启逻辑
- 前端新增文件上传组件和模式切换

**Tech Stack:** FastAPI, SQLAlchemy, Vue3, Element Plus

---

## Task 1: 后端 - 新增 UPLOAD 部署类型枚举

**Files:**
- Modify: `backend/app/models/deployment.py`

**Step 1: 添加 UPLOAD 枚举值**

在 `DeploymentType` 枚举中添加 `UPLOAD` 值：

```python
class DeploymentType(str, enum.Enum):
    """部署类型枚举"""

    FULL = "full"  # 完整部署（包含克隆、构建、上传）
    RESTART_ONLY = "restart_only"  # 仅重启（不构建）
    UPLOAD = "upload"  # 上传部署包（新增）
```

**Step 2: 运行测试验证**

Run: `cd backend && python -c "from app.models.deployment import DeploymentType; print(DeploymentType.UPLOAD.value)"`
Expected: 输出 `upload`

**Step 3: 提交**

```bash
git add backend/app/models/deployment.py
git commit -m "feat: add UPLOAD deployment type enum"
```

---

## Task 2: 后端 - 新增上传部署请求 Schema

**Files:**
- Modify: `backend/app/schemas/deployment.py`

**Step 1: 查看现有 Schema 结构**

检查 `DeploymentCreate` 和相关 Schema 的定义

**Step 2: 添加上传部署请求 Schema**

```python
class DeploymentUploadCreate(BaseModel):
    """上传部署包创建请求"""

    project_id: int = Field(..., description="项目ID")
    server_group_ids: list[int] = Field(..., min_items=1, description="服务器组ID列表")
```

**Step 3: 验证**

Run: `cd backend && python -c "from app.schemas.deployment import DeploymentUploadCreate; print(DeploymentUploadCreate.__doc__)"`
Expected: 输出 Schema 文档字符串

**Step 4: 提交**

```bash
git add backend/app/schemas/deployment.py
git commit -m "feat: add DeploymentUploadCreate schema"
```

---

## Task 3: 后端 - 新增文件上传 API

**Files:**
- Modify: `backend/app/api/deployments.py`
- Test: `backend/tests/test_upload_deployment.py`

**Step 1: 导入必要模块**

在 `deployments.py` 顶部添加：

```python
from fastapi import UploadFile, File, Form
import tempfile
import os
from pathlib import Path
```

**Step 2: 添加文件验证函数**

```python
def validate_upload_file(project_type: str, filename: str) -> None:
    """验证上传文件类型"""
    if project_type == ProjectType.JAVA:
        if not filename.endswith('.jar'):
            raise HTTPException(
                status_code=400,
                detail="Java项目请上传.jar文件"
            )
    elif project_type == ProjectType.FRONTEND:
        if not filename.endswith('.zip'):
            raise HTTPException(
                status_code=400,
                detail="前端项目请上传.zip压缩包"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的项目类型: {project_type}"
        )
```

**Step 3: 添加上传部署 API**

```python
@router.post("/upload", response_model=DeploymentResponse)
async def create_upload_deployment(
    project_id: int = Form(...),
    server_group_ids: str = Form(...),  # 逗号分隔的字符串
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建上传部署包类型的部署任务"""
    # 解析服务器组ID列表
    group_ids = [int gid.strip()) for gid in server_group_ids.split(',')]

    # 验证项目存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 验证文件类型
    validate_upload_file(project.project_type, file.filename)

    # 创建临时目录保存上传文件
    temp_dir = Path(tempfile.gettempdir()) / "deployments"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 读取文件内容
    content = await file.read()

    # 创建部署记录
    deployment = Deployment(
        project_id=project_id,
        branch="upload",
        deployment_type=DeploymentType.UPLOAD,
        status=DeploymentStatus.PENDING,
        created_by=current_user.id,
        environment=project.environment,
        total_steps=3,  # 上传->部署->健康检查
    )
    db.add(deployment)
    db.commit()

    # 保存上传文件
    temp_file_path = temp_dir / f"{deployment.id}_{file.filename}"
    temp_file_path.write_bytes(content)

    # 创建 artifact 记录
    import hashlib
    checksum = hashlib.sha256(content).hexdigest()
    artifact = DeploymentArtifact(
        deployment_id=deployment.id,
        file_path=str(temp_file_path),
        file_size=len(content),
        checksum=checksum,
    )
    db.add(artifact)

    # 关联服务器组
    for group_id in group_ids:
        mapping = deployment_server_mappings.insert().values(
            deployment_id=deployment.id,
            server_group_id=group_id
        )
        db.execute(mapping)

    db.commit()

    # 触发后台部署任务
    await queue_deployment(deployment.id)

    return deployment
```

**Step 4: 提交**

```bash
git add backend/app/api/deployments.py
git commit -m "feat: add upload deployment API endpoint"
```

---

## Task 4: 后端 - 实现上传部署流程

**Files:**
- Modify: `backend/app/services/deploy_service.py`

**Step 1: 在 deploy() 方法中添加 UPLOAD 类型处理**

在 `DeploymentService.deploy()` 方法中的 if-else 里添加：

```python
async def deploy(self) -> None:
    """Execute deployment process."""
    try:
        project = self.deployment.project

        if self.deployment.deployment_type == DeploymentType.RESTART_ONLY:
            await self._restart_only_deploy()
        elif self.deployment.deployment_type == DeploymentType.UPLOAD:
            await self._upload_deploy()
        else:
            await self._full_deploy()

    except Exception as e:
        await self._update_status(DeploymentStatus.FAILED, str(e))
        await self.logger.error(f"Deployment failed: {e}")
        raise DeploymentError(f"Deployment failed: {e}") from e
```

**Step 2: 实现 _upload_deploy() 方法**

```python
async def _upload_deploy(self) -> None:
    """执行上传部署包流程.

    流程：
    1. 获取已上传文件路径
    2. 部署到服务器
    3. 健康检查（如果启用）
    4. 清理临时文件
    """
    project = self.deployment.project
    await self.logger.info(f"开始上传部署包: {project.name}")

    # 步骤1: 获取已上传的文件
    await self._update_status(DeploymentStatus.UPLOADING)
    artifact_path = await self._get_uploaded_file()

    if self._cancelled:
        await self._handle_cancel()
        return

    # 步骤2: 部署到服务器
    await self._update_status(DeploymentStatus.DEPLOYING)
    await self._deploy_to_servers(artifact_path)

    if self._cancelled:
        await self._handle_cancel()
        return

    # 步骤3: 健康检查
    if project.health_check_enabled:
        await self._update_status(DeploymentStatus.HEALTH_CHECKING)
        await self._perform_health_checks()

        if self._cancelled:
            await self._handle_cancel()
            return

    # 步骤4: 清理临时文件
    await self._cleanup_temp_files()

    # 步骤5: 成功
    await self._update_status(DeploymentStatus.SUCCESS)
    await self.logger.info("上传部署完成")
```

**Step 3: 实现 _get_uploaded_file() 方法**

```python
async def _get_uploaded_file(self) -> Path:
    """获取已上传文件的路径.

    Returns:
        上传文件的路径

    Raises:
        DeploymentError: 如果文件不存在
    """
    artifact = self.deployment.artifacts[0] if self.deployment.artifacts else None
    if not artifact:
        raise DeploymentError("未找到上传的部署包文件")

    file_path = Path(artifact.file_path)
    if not file_path.exists():
        raise DeploymentError(f"上传文件不存在: {artifact.file_path}")

    await self.logger.info(f"获取上传文件: {file_path.name} ({artifact.file_size} bytes)")
    return file_path
```

**Step 4: 实现 _cleanup_temp_files() 方法**

```python
async def _cleanup_temp_files(self) -> None:
    """清理上传的临时文件."""
    artifact = self.deployment.artifacts[0] if self.deployment.artifacts else None
    if artifact:
        file_path = Path(artifact.file_path)
        if file_path.exists():
            file_path.unlink()
            await self.logger.info(f"已清理临时文件: {file_path}")
```

**Step 5: 在 _handle_cancel() 中添加临时文件清理**

确保取消时也清理临时文件：

```python
async def _handle_cancel(self) -> None:
    """Handle deployment cancellation."""
    await self._cleanup_temp_files()  # 添加这行
    await self._update_status(DeploymentStatus.CANCELLED)
    await self.logger.warning("Deployment was cancelled")
```

**Step 6: 提交**

```bash
git add backend/app/services/deploy_service.py
git commit -m "feat: implement upload deployment flow in service"
```

---

## Task 5: 后端 - Java 项目部署适配

**Files:**
- Modify: `backend/app/services/deploy_service.py`

**Step 1: 修改 _deploy_backend_to_server() 方法**

适配上传模式，Java 项目上传 jar 不需要解压：

```python
async def _deploy_backend_to_server(
    self,
    conn: SSHConnection,
    server: Server,
    upload_path: str,
    artifact_path: Path,
) -> None:
    """Deploy backend/java project to server.

    对于 jar 文件直接上传，不需要解压。
    对于 zip 文件解压到 upload_path 目录。

    Args:
        conn: SSH connection
        server: Target server
        upload_path: Remote upload path
        artifact_path: Local artifact path
    """
    remote_artifact = f"{upload_path}/{artifact_path.name}"

    await self.logger.info(f"上传部署产物到: {remote_artifact}")

    # Ensure upload directory exists
    mkdir_command = f"mkdir -p {upload_path}"
    exit_code, stdout, stderr = conn.execute_command(mkdir_command)
    if exit_code != 0:
        await self.logger.error(f"创建上传目录失败: {stderr}")
        raise DeploymentError(f"Failed to create upload directory: {stderr}")

    # Upload artifact
    conn.upload_file(artifact_path, remote_artifact)
    await self.logger.info(f"部署产物上传完成: {remote_artifact}")

    # 判断文件类型，jar 不需要解压
    if artifact_path.name.endswith('.jar'):
        await self.logger.info("Java jar 包部署完成，无需解压")
    else:
        # 解压zip包到upload_path目录
        await self.logger.info(f"解压部署产物到: {upload_path}")
        unzip_command = f"unzip -o {remote_artifact} -d {upload_path}"
        exit_code, stdout, stderr = conn.execute_command(unzip_command)
        if exit_code != 0:
            await self.logger.error(f"解压失败: {stderr}")
            raise DeploymentError(f"Failed to unzip artifact: {stderr}")
        await self.logger.info("解压完成")
```

**Step 2: 提交**

```bash
git add backend/app/services/deploy_service.py
git commit -m "feat: adapt backend deployment for jar files without unzip"
```

---

## Task 6: 前端 - 更新类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: 添加 upload 部署类型**

在 Deployment 接口中更新 deployment_type：

```typescript
export interface Deployment {
  // ... 其他字段
  deployment_type?: 'full' | 'restart_only' | 'upload'  // 添加 'upload'
  // ...
}
```

**Step 2: 验证 TypeScript 编译**

Run: `cd frontend && npm run type-check`
Expected: 无类型错误

**Step 3: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add upload deployment type to frontend types"
```

---

## Task 7: 前端 - 添加上传部署 API

**Files:**
- Modify: `frontend/src/api/deployments.ts`

**Step 1: 添加上传部署 API 函数**

```typescript
// 上传部署包创建部署
export function createUploadDeployment(
  projectId: number,
  serverGroupIds: number[],
  file: File,
  onProgress?: (progress: number) => void
): Promise<Deployment> {
  const formData = new FormData()
  formData.append('project_id', projectId.toString())
  formData.append('server_group_ids', serverGroupIds.join(','))
  formData.append('file', file)

  return request.post<Deployment>('/deployments/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(progress)
      }
    }
  })
}
```

**Step 2: 提交**

```bash
git add frontend/src/api/deployments.ts
git commit -m "feat: add upload deployment API function"
```

---

## Task 8: 前端 - 部署控制台添加上传模式 UI

**Files:**
- Modify: `frontend/src/views/DeploymentConsole.vue`

**Step 1: 添加上传模式单选框**

在部署模式的 el-radio-group 中添加：

```vue
<el-radio label="upload">
  <div class="radio-option">
    <span class="radio-label">上传部署包</span>
    <span class="radio-desc">直接上传构建好的部署包</span>
  </div>
</el-radio>
```

**Step 2: 添加文件上传组件**

在分支输入框后添加：

```vue
<!-- 上传部署包时显示 -->
<el-form-item v-if="form.deployment_type === 'upload'" label="部署包" required>
  <el-upload
    ref="uploadRef"
    :auto-upload="false"
    :limit="1"
    :on-change="handleFileChange"
    :on-remove="handleFileRemove"
    drag
    class="deploy-upload"
  >
    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
    <div class="el-upload__text">
      将文件拖到此处，或<em>点击上传</em>
    </div>
    <template #tip>
      <div class="el-upload__tip">
        {{ uploadHint }}
      </div>
    </template>
  </el-upload>
</el-form-item>
```

**Step 3: 添加上传进度显示**

在按钮区域上方添加：

```vue
<!-- 上传进度 -->
<div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
  <el-progress :percentage="uploadProgress" />
</div>
```

**Step 4: 添加计算属性和方法**

在 script 部分添加：

```typescript
// 文件上传相关
const uploadRef = ref<InstanceType<typeof ElUpload>>()
const uploadedFile = ref<File | null>(null)
const uploadProgress = ref(0)

// 上传提示文本
const uploadHint = computed(() => {
  if (!selectedProject.value) return '请先选择项目'
  if (selectedProject.value.project_type === 'java') {
    return '请上传 .jar 文件'
  }
  return '请上传 dist 目录的 .zip 压缩包'
})

// 文件选择处理
function handleFileChange(file: UploadFile) {
  if (file.raw) {
    uploadedFile.value = file.raw
  }
}

// 文件移除处理
function handleFileRemove() {
  uploadedFile.value = null
}
```

**Step 5: 修改部署按钮逻辑**

修改 createDeployment 函数以处理上传模式：

```typescript
async function createDeployment() {
  // 验证
  if (!form.project_id) {
    ElMessage.error('请选择项目')
    return
  }
  if (!form.server_group_ids || form.server_group_ids.length === 0) {
    ElMessage.error('请选择服务器组')
    return
  }

  // 上传模式需要验证文件
  if (form.deployment_type === 'upload') {
    if (!uploadedFile.value) {
      ElMessage.error('请上传部署包')
      return
    }
  } else {
    // 其他模式需要验证分支
    if (!form.branch) {
      ElMessage.error('请输入分支名称')
      return
    }
  }

  deploying.value = true

  try {
    let deployment: Deployment

    if (form.deployment_type === 'upload') {
      // 上传部署包
      deployment = await createUploadDeployment(
        form.project_id,
        form.server_group_ids,
        uploadedFile.value!,
        (progress) => {
          uploadProgress.value = progress
        }
      )
    } else {
      // 原有部署方式
      deployment = await createDeployment({
        project_id: form.project_id,
        branch: form.branch!,
        server_group_ids: form.server_group_ids,
        deployment_type: form.deployment_type as 'full' | 'restart_only',
      })
    }

    ElMessage.success('部署任务已创建')
    resetForm()
    emit('deployment-created')
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '创建部署失败'
    ElMessage.error(message)
  } finally {
    deploying.value = false
    uploadProgress.value = 0
  }
}
```

**Step 6: 修改分支字段显示条件**

让分支字段在上传模式时隐藏：

```vue
<el-form-item
  v-if="form.deployment_type !== 'upload' && form.deployment_type !== 'restart_only'"
  label="分支"
>
  <!-- ... -->
</el-form-item>
```

**Step 7: 添加样式**

在 style 部分添加：

```scss
.deploy-upload {
  width: 100%;

  :deep(.el-upload-dragger) {
    width: 100%;
    padding: 20px;
  }
}

.upload-progress {
  margin-bottom: 15px;
}
```

**Step 8: 导入必要的图标**

确保导入了 `UploadFilled` 图标：

```typescript
import { UploadFilled, Warning, InfoFilled } from '@element-plus/icons-vue'
```

**Step 9: 提交**

```bash
git add frontend/src/views/DeploymentConsole.vue
git commit -m "feat: add upload deployment UI to deployment console"
```

---

## Task 9: 前端 - 部署历史显示上传类型

**Files:**
- Modify: `frontend/src/views/DeploymentHistory.vue`

**Step 1: 更新部署类型显示**

添加上传类型的标签显示：

```typescript
function getDeploymentTypeLabel(type: string) {
  const labels: Record<string, string> = {
    full: '完整部署',
    restart_only: '仅重启',
    upload: '上传部署包'  // 新增
  }
  return labels[type] || type
}
```

**Step 2: 提交**

```bash
git add frontend/src/views/DeploymentHistory.vue
git commit -m "feat: display upload deployment type in history"
```

---

## Task 10: 测试验证

**Files:**
- Test: Manual testing

**Step 1: 启动后端服务**

```bash
cd ../devops-upload-deployment/backend
python -m uvicorn app.main:app --reload
```

**Step 2: 启动前端服务**

```bash
cd ../devops-upload-deployment/frontend
npm run dev
```

**Step 3: 测试 Java 项目上传部署**

1. 创建 Java 测试项目
2. 准备一个测试 jar 文件
3. 选择「上传部署包」模式
4. 上传 jar 文件
5. 验证部署成功

**Step 4: 测试前端项目上传部署**

1. 创建前端测试项目
2. 准备一个 dist.zip 文件
3. 选择「上传部署包」模式
4. 上传 zip 文件
5. 验证部署成功和备份机制

**Step 5: 测试错误场景**

- 上传错误文件类型（应该被拒绝）
- 上传后取消部署（应该清理临时文件）
- 解压失败场景（前端项目应该回滚备份）

**Step 6: 提交测试结果文档**

```bash
# 如有需要，记录测试结果
```

---

## 最终检查清单

- [ ] 后端 `DeploymentType.UPLOAD` 枚举已添加
- [ ] 后端上传 API 已实现
- [ ] 后端部署服务已支持上传模式
- [ ] Java jar 文件直接部署不解压
- [ ] 前端类型定义已更新
- [ ] 前端上传 API 已添加
- [ ] 部署控制台 UI 已更新
- [ ] 部署历史显示正确
- [ ] 所有测试通过
- [ ] 代码已提交到 feature/upload-deployment 分支

---

**完成条件:** 所有任务完成，代码已提交，测试通过，准备合并到 main 分支。
