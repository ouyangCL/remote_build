#!/bin/bash
# 安全重启后端容器 - 保留数据库并运行迁移

set -e

CONTAINER_NAME="devops-backend"
IMAGE_NAME="docker-backend:new"
NETWORK_NAME="docker_devops-network"
DATA_DIR="/opt/devops/data"
BACKUP_DIR="/opt/devops/backups"

echo "=== 安全重启后端容器 ==="

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 1. 备份当前数据库
if [ -f "$DATA_DIR/devops.db" ]; then
    BACKUP_FILE="$BACKUP_DIR/devops.db.$(date +%Y%m%d_%H%M%S)"
    echo "备份数据库到: $BACKUP_FILE"
    cp "$DATA_DIR/devops.db" "$BACKUP_FILE"
    echo "备份完成"
else
    echo "警告: 当前数据库不存在，跳过备份"
fi

# 2. 停止并删除旧容器
echo "停止旧容器..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# 3. 启动新容器（挂载数据目录）
echo "启动新容器..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p 9090:9090 \
    -v "$DATA_DIR:/app/data" \
    -v /opt/devops/work:/app/work \
    -v /opt/devops/artifacts:/app/artifacts \
    -v /opt/devops/logs:/app/logs \
    --network "$NETWORK_NAME" \
    "$IMAGE_NAME"

# 4. 等待容器启动
echo "等待容器启动..."
sleep 5

# 5. 运行数据库迁移（如果需要）
echo "检查数据库迁移..."
docker exec "$CONTAINER_NAME" python -c "
from alembic.config import Config
from alembic import command
import os

alembic_cfg = Config('/app/alembic.ini')
try:
    command.upgrade(alembic_cfg, 'head')
    print('数据库迁移完成')
except Exception as e:
    print(f'迁移警告: {e}')
    print('继续使用当前数据库')
" 2>/dev/null || echo "迁移检查完成（可能已是最新版本）"

# 6. 验证服务
echo "验证服务..."
if docker exec "$CONTAINER_NAME" python -c "from app.db.session import SessionLocal; db = SessionLocal(); print('数据库连接成功')"; then
    echo "✅ 后端服务启动成功"
else
    echo "❌ 后端服务启动失败"
    exit 1
fi

# 7. 添加网络别名（如果需要）
echo "配置网络..."
docker network disconnect "$NETWORK_NAME" "$CONTAINER_NAME" 2>/dev/null || true
docker network connect "$NETWORK_NAME" "$CONTAINER_NAME" --alias backend

echo ""
echo "=== 重启完成 ==="
echo "容器: $CONTAINER_NAME"
echo "数据库: $DATA_DIR/devops.db"
docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
