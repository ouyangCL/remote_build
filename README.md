# DevOps Deployment Platform

An automated deployment platform supporting Git-based projects, build management, and one-click deployments to server groups.

## Features

- **Multi-user Support**: Role-based access control (Admin, Operator, Viewer)
- **Project Management**: Configure Git repositories, build scripts, and deployment settings
- **Server Management**: SSH connection management with server groups
- **One-Click Deployment**: Automated build and deploy pipeline
- **Real-time Logs**: SSE-based streaming logs
- **Version Rollback**: Quick rollback to previous deployments
- **Secure**: Encrypted credentials, JWT authentication

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: Vue 3 + Element Plus + TypeScript
- **Deployment**: Systemd + Nginx (Production) / Native (Development)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Git

### Local Development

一键启动开发模式：

```bash
./scripts/dev.sh
```

或手动启动：

```bash
# 后端
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 9090 --reload

# 前端（新终端）
cd frontend
npm install
npm run dev
```

访问地址：
- Frontend: http://localhost:5173
- Backend API: http://localhost:9090
- Default credentials: `admin` / `admin123`

### Production Deployment

生产环境使用 systemd + nginx 部署：

```bash
# 1. 运行部署脚本（需要 root 权限）
sudo ./scripts/deploy.sh

# 2. 编辑生产环境配置
sudo nano /opt/devops/backend/.env.production

# 3. 重新部署
sudo ./scripts/deploy.sh
```

服务管理命令：

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

## Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `sqlite:///./data/devops.db` |
| `SECRET_KEY` | JWT signing key | - |
| `ENCRYPTION_KEY` | SSH credentials encryption key | - |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173` |
| `WORK_DIR` | Working directory for builds | `./work` |
| `ARTIFACTS_DIR` | Deployment artifacts directory | `./artifacts` |
| `LOGS_DIR` | Logs directory | `./logs` |

### Production Setup

生产环境部署目录：

```
/opt/devops/
├── backend/         # 后端代码
│   ├── venv/        # Python 虚拟环境
│   ├── data/        # SQLite 数据库
│   ├── work/        # 构建工作区
│   ├── artifacts/   # 部署包存档
│   └── logs/        # 日志
└── frontend/
    └── dist/        # 前端构建产物
```

### Project Setup

1. **Create a Project**:
   - Navigate to Projects page
   - Click "New Project"
   - Configure Git URL, build script, and deployment settings

2. **Add Servers**:
   - Navigate to Servers page
   - Add servers with SSH credentials
   - Test connection before saving

3. **Create Server Groups**:
   - Navigate to Server Groups page
   - Create groups and add servers

4. **Deploy**:
   - Navigate to Deploy page
   - Select project, branch, and server groups
   - Click "Start Deployment"
   - Monitor real-time logs

## Project Structure

```
devops/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Security, SSH
│   │   ├── models/         # Database models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── db/             # Database session
│   │   ├── config.py       # Configuration
│   │   └── main.py         # Application entry
│   ├── alembic/            # Database migrations
│   └── requirements.txt
│
├── frontend/                # Vue 3 frontend
│   ├── src/
│   │   ├── api/            # API clients
│   │   ├── views/          # Page components
│   │   ├── stores/         # Pinia state
│   │   ├── router/         # Vue Router
│   │   └── types/          # TypeScript types
│   └── package.json
│
├── scripts/                 # 部署脚本
│   ├── dev.sh              # 本地开发启动
│   └── deploy.sh           # 生产环境部署
│
└── deploy/                  # 生产环境配置
    ├── devops-backend.service   # systemd 配置
    └── devops-nginx.conf        # nginx 配置
```

## Deployment Flow

1. User selects project, branch, and server groups
2. Backend clones the Git repository
3. Executes custom build script
4. Packages build output as tar.gz
5. Uploads to all servers in the group via SSH
6. Executes pre-configured restart script
7. Stores artifact for rollback

## Security

- SSH passwords/keys encrypted with AES-256
- JWT token authentication
- Role-based access control
- Audit logging for all operations
- Secure HTTP headers

## License

MIT
