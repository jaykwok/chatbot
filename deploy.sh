#!/bin/bash

# deploy.sh - AI聊天机器人部署脚本

set -e

echo "🚀 开始部署AI聊天机器人..."

# 检查必要文件
echo "📋 检查必要文件..."
required_files=(".env" "group_configs.json")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ 缺少必要文件: $file"
        exit 1
    fi
done

# 创建必要目录和文件
echo "📁 创建必要目录和文件..."
mkdir -p knowledge_base logs static templates

# 预创建日志文件并设置权限
touch logs/chatbot.log
chmod 666 logs/chatbot.log

# 确保目录权限正确
chmod 755 knowledge_base logs

echo "✅ 目录和文件创建完成"

# 停止并删除现有容器
echo "🛑 停止现有容器..."
if docker ps -a | grep -q chatbot; then
    docker stop chatbot || true
    docker rm chatbot || true
    echo "✅ 现有容器已清理"
fi

# 构建新镜像
echo "🔨 构建Docker镜像..."
docker build -t chatbot .

# 运行新容器
echo "🚀 启动新容器..."
docker run -d \
  -p 1011:1011 \
  -v $(pwd)/knowledge_base:/app/knowledge_base \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/group_configs.json:/app/group_configs.json \
  --env-file .env \
  --restart unless-stopped \
  --name chatbot \
  chatbot

echo "✅ 容器启动完成"

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查容器状态
if docker ps | grep -q chatbot; then
    echo "✅ 服务启动成功"
    echo "🌐 管理页面: http://localhost:1011/sessions"
    echo "📊 API端点: http://localhost:1011/webhook"
    echo "📝 日志文件: $(pwd)/logs/chatbot.log"
    
    # 显示最近日志
    echo ""
    echo "📝 最近日志:"
    docker logs --tail 50 chatbot
else
    echo "❌ 服务启动失败"
    echo "📝 错误日志:"
    docker logs chatbot
    exit 1
fi

echo ""
echo "🎉 部署完成！"
echo ""
echo "常用命令:"
echo "  查看日志: docker logs -f chatbot"
echo "  重启服务: docker restart chatbot"
echo "  停止服务: docker stop chatbot"
echo "  进入容器: docker exec -it chatbot /bin/bash"