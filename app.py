import time
import threading
from flask import Flask, request, jsonify, render_template
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

# 设置日志
setup_logging()
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)


def process_reasoning_request(content, phone, group_id, callback_url):
    """后台处理思考模式请求"""
    try:
        # 更新请求状态
        active_requests[phone] = {
            "start_time": time.time(),
            "status": "processing",
            "group_id": group_id,
            "callback_url": callback_url,
        }

        # 获取群组配置
        group_config = GROUP_CONFIGS.get(group_id, DEFAULT_GROUP_CONFIG)

        # 根据群组配置决定是否加载知识库
        knowledge_base = None
        if group_config.get("use_knowledge_base", True):
            knowledge_base = load_knowledge_base(group_id)

        # 发送进度消息
        send_message_to_im(
            "正在思考中，这可能需要一些时间...", group_id, phone, callback_url
        )

        # 获取AI回复
        logger.info(f"后台处理用户 {phone} 的思考请求: '{content}'，群组: {group_id}")
        ai_response, is_new_session = get_ai_response(
            content, phone, group_id, knowledge_base, use_reasoning_model=True
        )

        # 发送最终回复
        send_message_to_im(ai_response, group_id, phone, callback_url)

        # 如果是新会话，发送操作指南
        if is_new_session:
            welcome_guide = (
                "欢迎使用AI助手！以下是基本操作说明：\n\n"
                "- 输入「重置」或「reset」: 清除对话历史，开始新对话\n"
                "- 输入「思考:问题内容」: 启用思考模式，显示AI的思考过程\n\n"
                "有任何问题，随时向我提问！"
            )
            send_message_to_im(welcome_guide, group_id, phone, callback_url)

        # 处理完成，移除跟踪
        if phone in active_requests:
            processing_time = time.time() - active_requests[phone]["start_time"]
            logger.info(
                f"思考请求完成，用户: {phone}, 群组: {group_id}, 处理时间: {processing_time:.2f}秒"
            )
            del active_requests[phone]

    except Exception as e:
        logger.error(f"后台处理思考请求时出错: {e}, 用户: {phone}, 群组: {group_id}")
        send_message_to_im(
            "抱歉，处理您的请求时出现了错误，请稍后再试。",
            group_id,
            phone,
            callback_url,
        )
        if phone in active_requests:
            del active_requests[phone]


@app.route("/webhook", methods=["POST"])
def webhook():
    """处理来自IM平台的webhook请求"""
    try:
        client_ip = get_client_ip()
        logger.info(
            f"\n收到请求 - 方法: {request.method}, 路径: {request.path}, IP: {client_ip}"
        )

        # 验证请求
        if not request.is_json:
            logger.warning(f"\n收到非JSON请求: {request.content_type}, IP: {client_ip}")
            return jsonify({"status": "error"}), 400

        data = request.json
        phone = data.get("phone", "Null")
        group_id = data.get("groupId", "Null")
        text_msg = data.get("textMsg", {})
        content = (
            text_msg.get("content", "").strip() if isinstance(text_msg, dict) else ""
        )
        callback_url = data.get("callBackUrl", "")

        logger.info(
            f"\n收到请求 - IP: {client_ip}, 用户: {phone}, 群组: {group_id}, 内容: {content}"
        )

        # 各种验证
        required_fields = ["type", "textMsg", "phone", "groupId", "callBackUrl"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.warning(
                f"\n请求缺少必要字段: {missing_fields}, IP: {client_ip}, 用户: {phone}"
            )
            return jsonify({"status": "error"}), 400

        if data.get("type") != "text":
            logger.warning(
                f"\n收到不支持的消息类型: {data.get('type')}, IP: {client_ip}, 用户: {phone}"
            )
            return jsonify({"status": "error"}), 400

        valid_domains = ["https://imtwo.zdxlz.com/", "https://im.zdxlz.com/"]
        if not any(callback_url.startswith(domain) for domain in valid_domains):
            logger.warning(
                f"\n检测到可疑的回调URL: {callback_url}, IP: {client_ip}, 用户: {phone}"
            )
            return jsonify({"status": "error"}), 403

        if not content:
            logger.warning(f"\n收到空内容消息，用户: {phone}, IP: {client_ip}")
            return jsonify({"status": "error"}), 400

        # 频率限制检查
        is_limited, time_diff = is_user_rate_limited(phone)
        if is_limited:
            logger.warning(
                f"\n用户 {phone} 请求频率过高: {time_diff:.3f}秒, IP: {client_ip}"
            )
            return jsonify({"status": "error"}), 429

        # 检查是否有正在处理的请求
        has_active, elapsed_time = has_active_request(phone)
        if has_active and elapsed_time < MAX_WAIT_TIME:
            send_message_to_im(
                f"您的上一个请求正在处理中，请稍候（已处理 {int(elapsed_time)} 秒）。如需取消，请输入'重置'。",
                group_id,
                phone,
                callback_url,
            )
            return jsonify({"status": "success"})

        # 检查思考模式
        use_reasoning_model = False
        processing_content = content
        if content.startswith("思考:") or content.startswith("思考："):
            use_reasoning_model = True
            processing_content = content[3:].strip()
            logger.info(f"用户 {phone} 启用思考模式，群组: {group_id}, IP: {client_ip}")

        # 检查重置命令
        if processing_content.lower() in ["重置", "reset", "新对话", "new chat"]:
            reset_user_session(phone)
            send_message_to_im(
                "已重置对话，开始新的对话。", group_id, phone, callback_url
            )
            return jsonify({"status": "success"})

        # 处理请求
        if use_reasoning_model:
            threading.Thread(
                target=process_reasoning_request,
                args=(processing_content, phone, group_id, callback_url),
            ).start()
            return jsonify({"status": "success"})
        else:
            group_config = GROUP_CONFIGS.get(group_id, DEFAULT_GROUP_CONFIG)
            knowledge_base = None
            if group_config.get("use_knowledge_base", True):
                knowledge_base = load_knowledge_base(group_id)

            ai_response, is_new_session = get_ai_response(
                processing_content, phone, group_id, knowledge_base, False
            )

            send_message_to_im(ai_response, group_id, phone, callback_url)

            if is_new_session:
                welcome_guide = (
                    "欢迎使用AI助手！以下是基本操作说明：\n\n"
                    "- 输入「重置」或「reset」: 清除对话历史，开始新对话\n"
                    "- 输入「思考:问题内容」: 启用思考模式，显示AI的思考过程\n\n"
                    "有任何问题，随时向我提问！"
                )
                send_message_to_im(welcome_guide, group_id, phone, callback_url)

        # 定期清理
        if len(user_sessions) > 100:
            cleaned_count = clean_expired_sessions()
            logger.info(f"清理了 {cleaned_count} 个过期会话")

        if len(active_requests) > 20:
            cleaned_count = clean_expired_requests()
            if cleaned_count > 0:
                logger.info(f"清理了 {cleaned_count} 个超时请求")

        if len(last_request_time) > 1000:
            current_time = time.time()
            expired_time = current_time - 600
            expired_phones = [
                p for p, t in last_request_time.items() if t < expired_time
            ]
            for p in expired_phones:
                del last_request_time[p]
            logger.info(f"清理了 {len(expired_phones)} 个过期的频率限制记录")

        return jsonify({"status": "success"})

    except Exception as e:
        try:
            client_ip = get_client_ip()
            data = request.json if request.is_json else {}
            phone = data.get("phone", "Null") if data else "Null"
            group_id = data.get("groupId", "Null") if data else "Null"
        except:
            client_ip = "Null"
            phone = "Null"
            group_id = "Null"

        logger.error(
            f"处理webhook请求时出错: {e}, IP: {client_ip}, 用户: {phone}, 群组: {group_id}"
        )
        return jsonify({"status": "error"}), 500


@app.route("/sessions", methods=["GET"])
@requires_auth
def list_sessions():
    """管理页面 - 显示会话信息和配置"""
    try:
        client_ip = get_client_ip()
        logger.info(
            f"访问管理页面 - IP: {client_ip}, 用户: {request.authorization.username}"
        )

        # 清理过期会话
        clean_expired_sessions()
        clean_expired_requests()

        # 准备会话信息
        sessions_info = {}
        for phone, session in user_sessions.items():
            sessions_info[phone] = {
                "message_count": len(session["messages"]),
                "last_active": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(session["last_active"])
                ),
                "active_duration": int(time.time() - session["last_active"]),
                "has_active_request": phone in active_requests,
                "recent_messages": (
                    session["messages"][-6:] if len(session["messages"]) > 0 else []
                ),  # 最近3轮对话
            }

        # 准备活跃请求信息
        active_req_info = {}
        for phone, info in active_requests.items():
            active_req_info[phone] = {
                "start_time": time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(info["start_time"])
                ),
                "duration": int(time.time() - info["start_time"]),
                "status": info["status"],
                "group_id": info.get("group_id", "未知"),
            }

        # 如果请求JSON数据
        if request.headers.get("Accept") == "application/json":
            return jsonify(
                {
                    "status": "success",
                    "active_sessions": len(user_sessions),
                    "active_requests": len(active_requests),
                    "sessions": sessions_info,
                    "requests": active_req_info,
                    "group_configs": GROUP_CONFIGS,
                    "default_config": DEFAULT_GROUP_CONFIG,
                }
            )

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
            current_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

    except Exception as e:
        client_ip = get_client_ip()
        logger.error(f"获取管理页面信息时出错: {e}, IP: {client_ip}")
        return jsonify({"status": "error", "message": str(e)})


@app.route("/<path:invalid_path>", methods=["GET", "POST", "PUT", "DELETE"])
def invalid_endpoint(invalid_path):
    client_ip = get_client_ip()
    logger.warning(
        f"\n尝试访问无效端点 - 路径: /{invalid_path}, 方法: {request.method}, IP: {client_ip}"
    )
    return jsonify({"status": "error", "message": "404 not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    client_ip = get_client_ip()
    logger.warning(
        f"\n方法不允许 - 路径: {request.path}, 方法: {request.method}, IP: {client_ip}"
    )
    return jsonify({"status": "error", "message": "Method not allowed"}), 405


@app.route("/favicon.svg")
def favicon():
    return app.send_static_file("favicon.svg")


@app.route("/favicon.ico")
def favicon_ico():
    return app.send_static_file("favicon.svg")


if __name__ == "__main__":
    logger.info("启动服务，监听端口: 1011")
    app.run(host="0.0.0.0", port=1011)
