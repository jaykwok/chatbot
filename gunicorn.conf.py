# --- 服务器Socket配置 ---
# 绑定到所有网络接口的1011端口
bind = "0.0.0.0:1011"
# 等待连接的队列大小
backlog = 2048

# --- 工作进程 ---
# 使用 gevent 协程 worker，非常适合IO密集型应用
worker_class = "gevent"
# 对于AI这种可能长耗时的IO，worker数量设为1，利用gevent的并发能力，可以简化状态管理（如session_manager）
# 如果CPU核心数多且确认状态管理是线程/进程安全的，可以适当增加
workers = 1
# 每个 worker 能处理的最大并发连接数
worker_connections = 1000
# AI请求可能较慢，设置一个合理的超时时间，例如90秒
timeout = 90
# HTTP keep-alive 的超时时间
keepalive = 5

# --- 进程管理 ---
# 预加载应用代码，可以加快 worker 的启动速度
preload_app = True
# 进程名，方便在 `ps` 或 `top` 中识别
proc_name = "chatbot"
# 切换到非 root 用户运行，增强安全性 (UID/GID 在 Dockerfile 中创建)
user = "appuser"
group = "appgroup"
# worker 进程的临时文件目录，使用内存可以提高性能
worker_tmp_dir = "/dev/shm"

# --- 日志 ---
# 日志级别
loglevel = "info"
# 将访问日志和错误日志都输出到标准输出/错误，方便 Docker logs 查看
accesslog = "-"
errorlog = "-"
# 访问日志格式
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# --- 自动重启 ---
# 每个 worker 处理这么多请求后自动重启，有助于释放内存，防止内存泄漏
max_requests = 1000
max_requests_jitter = 50
