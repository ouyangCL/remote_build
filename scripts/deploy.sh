#!/bin/bash
# 生产环境部署脚本

set -e

INSTALL_DIR="/opt/devops"
SERVICE_NAME="devops-backend"
NGINX_CONF="devops-nginx.conf"
SYSTEMD_SERVICE="devops-backend.service"

echo "=== DevOps 平台 - 生产环境部署 ==="

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用 root 权限运行此脚本"
    exit 1
fi

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "错误: 需要安装 Python 3.11+"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "错误: 需要安装 Node.js 20+"; exit 1; }

# 获取项目目录（假设脚本在项目目录下运行）
PROJECT_ROOT=$(pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

echo "项目目录: $PROJECT_ROOT"

# 1. 创建用户和目录
echo ""
echo ">>> 创建用户和目录..."
if ! id -u devops >/dev/null 2>&1; then
    useradd -r -s /bin/bash -d $INSTALL_DIR devops
fi
mkdir -p $INSTALL_DIR/{backend,frontend,data,work,artifacts,logs}
chown -R devops:devops $INSTALL_DIR

# 2. 部署后端
echo ""
echo ">>> 部署后端..."
cp -r $BACKEND_DIR/* $INSTALL_DIR/backend/
cd $INSTALL_DIR/backend

# 创建虚拟环境
if [ ! -d "venv" ]; then
    sudo -u devops python3 -m venv venv
fi

# 安装依赖
sudo -u devops venv/bin/pip install -q -r requirements.txt

# 配置生产环境
if [ ! -f ".env.production" ]; then
    echo "请配置生产环境变量 (.env.production):"
    cat > .env.production << EOF
# Application
APP_NAME=DevOps Deployment Platform
DEBUG=false
ENVIRONMENT=production

# Server
HOST=0.0.0.0
PORT=9090

# Database
DATABASE_URL=sqlite:///./data/devops.db

# JWT - 请修改为强密钥!
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Encryption - 请修改为强密钥!
ENCRYPTION_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

# File Storage
WORK_DIR=./work
ARTIFACTS_DIR=./artifacts
LOGS_DIR=./logs

# CORS - 请修改为实际域名
CORS_ORIGINS=http://your-domain.com
EOF
    echo ""
    echo "已生成 .env.production，请编辑后重新运行!"
    exit 1
fi

# 初始化数据库
sudo -u devops venv/bin/alembic upgrade head

# 3. 部署前端
echo ""
echo ">>> 部署前端..."
cp -r $FRONTEND_DIR/* $INSTALL_DIR/frontend/
cd $INSTALL_DIR/frontend
sudo -u devops npm install
sudo -u devops npm run build

# 4. 配置 systemd
echo ""
echo ">>> 配置 systemd..."
cp $DEPLOY_DIR/$SYSTEMD_SERVICE /etc/systemd/system/
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# 5. 配置 nginx
echo ""
echo ">>> 配置 nginx..."
if [ -f "/etc/nginx/sites-available/default" ]; then
    NGINX_SITES="/etc/nginx/sites-available"
    NGINX_ENABLED="/etc/nginx/sites-enabled"
else
    NGINX_SITES="/etc/nginx/conf.d"
    NGINX_ENABLED="/etc/nginx/conf.d"
fi

cp $DEPLOY_DIR/$NGINX_CONF $NGINX_SITES/
ln -sf $NGINX_SITES/$NGINX_CONF $NGINX_ENABLED/$NGINX_CONF
nginx -t

# 6. 启动服务
echo ""
echo "=== 启动服务 ==="
systemctl restart $SERVICE_NAME
systemctl restart nginx

echo ""
echo "=== 部署完成 ==="
echo ""
echo "服务管理命令:"
echo "  启动: systemctl start $SERVICE_NAME"
echo "  停止: systemctl stop $SERVICE_NAME"
echo "  重启: systemctl restart $SERVICE_NAME"
echo "  状态: systemctl status $SERVICE_NAME"
echo "  日志: journalctl -u $SERVICE_NAME -f"
echo ""
echo "访问地址: http://$(hostname -I | awk '{print $1}')"
echo "默认账号: admin / admin123"
echo ""
echo "请及时修改 .env.production 中的密钥!"
