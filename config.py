import os
import json
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基本配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")

# 默认群组配置
DEFAULT_GROUP_CONFIG = {
    "model": "qwen-plus-latest",
    "reasoning_model": "qwen-plus-latest",
    "system_prompt": "请简洁明了地回答问题，且不要使用Markdown等格式（如*、**等符号）来强调文本。",
}

# 超时设置
SESSION_TIMEOUT = 1800  # 30分钟
MAX_WAIT_TIME = 600  # 10分钟


def load_group_configs():
    """从配置文件加载群组配置"""
    config_file = "./group_configs.json"
    logger = logging.getLogger(__name__)
    logger.info(f"尝试从 {config_file} 加载群组配置")

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                configs = json.load(f)
                logger.info(f"成功加载群组配置，共 {len(configs)} 个群组")
                return configs
        except Exception as e:
            logger.error(f"加载群组配置时出错: {e}")

    logger.warning("未找到群组配置文件或文件无效，使用默认配置")
    return {}


# 加载群组配置
GROUP_CONFIGS = load_group_configs()
