#!/bin/bash
# 生产环境部署脚本

set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时退出
set -o pipefail  # 管道中任何命令失败都会导致整个管道失败

INSTALL_DIR="/opt/devops"
SERVICE_NAME="devops-backend"
NGINX_CONF="devops-nginx.conf"
SYSTEMD_SERVICE="devops-backend.service"

echo "=== DevOps 平台 - 生产环境部署 ==="

# 颜色输出辅助函数
info() { echo -e "\033[0;34m[INFO]\033[0m $1"; }
success() { echo -e "\033[0;32m[SUCCESS]\033[0m $1"; }
warning() { echo -e "\033[0;33m[WARNING]\033[0m $1"; }
error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    error "请使用 root 权限运行此脚本"
    exit 1
fi

# 检查依赖版本
check_python_version() {
    if ! command -v python3 >/dev/null 2>&1; then
        error "未找到 Python 3，请先安装 Python 3.11+"
        exit 1
    fi

    local python_version=$(python3 --version | awk '{print $2}')
    local major=$(echo $python_version | cut -d. -f1)
    local minor=$(echo $python_version | cut -d. -f2)

    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 11 ]); then
        error "Python 版本过低: $python_version (需要 3.11+)"
        exit 1
    fi
    success "Python 版本检查通过: $python_version"
}

check_node_version() {
    if ! command -v node >/dev/null 2>&1; then
        error "未找到 Node.js，请先安装 Node.js 20+"
        exit 1
    fi

    local node_version=$(node --version | sed 's/v//')
    local major=$(echo $node_version | cut -d. -f1)

    if [ "$major" -lt 20 ]; then
        error "Node.js 版本过低: v$node_version (需要 20+)"
        exit 1
    fi
    success "Node.js 版本检查通过: v$node_version"
}

check_dependencies() {
    info "检查依赖项..."
    check_python_version
    check_node_version

    # 检查其他必需命令
    local required_commands=("npm" "git" "nginx" "systemctl")
    for cmd in "${required_commands[@]}"; do
        if ! command -v $cmd >/dev/null 2>&1; then
            error "未找到必需命令: $cmd"
            exit 1
        fi
    done
    success "所有依赖项检查通过"
}

check_dependencies

# Detect operating system
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
    else
        OS="unknown"
    fi
}

# Check Java/Maven build tools
check_java_tools() {
    info "检查 Java/Maven 构建工具..."

    # Check Java
    if command -v java >/dev/null 2>&1; then
        local java_version=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | awk -F. '{print $1}')
        if [ -n "$java_version" ] && [ "$java_version" -ge 11 ]; then
            success "Java: $java_version+"
        else
            warning "Java: 版本过低 (需要 JDK 11+)"
            if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
                info "  安装命令（Ubuntu/Debian）: sudo apt-get install openjdk-11-jdk"
            elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "rocky" ] || [ "$OS" = "almalinux" ]; then
                info "  安装命令（CentOS/RHEL）: sudo yum install java-11-openjdk-devel"
            fi
        fi
    else
        warning "Java: 未找到 (构建 Java 项目需要 JDK 11+)"
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            info "  安装命令（Ubuntu/Debian）: sudo apt-get install openjdk-11-jdk"
        elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "rocky" ] || [ "$OS" = "almalinux" ]; then
            info "  安装命令（CentOS/RHEL）: sudo yum install java-11-openjdk-devel"
        fi
    fi

    # Check Maven
    if command -v mvn >/dev/null 2>&1; then
        local maven_version=$(mvn -version 2>&1 | grep "Apache Maven" | awk '{print $3}')
        if [ -n "$maven_version" ]; then
            success "Maven: $maven_version"
        else
            warning "Maven: 已安装但无法获取版本信息"
        fi
    else
        warning "Maven: 未找到 (构建 Java 项目需要 Maven 3.6+)"
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            info "  安装命令（Ubuntu/Debian）: sudo apt-get install maven"
        elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "rocky" ] || [ "$OS" = "almalinux" ]; then
            info "  安装命令（CentOS/RHEL）: sudo yum install maven"
        fi
    fi
}

# Check Python build tools
check_python_tools() {
    info "检查 Python 构建工具..."

    # Skip Python check as it's already checked in check_dependencies()
    info "  Python 已在依赖检查中验证"

    # Check pip
    if command -v pip3 >/dev/null 2>&1; then
        local pip_version=$(pip3 --version 2>/dev/null | awk '{print $2}')
        success "pip: $pip_version"
    else
        warning "pip: 未找到"
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            info "  安装命令（Ubuntu/Debian）: sudo apt-get install python3-pip"
        elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "rocky" ] || [ "$OS" = "almalinux" ]; then
            info "  安装命令（CentOS/RHEL）: sudo yum install python3-pip"
        fi
    fi
}

# Check Node.js build tools
check_node_tools() {
    info "检查 Node.js 构建工具..."

    # Skip Node.js and npm checks as they are already checked in check_dependencies()
    info "  Node.js 和 npm 已在依赖检查中验证"
}

# Check compile tools
check_compile_tools() {
    info "检查编译工具..."

    local has_gcc=0
    local has_gpp=0

    if command -v gcc >/dev/null 2>&1; then
        local gcc_version=$(gcc --version 2>/dev/null | awk 'NR==1 {print $3}' | awk -F. '{print $1"."$2}')
        success "gcc: $gcc_version"
        has_gcc=1
    else
        warning "gcc: 未找到"
    fi

    if command -v g++ >/dev/null 2>&1; then
        local gpp_version=$(g++ --version 2>/dev/null | awk 'NR==1 {print $3}' | awk -F. '{print $1"."$2}')
        success "g++: $gpp_version"
        has_gpp=1
    else
        warning "g++: 未找到"
    fi

    if [ $has_gcc -eq 0 ] || [ $has_gpp -eq 0 ]; then
        info "  某些项目（如 Python 原生模块）可能需要编译工具"
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            info "  安装命令（Ubuntu/Debian）: sudo apt-get install build-essential"
        elif [ "$OS" = "rhel" ] || [ "$OS" = "centos" ] || [ "$OS" = "rocky" ] || [ "$OS" = "almalinux" ]; then
            info "  安装命令（CentOS/RHEL）: sudo yum groupinstall 'Development Tools'"
        fi
    fi
}

# Check build environment
check_build_environment() {
    echo ""
    info "=== 检查构建环境 ==="
    echo ""

    # Detect OS first
    detect_os

    # Check different tool categories
    check_java_tools
    echo ""

    check_python_tools
    echo ""

    check_node_tools
    echo ""

    check_compile_tools
    echo ""

    info "=== 构建环境检查完成 ==="
    info "提示: 缺失的工具不会影响平台运行，但会影响相应类型项目的构建"
    echo ""
}

check_build_environment

# 获取项目目录（假设脚本在项目目录下运行）
PROJECT_ROOT=$(pwd)
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

info "项目目录: $PROJECT_ROOT"

# 验证必要的目录是否存在
validate_directories() {
    info "验证项目目录结构..."

    if [ ! -d "$BACKEND_DIR" ]; then
        error "后端目录不存在: $BACKEND_DIR"
        error "请确保从项目根目录运行此脚本"
        exit 1
    fi

    if [ ! -d "$FRONTEND_DIR" ]; then
        error "前端目录不存在: $FRONTEND_DIR"
        error "请确保从项目根目录运行此脚本"
        exit 1
    fi

    if [ ! -d "$DEPLOY_DIR" ]; then
        error "部署配置目录不存在: $DEPLOY_DIR"
        error "请确保从项目根目录运行此脚本"
        exit 1
    fi

    if [ ! -f "$DEPLOY_DIR/$NGINX_CONF" ]; then
        error "Nginx 配置文件不存在: $DEPLOY_DIR/$NGINX_CONF"
        exit 1
    fi

    if [ ! -f "$DEPLOY_DIR/$SYSTEMD_SERVICE" ]; then
        error "Systemd 服务文件不存在: $DEPLOY_DIR/$SYSTEMD_SERVICE"
        exit 1
    fi

    success "目录结构验证通过"
}

validate_directories

# 1. 创建用户和目录
echo ""
info "创建用户和目录..."

if ! id -u devops >/dev/null 2>&1; then
    useradd -r -s /bin/bash -d $INSTALL_DIR devops
    success "创建用户: devops"
else
    info "用户 devops 已存在"
fi

mkdir -p $INSTALL_DIR/{backend,frontend,data,work,artifacts,logs}
chown -R devops:devops $INSTALL_DIR
success "创建并配置目录: $INSTALL_DIR"

# 设置 nginx 日志目录权限（nginx 需要写入权限）
mkdir -p $INSTALL_DIR/logs
chmod 755 $INSTALL_DIR/logs
# 如果 nginx 运行在 www-data 用户下，需要设置适当的权限
if id -u www-data >/dev/null 2>&1; then
    chown www-data:www-data $INSTALL_DIR/logs
    info "设置 nginx 日志目录所有者为 www-data"
else
    warning "www-data 用户不存在，nginx 日志目录权限可能需要手动调整"
fi

# 2. 部署后端
echo ""
info "部署后端..."

# 复制后端文件
cp -r $BACKEND_DIR/* $INSTALL_DIR/backend/
chown -R devops:devops $INSTALL_DIR/backend
success "复制后端文件"

cd $INSTALL_DIR/backend

# 创建虚拟环境
if [ ! -d "venv" ]; then
    info "创建 Python 虚拟环境..."
    sudo -u devops python3 -m venv venv || {
        error "创建虚拟环境失败"
        exit 1
    }
    success "虚拟环境创建成功"
fi

# 升级 pip 并安装依赖
info "安装 Python 依赖..."
sudo -u devops venv/bin/pip install --upgrade pip -q || {
    error "升级 pip 失败"
    exit 1
}

if [ -f "requirements.txt" ]; then
    sudo -u devops venv/bin/pip install -r requirements.txt -q || {
        error "安装 Python 依赖失败，请检查 requirements.txt"
        exit 1
    }
    success "Python 依赖安装完成"
else
    error "未找到 requirements.txt"
    exit 1
fi

# 检查 alembic 是否安装
if ! sudo -u devops venv/bin/python -c "import alembic" 2>/dev/null; then
    error "alembic 未安装，正在安装..."
    sudo -u devops venv/bin/pip install alembic -q || {
        error "安装 alembic 失败"
        exit 1
    }
fi

# 生成安全密钥函数
generate_secret_key() {
    # 使用 venv 中的 Python 生成密钥，确保版本和模块正确
    sudo -u devops venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'
}

# 配置生产环境
if [ ! -f ".env.production" ]; then
    info "配置生产环境变量..."
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
SECRET_KEY=$(generate_secret_key)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Encryption - 请修改为强密钥!
ENCRYPTION_KEY=$(generate_secret_key)

# File Storage
WORK_DIR=./work
ARTIFACTS_DIR=./artifacts
LOGS_DIR=./logs

# CORS - 请修改为实际域名
CORS_ORIGINS=http://your-domain.com
EOF

    chown devops:devops .env.production
    chmod 600 .env.production
    warning "已生成 .env.production，请编辑配置后重新运行部署"
    warning "特别注意修改 SECRET_KEY、ENCRYPTION_KEY 和 CORS_ORIGINS"
    exit 1
else
    info ".env.production 已存在，跳过配置"
fi

# 初始化数据库
info "初始化数据库..."
if [ -f "alembic.ini" ] && [ -d "alembic" ]; then
    sudo -u devops venv/bin/alembic upgrade head || {
        error "数据库迁移失败"
        exit 1
    }
    success "数据库初始化完成"
else
    warning "未找到 alembic 配置，跳过数据库迁移"
fi

# 3. 部署前端
echo ""
info "部署前端..."

# 复制前端文件
cp -r $FRONTEND_DIR/* $INSTALL_DIR/frontend/
chown -R devops:devops $INSTALL_DIR/frontend
success "复制前端文件"

cd $INSTALL_DIR/frontend

# 检查 package.json
if [ ! -f "package.json" ]; then
    error "未找到 package.json"
    exit 1
fi

# 安装依赖
info "安装 Node.js 依赖..."
sudo -u devops npm install || {
    error "npm install 失败"
    exit 1
}
success "Node.js 依赖安装完成"

# 构建前端
info "构建前端..."
if sudo -u devops npm run build 2>&1; then
    success "前端构建完成"
else
    error "前端构建失败"
    exit 1
fi

# 4. 配置 systemd
echo ""
info "配置 systemd 服务..."

if [ ! -f "$DEPLOY_DIR/$SYSTEMD_SERVICE" ]; then
    error "Systemd 服务文件不存在: $DEPLOY_DIR/$SYSTEMD_SERVICE"
    exit 1
fi

cp $DEPLOY_DIR/$SYSTEMD_SERVICE /etc/systemd/system/
systemctl daemon-reload || {
    error "systemctl daemon-reload 失败"
    exit 1
}
systemctl enable $SERVICE_NAME || {
    error "启用服务失败"
    exit 1
}
success "Systemd 服务配置完成"

# 5. 配置 nginx
echo ""
info "配置 Nginx..."

# 确定nginx配置目录
if [ -d "/etc/nginx/sites-available" ]; then
    NGINX_SITES="/etc/nginx/sites-available"
    NGINX_ENABLED="/etc/nginx/sites-enabled"
elif [ -d "/etc/nginx/conf.d" ]; then
    NGINX_SITES="/etc/nginx/conf.d"
    NGINX_ENABLED="/etc/nginx/conf.d"
else
    error "无法确定 Nginx 配置目录"
    exit 1
fi

# 备份现有配置（如果存在）
if [ -f "$NGINX_SITES/$NGINX_CONF" ]; then
    backup_file="$NGINX_SITES/$NGINX_CONF.backup.$(date +%Y%m%d%H%M%S)"
    cp "$NGINX_SITES/$NGINX_CONF" "$backup_file"
    info "备份现有配置到: $backup_file"
fi

cp $DEPLOY_DIR/$NGINX_CONF $NGINX_SITES/
ln -sf $NGINX_SITES/$NGINX_CONF $NGINX_ENABLED/$NGINX_CONF

# 测试 nginx 配置
info "测试 Nginx 配置..."
if nginx -t 2>&1; then
    success "Nginx 配置测试通过"
else
    error "Nginx 配置测试失败"
    error "请检查配置文件: $NGINX_SITES/$NGINX_CONF"
    exit 1
fi

# 6. 启动服务
echo ""
info "启动服务..."

# 重启后端服务
if systemctl restart $SERVICE_NAME 2>&1; then
    success "后端服务启动成功"
else
    error "后端服务启动失败"
    error "查看日志: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# 等待服务启动
sleep 3

# 检查服务状态
if systemctl is-active --quiet $SERVICE_NAME; then
    success "后端服务运行正常"
else
    warning "后端服务可能未正常启动，请检查日志"
fi

# 重启 nginx
if systemctl restart nginx 2>&1; then
    success "Nginx 服务启动成功"
else
    error "Nginx 服务启动失败"
    systemctl status nginx
    exit 1
fi

echo ""
success "=== 部署完成 ==="
echo ""
echo "========================================"
echo "服务管理命令:"
echo "========================================"
echo "  启动服务: systemctl start $SERVICE_NAME"
echo "  停止服务: systemctl stop $SERVICE_NAME"
echo "  重启服务: systemctl restart $SERVICE_NAME"
echo "  查看状态: systemctl status $SERVICE_NAME"
echo "  查看日志: journalctl -u $SERVICE_NAME -f"
echo "  Nginx状态: systemctl status nginx"
echo "  Nginx日志: tail -f /var/log/nginx/error.log"
echo ""
echo "========================================"
echo "访问信息:"
echo "========================================"
echo "  访问地址: http://$(hostname -I | awk '{print $1}')"
echo "  默认账号: admin / admin123"
echo ""
echo "========================================"
echo "安全提醒:"
echo "========================================"
warning "请立即修改以下配置:"
echo "  1. /opt/devops/backend/.env.production 中的密钥"
echo "  2. 修改默认管理员密码"
echo "  3. 配置正确的 CORS_ORIGINS"
echo "  4. 考虑使用 HTTPS (配置 SSL 证书)"
echo ""
echo "========================================"
echo "下一步操作建议:"
echo "========================================"
echo "  1. 检查服务状态: systemctl status $SERVICE_NAME"
echo "  2. 查看服务日志: journalctl -u $SERVICE_NAME -n 100"
echo "  3. 检查端口监听: netstat -tlnp | grep 9090"
echo "  4. 测试API访问: curl http://localhost:9090/api/health"
echo "========================================"
