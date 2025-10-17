# chatbot
量子密信聊天机器人，需在根目录下配置相关文件才可使用：

必选项：.env文件

可选项：group_configs.json文件



.env文件里面需要设置三项参数：

```
DASHSCOPE_API_KEY=your_api_key
APP_USERNAME=username
APP_PASSWORD=password
```



group_configs.json为群组配置文件，格式为json格式：

```json
{
    "群组ID配置示例": {
        "model": "qwen-plus-latest",
        "reasoning_model": "qwen-plus-latest",
        "system_prompt": "你是客服助手，请简洁专业地回答问题。不要使用Markdown等格式（如*、**等符号）来展示强调文本，聊天软件不支持markdown等文本格式。"
    },
    "1940291788795777025": {
        "model": "deepseek-v3.2-exp",
        "reasoning_model": "deepseek-v3.2-exp",
        "system_prompt": "你是聊天机器人，可以使用emoji表情或者颜文字符号等，但在对话过程中不要使用Markdown等格式（如*、**等符号）来展示强调文本，聊天软件不支持markdown等文本格式。"
    }
}
```

