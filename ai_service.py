import time
import logging
from openai import OpenAI
from config import (
    DASHSCOPE_API_KEY,
    BASE_URL,
    GROUP_CONFIGS,
    DEFAULT_GROUP_CONFIG,
    SESSION_TIMEOUT,
    MAX_WAIT_TIME,
)
from session_manager import user_sessions

logger = logging.getLogger(__name__)

# 初始化OpenAI客户端
client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=BASE_URL,
)


def get_ai_response(message, phone, group_id, use_reasoning_model=False):
    """使用DashScope API获取回复"""
    try:
        group_config = GROUP_CONFIGS.get(group_id, DEFAULT_GROUP_CONFIG)
        current_time = time.time()

        # 会话管理
        is_new_session = False
        if phone not in user_sessions or (
            current_time - user_sessions[phone]["last_active"] > SESSION_TIMEOUT
        ):
            user_sessions[phone] = {"messages": [], "last_active": current_time}
            logger.info(f"为用户 {phone} 创建新会话，群组: {group_id}")
            is_new_session = True
        else:
            user_sessions[phone]["last_active"] = current_time

        # 构建消息
        messages = []
        instruction = group_config.get(
            "system_prompt", DEFAULT_GROUP_CONFIG["system_prompt"]
        )

        if not use_reasoning_model:
            messages.append({"role": "system", "content": instruction})

        # 添加历史消息
        messages.extend(user_sessions[phone]["messages"][-20:])

        # 添加当前消息
        if use_reasoning_model:
            enhanced_message = (
                f"请按照以下指令行动：{instruction}\n\n用户问题：{message}"
            )
            messages.append({"role": "user", "content": enhanced_message})
        else:
            messages.append({"role": "user", "content": message})

        # 获取模型回复
        model = (
            group_config.get("reasoning_model", DEFAULT_GROUP_CONFIG["reasoning_model"])
            if use_reasoning_model
            else group_config.get("model", DEFAULT_GROUP_CONFIG["model"])
        )

        if use_reasoning_model:
            ai_response = _get_reasoning_response(model, messages)
        else:
            ai_response = _get_normal_response(model, messages)

        # 更新会话历史
        user_sessions[phone]["messages"].extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": ai_response},
            ]
        )

        return ai_response, is_new_session

    except Exception as e:
        logger.error(f"获取AI回复时出错: {e}, 群组: {group_id}")
        return f"抱歉，我遇到了技术问题，无法回答您的问题。错误: {str(e)}", False


def _get_reasoning_response(model, messages):
    """获取推理模式回复"""
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        extra_body={"enable_thinking": True},
    )

    reasoning_content = ""
    answer_content = ""
    start_time = time.time()

    for chunk in completion:
        if time.time() - start_time > MAX_WAIT_TIME:
            logger.warning("流式处理超时，提前结束")
            if answer_content:
                answer_content += "\n\n[注意: 由于处理时间过长，回复已提前结束]"
            else:
                answer_content = "处理超时，请尝试简化您的问题或稍后再试。"
            break

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta
        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
            reasoning_content += delta.reasoning_content
        if delta.content is not None:
            answer_content += delta.content

    return answer_content


def _get_normal_response(model, messages):
    """获取普通模式回复"""
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        extra_body={"enable_thinking": False},
    )
    return completion.choices[0].message.content
