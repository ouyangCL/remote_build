# 仅重启脚本增强功能说明

## 新增功能

1. **独立的仅重启脚本配置**
   - 新增 `restart_only_script_path` 字段
   - 仅重启部署模式使用此字段
   - 与常规部署的重启脚本分离

2. **自动切换脚本目录**
   - 执行脚本前自动切换到脚本所在目录
   - 支持绝对路径和相对路径
   - 内置命令注入防护

3. **脚本工具函数**
   - `parse_script_output()`: 解析脚本执行信息
   - `execute_script()`: 安全的脚本执行函数
   - 支持工作目录切换和命令注入防护

## 使用示例

项目配置：
- 重启脚本路径（常规部署）: `/opt/app/deploy.sh`
- 仅重启脚本路径: `/opt/app/restart-only.sh`

部署行为：
- **常规部署**: 使用 `restart_script_path`
- **仅重启部署**: 使用 `restart_only_script_path`

## 技术实现

### 数据库变更
- 迁移文件: `011_add_restart_only_script_path.py`
- 新增字段: `projects.restart_only_script_path VARCHAR(255)`

### 后端变更
- **Model**: `app/models/project.py` - 添加 `restart_only_script_path` 字段
- **Schema**: `app/schemas/project.py` - 添加 `restart_only_script_path` 字段
- **API**: `app/api/projects.py` - 支持新字段的创建和更新
- **Service**:
  - `app/services/deploy_service.py` - 重构部署逻辑
  - `app/services/git_service.py` - 添加脚本工具函数

### 前端变更
- **ProjectList.vue**: 添加仅重启脚本路径输入框
- **TypeScript 类型定义**: 添加 `restart_only_script_path` 字段

## 安全性

1. **命令注入防护**
   - 使用 `shlex.quote()` 转义所有路径参数
   - 验证脚本路径合法性
   - 白名单机制限制可执行文件

2. **路径验证**
   - 检查文件是否存在
   - 验证文件是否可执行
   - 防止路径遍历攻击

## 测试结果

- [x] 单元测试通过 (script_utils)
- [x] 数据库迁移成功
- [x] 代码风格检查通过
- [x] 功能完整性验证
  - [x] 数据库字段添加
  - [x] Model 和 Schema 更新
  - [x] API 接口支持
  - [x] 部署服务集成
  - [x] 前端界面支持
- [ ] 手动验证（需要启动服务）
  - [ ] 创建项目并配置仅重启脚本
  - [ ] 执行仅重启部署
  - [ ] 验证脚本输出解析

## 提交历史

- `9c88af6` feat: 前端添加仅重启脚本路径输入框
- `57c090d` feat: 前端类型定义添加 restart_only_script_path 字段
- `4df5411` feat: Project Schema 添加 restart_only_script_path 字段
- `7e52d8f` refactor: 更新 _deploy_to_server 使用新脚本执行逻辑
- `079644f` refactor: 更新 _restart_server 使用新脚本执行逻辑
- `0a2b106` security: 修复脚本工具函数的命令注入风险
- `f3c2454` fix: 修复脚本工具函数的代码质量问题
- `2cae04d` feat: 添加脚本执行信息解析工具函数
- `b9446bd` feat: 添加 restart_only_script_path 数据库字段
- `2f47afb` docs: 添加仅重启脚本增强实施计划
- `f6e7c93` docs: 添加仅重启脚本增强设计文档

## 注意事项

1. **测试环境限制**
   - Python 3.7 不支持 `AsyncMock`（需要 Python 3.8+）
   - 部分测试依赖未安装（paramiko）
   - 建议升级到 Python 3.8+ 以运行完整测试套件

2. **手动测试建议**
   - 启动后端服务
   - 创建测试项目
   - 配置不同的重启脚本路径
   - 执行常规部署和仅重启部署
   - 验证日志输出和部署结果

3. **部署前检查**
   - 确保数据库迁移已执行
   - 验证脚本路径存在且可执行
   - 检查脚本文件权限
   - 测试脚本手动执行是否正常

## 后续优化建议

1. **增强错误处理**
   - 添加脚本执行超时控制
   - 优化错误信息提示
   - 支持脚本执行日志持久化

2. **功能扩展**
   - 支持脚本参数配置
   - 添加脚本执行历史记录
   - 支持脚本版本管理

3. **监控和告警**
   - 添加脚本执行成功率统计
   - 实现脚本执行失败告警
   - 提供脚本执行性能指标
