# chatbot
量子密信聊天机器人，需在根目录下配置相关文件才可使用：

必选项：.env文件

可选项：group_configs.json文件以及知识库文件夹，里面以文本文件的形式进行呈现（后期直接使用智能体了，知识库应该会删除）



.env文件里面需要设置三项参数：

```
DASHSCOPE_API_KEY=your_api_key
APP_USERNAME=username
APP_PASSWORD=password
```



group_configs.json为群组配置文件，格式为json格式：

```json
{
    "group_id1": {
        "use_knowledge_base": true,
        "knowledge_base_dir": "knowledge_base/customer_service",
        "model": "qwen-plus-latest",
        "reasoning_model": "qwen3-235b-a22b",
        "system_prompt": "你是客服助手，请简洁专业地回答问题。不要使用Markdown等格式（如*、**等符号）来展示强调文本，聊天软件不支持markdown等文本格式。"
    },
    "group_id2": {
        "use_knowledge_base": false,
        "model": "qwen-plus-latest",
        "reasoning_model": "qwen3-235b-a22b",
        "system_prompt": "你是聊天机器人，可以使用emoji表情或者颜文字符号等，但在对话过程中不要使用Markdown等格式（如*、**等符号）来展示强调文本，聊天软件不支持markdown等文本格式。"
    }
}
```

