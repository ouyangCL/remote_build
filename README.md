# DevOps Deployment Platform

> 一个功能完整的 DevOps 自动化部署平台，支持 Git 项目自动化构建、打包和一键部署到服务器集群。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org)

---

## 功能特性

### 核心功能

- **多用户系统**：基于角色的访问控制（管理员、操作员、查看者）
- **项目管理**：支持配置 Git 仓库、构建脚本和部署参数
- **服务器管理**：SSH 连接管理，支持服务器分组
- **一键部署**：自动化构建和部署流水线
- **部署模式**：
  - **完整部署**：克隆代码 → 构建 → 上传 → 重启
  - **仅重启**：跳过克隆和构建，直接执行重启脚本（适用于配置更新、快速回滚等场景）
- **实时日志**：基于 SSE 的流式日志，实时查看部署过程
- **版本回滚**：快速回滚到之前的部署版本
- **私有仓库支持**：通过 Git Token 认证访问私有 Git 仓库
- **多种项目类型**：支持前端、后端、Java/Maven 等多种项目类型

### 安全特性

- AES-256 加密存储 SSH 凭据
- JWT Token 认证机制
- 基于角色的权限控制（RBAC）
- 完整的操作审计日志
- 生产环境密钥强度验证

---

## 技术栈

### 后端
- **框架**：[FastAPI](https://fastapi.tiangolo.com/) - 现代高性能 Python Web 框架
- **数据库**：SQLite (开发) / PostgreSQL (生产)
- **ORM**：[SQLAlchemy 2.0](https://www.sqlalchemy.org/)
- **认证**：JWT (python-jose) + Passlib
- **SSH**：[Paramiko](https://www.paramiko.org/)
- **Git**：[GitPython](https://gitpython.readthedocs.io/)
- **日志**：[Loguru](https://github.com/Delgan/loguru)

### 前端
- **框架**：[Vue 3](https://vuejs.org/) (Composition API)
- **UI 库**：[Element Plus](https://element-plus.org/)
- **状态管理**：[Pinia](https://pinia.vuejs.org/)
- **路由**：[Vue Router 4](https://router.vuejs.org/)
- **构建工具**：[Vite](https://vitejs.dev/)
- **类型系统**：TypeScript

### 部署
- **开发环境**：Uvicorn + Vite Dev Server
- **生产环境**：Systemd + Nginx

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- Git

### 本地开发

#### 方式一：一键启动（推荐）

```bash
./scripts/dev.sh
```

#### 方式二：手动启动

**后端服务：**

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 9090 --reload
```

**前端服务（新终端）：**

```bash
cd frontend
npm install
npm run dev
```

### 访问地址

- **前端界面**：http://localhost:5173
- **后端 API**：http://localhost:9090
- **API 文档**：http://localhost:9090/docs
- **默认账号**：`admin` / `admin123`

---

## 生产部署

使用 Systemd + Nginx 部署：

```bash
# 1. 运行部署脚本（需要 root 权限）
sudo ./scripts/deploy.sh

# 2. 编辑生产环境配置
sudo nano /opt/devops/backend/.env.production

# 3. 重新部署
sudo ./scripts/deploy.sh
```

**服务管理：**

```bash
# 启动/停止/重启服务
sudo systemctl start devops-backend
sudo systemctl stop devops-backend
sudo systemctl restart devops-backend

# 查看服务状态
sudo systemctl status devops-backend

# 查看日志
sudo journalctl -u devops-backend -f
```

---

## 配置说明

### 后端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `sqlite:///./data/devops.db` |
| `SECRET_KEY` | JWT 签名密钥 | - |
| `ENCRYPTION_KEY` | SSH 凭据加密密钥 | - |
| `CORS_ORIGINS` | 允许的 CORS 源 | `http://localhost:5173` |
| `WORK_DIR` | 构建工作目录 | `./work` |
| `ARTIFACTS_DIR` | 部署包存档目录 | `./artifacts` |
| `LOGS_DIR` | 日志目录 | `./logs` |

### 项目配置说明

每个项目需要配置以下关键参数：

- **upload_path**: 部署包上传到服务器的目标路径（例如：`/opt/myapp`）
- **restart_script_path**: 部署后执行的重启脚本路径（支持内联命令）
- **build_script**: 项目构建脚本
- **output_dir**: 构建产物输出目录（相对于项目根目录）

### 生产环境目录结构

```
/opt/devops/
├── backend/
│   ├── venv/           # Python 虚拟环境
│   ├── data/           # SQLite 数据库
│   ├── work/           # 构建工作区
│   ├── artifacts/      # 部署包存档
│   └── logs/           # 日志文件
└── frontend/
    └── dist/           # 前端构建产物
```

---

## 使用指南

### 1. 创建项目

1. 导航到「项目管理」页面
2. 点击「新建项目」
3. 配置 Git 仓库地址（支持私有仓库 Token 认证）
4. 设置构建脚本和部署脚本
5. 选择项目类型（前端/后端/Java）

### 2. 添加服务器

1. 导航到「服务器管理」页面
2. 添加服务器 SSH 连接信息
3. 测试连接确保配置正确

### 3. 创建服务器组

1. 导航到「服务器组」页面
2. 创建分组并添加服务器
3. 可用于批量部署

### 4. 执行部署

1. 导航到「部署」页面
2. 选择项目、分支和服务器组
3. 点击「开始部署」
4. 实时监控部署日志
5. 部署完成后可进行回滚操作

---

## 部署流程

### 完整部署模式

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  选择项目    │ --> │  克隆代码    │ --> │  执行构建    │
│  分支/环境   │     │  Git仓库     │     │  自定义脚本  │
└─────────────┘     └─────────────┘     └─────────────┘
                                                │
                                                v
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  存储版本    │ <-- │  执行重启    │ <-- │  打包上传    │
│  支持回滚    │     │  SSH远程命令  │     │  ZIP传输    │
└─────────────┘     └─────────────┘     └─────────────┘
                                            │
                                            v
                                    ┌─────────────┐
                                    │  上传到统一  │
                                    │ upload_path │
                                    └─────────────┘
```

**部署说明**：
- 部署包会上传到所有目标服务器的统一路径（`project.upload_path`）
- 支持内联命令或脚本文件作为重启脚本
- 健康检查会在统一路径下执行命令

### 仅重启模式

```
┌─────────────┐     ┌─────────────┐
│  选择项目    │ --> │  执行重启    │
│  服务器组    │     │  SSH远程命令  │
└─────────────┘     └─────────────┘
                            │
                            v
                   ┌─────────────┐
                   │  健康检查    │
                   │  验证进程状态  │
                   └─────────────┘
```

**使用场景：**
- 配置文件更新后需要重启服务
- 快速回滚到之前的部署版本
- 不需要重新构建的热修复场景

---

## 项目结构

```
devops/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 安全、SSH 核心
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 业务逻辑
│   │   ├── db/             # 数据库会话
│   │   ├── config.py       # 配置管理
│   │   └── main.py         # 应用入口
│   ├── alembic/            # 数据库迁移
│   └── requirements.txt
│
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── api/            # API 客户端
│   │   ├── views/          # 页面组件
│   │   ├── stores/         # Pinia 状态
│   │   ├── router/         # Vue Router
│   │   └── types/          # TypeScript 类型
│   └── package.json
│
├── scripts/                 # 部署脚本
│   ├── dev.sh              # 本地开发启动
│   └── deploy.sh           # 生产环境部署
│
├── deploy/                  # 生产环境配置
│   ├── devops-backend.service   # systemd 配置
│   └── devops-nginx.conf        # nginx 配置
```

---

## 安全说明

- **SSH 凭据加密**：使用 AES-256 加密算法存储所有服务器密码和私钥
- **JWT 认证**：所有 API 请求需要有效的 JWT Token
- **权限控制**：
  - **管理员**：完全访问权限
  - **操作员**：部署和查看权限
  - **查看者**：仅查看权限
- **审计日志**：所有关键操作都会记录审计日志
- **安全头**：生产环境配置了完整的安全 HTTP 头

---

## 数据库设计

| 表名 | 说明 |
|------|------|
| `users` | 用户表（支持三种角色） |
| `projects` | 项目配置表（包含 upload_path、restart_script_path 等配置） |
| `servers` | 服务器信息表（SSH 连接信息） |
| `server_groups` | 服务器组表（支持批量部署） |
| `deployments` | 部署记录表（包含部署状态、产物信息） |
| `deployment_artifacts` | 部署产物表（存储部署包路径和校验和） |
| `audit_logs` | 审计日志表 |
| `environments` | 环境配置表 |

**重要变更**：
- `projects` 表新增 `upload_path` 字段，用于统一管理部署目标路径
- `servers` 表不再包含 `deploy_path`，改为项目级别的统一配置

---

## 更新日志

### v1.2.0 (最新)

- **架构优化**：将部署路径从服务器级别（`server.deploy_path`）改为项目级别（`project.upload_path`）
- 支持一个部署包在多台服务器上使用统一路径部署
- 部署产物格式从 tar.gz 改为 ZIP
- 重启脚本支持内联命令（包含 shell 操作符的命令）
- 完善健康检查和回滚服务的路径处理逻辑
- 更新文档以反映新的部署流程

### v1.1.0

- 添加 Java/Maven 项目类型支持
- 添加 Git Token 认证支持私有仓库
- 数据库从 PostgreSQL 迁移到 SQLite（开发环境）
- 完善部署脚本和文档

### v1.2.0

- 新增**仅重启部署模式**，跳过克隆和构建步骤
- 部署产物格式从 tar.gz 改为 zip
- 添加部署健康检查机制
- 重构部署流程，部署路径从服务器级别改为项目级别
- 重写 README 为中文并完善项目文档

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 许可证

本项目采用 [MIT](LICENSE) 许可证。

---

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
