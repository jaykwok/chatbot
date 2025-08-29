import time
import gevent
from flask import Flask, request, jsonify, render_template
from werkzeug.exceptions import BadRequest, Forbidden, TooManyRequests
from contextlib import contextmanager
from typing import Dict, Any, Tuple, Optional

from utils import setup_logging, get_client_ip
from session_manager import (
    clean_expired_sessions,
    clean_expired_requests,
    is_user_rate_limited,
    has_active_request,
    reset_user_session,
    user_sessions,
    active_requests,
    last_request_time,
)
from ai_service import get_ai_response
from im_service import send_message_to_im
from knowledge_base import load_knowledge_base
from auth import requires_auth
from config import GROUP_CONFIGS, DEFAULT_GROUP_CONFIG, MAX_WAIT_TIME

# 初始化日志记录
setup_logging()
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

# 常量定义
REASONING_PREFIXES = ("思考:", "思考：")
RESET_COMMANDS = {"重置", "reset", "新对话", "new chat"}
VALID_DOMAINS = ("https://imtwo.zdxlz.com/", "https://im.zdxlz.com/")
REQUIRED_WEBHOOK_FIELDS = ["type", "textMsg", "phone", "groupId", "callBackUrl"]

# 清理阈值常量
SESSION_CLEANUP_THRESHOLD = 100
ACTIVE_REQUEST_CLEANUP_THRESHOLD = 20
RATE_LIMIT_CLEANUP_THRESHOLD = 1000
RATE_LIMIT_EXPIRE_TIME = 600

# 欢迎消息模板
WELCOME_GUIDE = """欢迎使用AI助手！以下是基本操作说明：

- 输入「重置」或「reset」: 清除历史对话记录，开始新对话
- 对话前面添加「思考:」: 启动推理模式，例如"思考:9.9和9.11哪个大"

有任何问题，随时向我提问！"""


@contextmanager
def request_context(phone: str, operation: str, client_ip: str = None):
    """请求上下文管理器，用于统一的日志记录和错误处理"""
    if client_ip is None:
        try:
            client_ip = get_client_ip()
        except RuntimeError:
            client_ip = "Unknown"

    start_time = time.time()

    logger.info(f"{operation} 开始 - 用户: {phone}, IP: {client_ip}")

    try:
        yield
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            f"{operation} 失败 - 用户: {phone}, IP: {client_ip}, "
            f"耗时: {processing_time:.2f}秒, 错误: {e}"
        )
        raise
    else:
        processing_time = time.time() - start_time
        logger.info(
            f"{operation} 完成 - 用户: {phone}, IP: {client_ip}, "
            f"耗时: {processing_time:.2f}秒"
        )


def validate_webhook_data(data: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """验证并提取webhook数据"""
    # 检查必要字段
    missing_fields = [field for field in REQUIRED_WEBHOOK_FIELDS if field not in data]
    if missing_fields:
        raise BadRequest(f"缺少必要字段: {missing_fields}")

    # 检查消息类型
    if data.get("type") != "text":
        raise BadRequest(f"不支持的消息类型: {data.get('type')}")

    # 提取数据
    phone = data.get("phone", "").strip()
    group_id = data.get("groupId", "").strip()
    callback_url = data.get("callBackUrl", "").strip()

    text_msg = data.get("textMsg", {})
    content = text_msg.get("content", "").strip() if isinstance(text_msg, dict) else ""

    # 验证数据有效性
    if not phone or not group_id or not content:
        raise BadRequest("phone、groupId 或 content 不能为空")

    # 验证回调URL
    if not any(callback_url.startswith(domain) for domain in VALID_DOMAINS):
        raise Forbidden(f"无效的回调URL: {callback_url}")

    return phone, group_id, content, callback_url


def check_user_permissions(phone: str) -> None:
    """检查用户权限和限制"""
    # 频率限制检查
    is_limited, time_diff = is_user_rate_limited(phone)
    if is_limited:
        raise TooManyRequests(f"请求频率过高，请 {time_diff:.1f} 秒后再试")

    # 检查活跃请求
    has_active, elapsed_time = has_active_request(phone)
    if has_active and elapsed_time < MAX_WAIT_TIME:
        raise TooManyRequests(
            f"上一个请求正在处理中，已处理 {int(elapsed_time)} 秒。如需取消，请输入'重置'"
        )


def parse_content(content: str) -> Tuple[bool, str]:
    """解析消息内容，判断是否为思考模式并提取实际内容"""
    use_reasoning = any(content.startswith(prefix) for prefix in REASONING_PREFIXES)
    if use_reasoning:
        # 去掉前缀
        actual_content = content[3:].strip()
        return True, actual_content
    return False, content


def get_group_knowledge_base(group_id: str) -> Optional[Any]:
    """获取群组知识库"""
    group_config = GROUP_CONFIGS.get(group_id, DEFAULT_GROUP_CONFIG)
    if group_config.get("use_knowledge_base", True):
        return load_knowledge_base(group_id)
    return None


def send_welcome_if_needed(
    is_new_session: bool, group_id: str, phone: str, callback_url: str
) -> None:
    """如果是新会话，发送欢迎消息"""
    if is_new_session:
        send_message_to_im(WELCOME_GUIDE, group_id, phone, callback_url)


def perform_periodic_cleanup() -> None:
    """执行定期清理任务"""
    # 清理过期会话
    if len(user_sessions) > SESSION_CLEANUP_THRESHOLD:
        cleaned_count = clean_expired_sessions()
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个过期会话")

    # 清理超时请求
    if len(active_requests) > ACTIVE_REQUEST_CLEANUP_THRESHOLD:
        cleaned_count = clean_expired_requests()
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个超时请求")

    # 清理过期的频率限制记录
    if len(last_request_time) > RATE_LIMIT_CLEANUP_THRESHOLD:
        current_time = time.time()
        expired_time = current_time - RATE_LIMIT_EXPIRE_TIME
        expired_phones = [
            phone
            for phone, timestamp in last_request_time.items()
            if timestamp < expired_time
        ]
        for phone in expired_phones:
            del last_request_time[phone]
        if expired_phones:
            logger.info(f"清理了 {len(expired_phones)} 个过期的频率限制记录")


def process_reasoning_request(
    content: str,
    phone: str,
    group_id: str,
    callback_url: str,
    client_ip: str = "Unknown",
) -> None:
    """后台处理思考模式请求"""
    with request_context(phone, "思考模式处理", client_ip):
        try:
            # 更新请求状态
            active_requests[phone] = {
                "start_time": time.time(),
                "status": "processing",
                "group_id": group_id,
                "callback_url": callback_url,
            }

            # 获取知识库
            knowledge_base = get_group_knowledge_base(group_id)

            # 发送进度消息
            send_message_to_im(
                "正在思考中，这可能需要一些时间...", group_id, phone, callback_url
            )

            # 获取AI回复
            ai_response, is_new_session = get_ai_response(
                content, phone, group_id, knowledge_base, use_reasoning_model=True
            )

            # 发送回复和欢迎消息
            send_message_to_im(ai_response, group_id, phone, callback_url)
            send_welcome_if_needed(is_new_session, group_id, phone, callback_url)

        except Exception as e:
            logger.error(f"处理思考请求时出错: {e}")
            send_message_to_im(
                "抱歉，处理您的请求时出现了错误，请稍后再试。",
                group_id,
                phone,
                callback_url,
            )
        finally:
            # 清理请求跟踪
            if phone in active_requests:
                del active_requests[phone]


def process_normal_request(
    content: str,
    phone: str,
    group_id: str,
    callback_url: str,
    client_ip: str = "Unknown",
) -> None:
    """处理普通请求"""
    with request_context(phone, "普通请求处理", client_ip):
        # 获取知识库
        knowledge_base = get_group_knowledge_base(group_id)

        # 获取AI回复
        ai_response, is_new_session = get_ai_response(
            content, phone, group_id, knowledge_base, use_reasoning_model=False
        )

        # 发送回复和欢迎消息
        send_message_to_im(ai_response, group_id, phone, callback_url)
        send_welcome_if_needed(is_new_session, group_id, phone, callback_url)


@app.route("/webhook", methods=["POST"])
def webhook():
    """处理来自IM平台的webhook请求"""
    client_ip = get_client_ip()

    try:
        # 验证请求格式
        if not request.is_json:
            logger.warning(f"收到非JSON请求: {request.content_type}, IP: {client_ip}")
            raise BadRequest("请求必须是JSON格式")

        # 验证和提取数据
        data = request.json
        phone, group_id, content, callback_url = validate_webhook_data(data)

        logger.info(
            f"收到请求 - IP: {client_ip}, 用户: {phone}, 群组: {group_id}, 内容: {content[:50]}..."
        )

        # 检查用户权限
        try:
            check_user_permissions(phone)
        except TooManyRequests as e:
            # 对于活跃请求的情况，需要发送消息而不是直接返回错误
            if "上一个请求正在处理中" in str(e):
                send_message_to_im(str(e), group_id, phone, callback_url)
                return jsonify({"status": "success"})
            else:
                logger.warning(f"用户 {phone} 请求频率过高: IP {client_ip}")
                raise

        # 解析内容
        use_reasoning, actual_content = parse_content(content)

        # 处理重置命令
        if actual_content.lower() in RESET_COMMANDS:
            reset_user_session(phone)
            send_message_to_im(
                "已重置对话，开始新的对话。", group_id, phone, callback_url
            )
            return jsonify({"status": "success"})

        # 处理请求
        if use_reasoning:
            logger.info(f"用户 {phone} 启动思考模式，群组: {group_id}")
            gevent.spawn(
                process_reasoning_request,
                actual_content,
                phone,
                group_id,
                callback_url,
                client_ip,
            )
        else:
            process_normal_request(
                actual_content, phone, group_id, callback_url, client_ip
            )

        # 执行定期清理
        perform_periodic_cleanup()

        return jsonify({"status": "success"})

    except (BadRequest, Forbidden, TooManyRequests) as e:
        return jsonify({"status": "error", "message": str(e)}), e.code

    except Exception as e:
        logger.error(f"处理webhook请求时出错: {e}, IP: {client_ip}")
        return jsonify({"status": "error", "message": "内部服务器错误"}), 500


@app.route("/sessions", methods=["GET"])
@requires_auth
def list_sessions():
    """管理页面 - 显示会话信息和配置"""
    client_ip = get_client_ip()

    try:
        logger.info(
            f"访问管理页面 - IP: {client_ip}, 用户: {request.authorization.username}"
        )

        # 清理过期数据
        clean_expired_sessions()
        clean_expired_requests()

        # 准备会话信息
        sessions_info = {}
        current_time = time.time()

        for phone, session in user_sessions.items():
            sessions_info[phone] = {
                "message_count": len(session["messages"]),
                "last_active": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(session["last_active"])
                ),
                "active_duration": int(current_time - session["last_active"]),
                "has_active_request": phone in active_requests,
                "recent_messages": (
                    session["messages"][-6:] if session["messages"] else []
                ),
            }

        # 准备活跃请求信息
        active_req_info = {}
        for phone, info in active_requests.items():
            active_req_info[phone] = {
                "start_time": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(info["start_time"])
                ),
                "duration": int(current_time - info["start_time"]),
                "status": info["status"],
                "group_id": info.get("group_id", "未知"),
            }

        # 准备响应数据
        response_data = {
            "status": "success",
            "active_sessions": len(user_sessions),
            "active_requests": len(active_requests),
            "sessions": sessions_info,
            "requests": active_req_info,
            "group_configs": GROUP_CONFIGS,
            "default_config": DEFAULT_GROUP_CONFIG,
            "current_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 根据请求类型返回数据
        if request.headers.get("Accept") == "application/json":
            return jsonify(response_data)

        # 渲染HTML模板
        return render_template(
            "sessions.html",
            sessions_info=sessions_info,
            active_req_info=active_req_info,
            user_sessions_count=len(user_sessions),
            active_requests_count=len(active_requests),
            group_configs_count=len(GROUP_CONFIGS),
            GROUP_CONFIGS=GROUP_CONFIGS,
            DEFAULT_GROUP_CONFIG=DEFAULT_GROUP_CONFIG,
            current_time=response_data["current_time"],
        )

    except Exception as e:
        logger.error(f"获取管理页面信息时出错: {e}, IP: {client_ip}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/<path:invalid_path>", methods=["GET", "POST", "PUT", "DELETE"])
def invalid_endpoint(invalid_path):
    """处理无效端点"""
    client_ip = get_client_ip()
    logger.warning(
        f"尝试访问无效端点 - 路径: /{invalid_path}, 方法: {request.method}, IP: {client_ip}"
    )
    return jsonify({"status": "error", "message": "404 Not Found"}), 404


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"status": "error", "message": "Bad Request"}), 400


@app.errorhandler(403)
def forbidden(error):
    return jsonify({"status": "error", "message": "Forbidden"}), 403


@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Not Found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    client_ip = get_client_ip()
    logger.warning(
        f"方法不允许 - 路径: {request.path}, 方法: {request.method}, IP: {client_ip}"
    )
    return jsonify({"status": "error", "message": "Method Not Allowed"}), 405


@app.errorhandler(429)
def too_many_requests(error):
    return jsonify({"status": "error", "message": "Too Many Requests"}), 429


@app.errorhandler(500)
def internal_server_error(error):
    client_ip = get_client_ip()
    logger.error(f"内部服务器错误 - IP: {client_ip}, 错误: {error}")
    return jsonify({"status": "error", "message": "Internal Server Error"}), 500


@app.route("/favicon.svg")
def favicon():
    return app.send_static_file("favicon.svg")


@app.route("/favicon.ico")
def favicon_ico():
    return app.send_static_file("favicon.svg")


if __name__ == "__main__":
    logger.info("启动服务，监听端口: 1011")
    app.run(host="0.0.0.0", port=1011, debug=False)
