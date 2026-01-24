#!/bin/bash
# 服务器预安装脚本 - 安装打包环境依赖

set -e

echo "=== DevOps 平台 - 服务器环境预安装 ==="

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "错误: 请使用 root 权限运行此脚本"
    exit 1
fi

# 检测系统类型
if [ -f /etc/redhat-release ]; then
    OS="centos"
    echo "检测到 CentOS/RHEL 系统"
elif [ -f /etc/debian_version ]; then
    OS="ubuntu"
    echo "检测到 Ubuntu/Debian 系统"
else
    echo "错误: 不支持的操作系统"
    exit 1
fi

# 更新软件源
echo ""
echo ">>> 更新软件源..."
if [ "$OS" = "centos" ]; then
    yum update -y || yum makecache
else
    apt-get update -y
fi

# 安装基础工具
echo ""
echo ">>> 安装基础工具 (curl, wget, vim)..."
if [ "$OS" = "centos" ]; then
    yum install -y curl wget vim git
else
    apt-get install -y curl wget vim git
fi

# 安装 Java (Maven 依赖)
echo ""
echo ">>> 安装 Java..."
if [ "$OS" = "centos" ]; then
    yum install -y java-11-openjdk java-11-openjdk-devel
else
    apt-get install -y openjdk-11-jdk
fi

# 配置 JAVA_HOME
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk
echo "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk" >> /etc/profile
echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> /etc/profile
source /etc/profile

# 安装 Maven
echo ""
echo ">>> 安装 Maven..."
MAVEN_VERSION="3.9.6"
MAVEN_DIR="apache-maven-${MAVEN_VERSION}"
MAVEN_TARBALL="${MAVEN_DIR}-bin.tar.gz"

if ! command -v mvn >/dev/null 2>&1; then
    cd /tmp
    if [ ! -f "$MAVEN_TARBALL" ]; then
        wget -q "https://downloads.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/${MAVEN_TARBALL}"
    fi
    tar -xzf "$MAVEN_TARBALL" -C /opt/
    ln -sf "/opt/${MAVEN_DIR}" /opt/maven

    # 配置 Maven 环境变量
    cat > /etc/profile.d/maven.sh << 'EOF'
export M2_HOME=/opt/maven
export PATH=$M2_HOME/bin:$PATH
EOF
    chmod +x /etc/profile.d/maven.sh
    source /etc/profile.d/maven.sh

    echo "Maven ${MAVEN_VERSION} 安装完成"
else
    echo "Maven 已安装: $(mvn -version | head -1)"
fi

# 安装 Node.js 和 npm
echo ""
echo ">>> 安装 Node.js 和 npm..."
if ! command -v npm >/dev/null 2>&1; then
    if [ "$OS" = "centos" ]; then
        # 使用 NodeSource 仓库安装 Node.js 20 LTS
        curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
        yum install -y nodejs
    else
        # 使用 NodeSource 仓库安装 Node.js 20 LTS
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    fi
    echo "Node.js $(node -v) 和 npm $(npm -v) 安装完成"
else
    echo "Node.js 已安装: $(node -v), npm: $(npm -v)"
fi

# 配置 npm 镜像（可选，国内用户）
echo ""
read -p "是否配置 npm 淘宝镜像? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    npm config set registry https://registry.npmmirror.com
    echo "npm 镜像已配置为淘宝镜像"
fi

# 配置 Maven 镜像（可选，国内用户）
echo ""
read -p "是否配置 Maven 阿里云镜像? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    MAVEN_SETTINGS="/opt/maven/conf/settings.xml"
    if [ -f "$MAVEN_SETTINGS" ]; then
        # 备份原配置
        cp "$MAVEN_SETTINGS" "${MAVEN_SETTINGS}.bak"
        # 添加阿里云镜像
        sed -i '/<mirrors>/a\    <mirror>\n      <id>aliyun</id>\n      <mirrorOf>central</mirrorOf>\n      <name>Aliyun Maven</name>\n      <url>https://maven.aliyun.com/repository/public</url>\n    </mirror>' "$MAVEN_SETTINGS"
        echo "Maven 镜像已配置为阿里云镜像"
    fi
fi

# 显示安装结果
echo ""
echo "=== 安装完成 ==="
echo ""
echo "已安装组件版本:"
echo "  Git:      $(git --version)"
echo "  Java:     $(java -version 2>&1 | head -1)"
echo "  Maven:    $(mvn -version | head -1 2>/dev/null || echo '未安装')"
echo "  Node.js:  $(node -v 2>/dev/null || echo '未安装')"
echo "  npm:      $(npm -v 2>/dev/null || echo '未安装')"
echo ""
echo "请重新登录或执行以下命令使环境变量生效:"
echo "  source /etc/profile"
echo "  source /etc/profile.d/maven.sh"
echo ""
