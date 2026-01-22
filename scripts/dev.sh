#!/bin/bash
# 本地开发模式启动脚本

set -e

echo "=== DevOps 平台 - 本地开发模式 ==="

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "错误: 需要安装 Python 3.11+"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "错误: 需要安装 Node.js 20+"; exit 1; }

# 进入项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "项目目录: $PROJECT_ROOT"

# 初始化后端
echo ""
echo ">>> 初始化后端..."
cd "$BACKEND_DIR"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装后端依赖..."
pip install -q -r requirements.txt

# 初始化数据库
if [ ! -f "devops.db" ]; then
    echo "初始化数据库..."
    alembic upgrade head
fi

# 初始化前端
echo ""
echo ">>> 初始化前端..."
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动服务
echo ""
echo "=== 启动服务 ==="

# 在后台启动后端
cd "$BACKEND_DIR"
echo "启动后端服务 (http://localhost:9090)..."
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 9090 --reload &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID"

# 在后台启动前端
cd "$FRONTEND_DIR"
echo "启动前端服务 (http://localhost:5173)..."
npm run dev &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID"

echo ""
echo "=== 服务已启动 ==="
echo "前端: http://localhost:5173"
echo "后端: http://localhost:9090"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号，清理后台进程
trap "echo ''; echo '停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# 等待任意一个进程结束
wait
