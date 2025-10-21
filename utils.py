import logging
from flask import request

logger = logging.getLogger(__name__)


def get_client_ip():
    """从请求头中提取用户IP地址"""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.remote_addr
    return client_ip


def setup_logging():
    """配置日志"""
    import os
    from logging.handlers import RotatingFileHandler

    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)

    # 配置日志格式和处理器
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                "logs/chatbot.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8",
            ),
        ],
    )
