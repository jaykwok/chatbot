#!/bin/bash

# 聊天机器人部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_status() { echo -e "${BLUE}🚀 $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

print_status "开始部署AI聊天机器人..."

# 检查必要文件
print_status "检查必要文件..."
required_files=(".env" "group_configs.json" "gunicorn.conf.py" "wsgi.py")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "缺少必要文件: $file"
        exit 1
    fi
done
print_success "必要文件检查通过"

# 创建必要目录和文件
print_status "创建必要目录和文件..."
mkdir -p logs static templates

# 设置日志目录权限
chmod 777 logs
print_success "目录和文件创建完成"

# 停止并删除现有容器
print_status "停止现有容器..."
if docker ps -a --format "table {{.Names}}" | grep -q "^chatbot$"; then
    docker stop chatbot || true
    docker rm chatbot || true
    print_success "现有容器已清理"
else
    print_success "没有发现现有容器"
fi

# 构建新镜像
print_status "构建Docker镜像..."
if docker build -t chatbot .; then
    print_success "镜像构建成功"
else
    print_error "镜像构建失败"
    exit 1
fi

# 运行新容器
print_status "启动新容器..."
if docker run -d \
  -p 1011:1011 \
  -v "$(pwd)/.env:/app/.env:ro" \
  -v "$(pwd)/group_configs.json:/app/group_configs.json:ro" \
  -v "$(pwd)/logs:/app/logs" \
  --restart unless-stopped \
  --name chatbot \
  --memory="512m" \
  --cpus="1.0" \
  chatbot; then
    print_success "容器启动成功"
else
    print_error "容器启动失败"
    exit 1
fi

# 等待服务启动
print_status "等待服务启动..."
sleep 8

# 检查容器状态
if docker ps --format "table {{.Names}}" | grep -q "^chatbot$"; then
    print_success "服务启动成功"

    SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")

    echo ""
    echo "🎉 部署完成！"
    echo ""
    echo "📋 服务信息:"
    echo "  🤖 Webhook端点: http://${SERVER_IP}:1011/webhook"
    echo "  🔐 管理页面: http://${SERVER_IP}:1011/sessions (需要认证)"
    echo "  📝 配置文件: $(pwd)/.env, $(pwd)/group_configs.json"
    echo "  📝 日志目录: $(pwd)/logs"
    echo ""
    echo "📊 容器资源限制:"
    echo "  💾 内存限制: 512MB"
    echo "  🖥️  CPU限制: 1.0核"
    echo ""
    print_status "最近日志:"
    docker logs --tail 20 chatbot

    echo ""
    echo "🛠️  常用命令:"
    echo "  📝 查看实时日志: docker logs -f chatbot"
    echo "  🔄 重启服务: docker restart chatbot"
    echo "  ⏹️  停止服务: docker stop chatbot"
    echo "  🔍 进入容器: docker exec -it chatbot /bin/bash"
    echo "  📊 容器状态: docker stats chatbot"
else
    print_error "服务启动失败"
    echo ""
    print_status "错误日志:"
    docker logs chatbot
    echo ""
    print_status "容器状态:"
    docker ps -a --filter name=chatbot
    exit 1
fi

echo ""
print_success "AI聊天机器人部署完成！"