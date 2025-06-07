import requests
import logging

logger = logging.getLogger(__name__)


def send_message_to_im(content, group_id, phone, callback_url):
    """发送消息回IM平台"""
    try:
        payload = {
            "type": "text",
            "textMsg": {
                "content": content,
                "isMentioned": True,
                "mentionType": 2,
                "mentionedMobileList": [phone],
                "groupId": group_id,
            },
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(callback_url, headers=headers, json=payload)

        if response.status_code == 200:
            logger.info(f"消息成功发送到IM平台，响应: {response.text}")
            return True
        else:
            logger.error(
                f"发送消息到IM平台失败，状态码: {response.status_code}, 响应: {response.text}"
            )
            return False

    except Exception as e:
        logger.error(f"发送消息到IM平台时出错: {e}")
        return False
