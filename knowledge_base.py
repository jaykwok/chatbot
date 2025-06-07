import os
import logging
from config import GROUP_CONFIGS, DEFAULT_GROUP_CONFIG

logger = logging.getLogger(__name__)


def load_knowledge_base(group_id=None):
    """加载本地知识库文件"""
    knowledge_base = []

    # 获取群组配置
    group_config = GROUP_CONFIGS.get(group_id, DEFAULT_GROUP_CONFIG)
    logger.info(f"群组 {group_id} 使用配置: {group_config}")

    # 如果配置不使用知识库，直接返回空列表
    if not group_config.get("use_knowledge_base", True):
        logger.info(f"群组 {group_id} 配置为不使用知识库")
        return knowledge_base

    # 获取该群组的知识库目录
    kb_dir = group_config.get("knowledge_base_dir")
    logger.info(f"群组 {group_id} 使用知识库目录: {kb_dir}")

    if os.path.exists(kb_dir):
        for filename in os.listdir(kb_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(kb_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        knowledge_base.append(f"[文档: {filename}]\n{content}")
                except Exception as e:
                    logger.error(f"读取知识库文件 {filename} 时出错: {e}")
    return knowledge_base
