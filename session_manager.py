import time
import logging
from config import SESSION_TIMEOUT, MAX_WAIT_TIME

logger = logging.getLogger(__name__)

# 用户会话管理
user_sessions = {}
active_requests = {}
last_request_time = {}


def clean_expired_sessions():
    """清理超时的会话"""
    current_time = time.time()
    expired_phones = []

    for phone, session in user_sessions.items():
        if current_time - session["last_active"] > SESSION_TIMEOUT:
            expired_phones.append(phone)

    for phone in expired_phones:
        del user_sessions[phone]
        logger.info(f"清理超时会话: 用户 {phone}")

    return len(expired_phones)


def clean_expired_requests():
    """清理超时的请求跟踪"""
    from im_service import send_message_to_im

    current_time = time.time()
    expired_phones = []

    for phone, info in active_requests.items():
        if current_time - info["start_time"] > MAX_WAIT_TIME + 30:
            expired_phones.append(phone)

            try:
                send_message_to_im(
                    "抱歉，您的请求处理时间超出了系统限制，已自动终止。请尝试简化您的问题。",
                    info["group_id"],
                    phone,
                    info["callback_url"],
                )
            except Exception as e:
                logger.error(f"发送超时通知时出错: {e}, 用户: {phone}")

    for phone in expired_phones:
        logger.warning(f"清理超时请求: 用户 {phone}, 已超过 {MAX_WAIT_TIME} 秒")
        del active_requests[phone]

    return len(expired_phones)


def is_user_rate_limited(phone):
    """检查用户是否被频率限制"""
    current_time = time.time()
    if phone in last_request_time:
        time_since_last_request = current_time - last_request_time[phone]
        if time_since_last_request < 1.0:
            return True, time_since_last_request

    last_request_time[phone] = current_time
    return False, 0


def has_active_request(phone):
    """检查用户是否有正在处理的请求"""
    if phone in active_requests:
        elapsed_time = time.time() - active_requests[phone]["start_time"]
        return True, elapsed_time
    return False, 0


def reset_user_session(phone):
    """重置用户会话"""
    if phone in user_sessions:
        del user_sessions[phone]
    if phone in active_requests:
        del active_requests[phone]
    logger.info(f"用户 {phone} 会话已重置")
