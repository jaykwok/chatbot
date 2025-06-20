# 在导入任何其他模块之前，立即执行猴子补丁！
import gevent.monkey

gevent.monkey.patch_all()

# 现在再安全地导入你的 Flask 应用
from app import app

# Gunicorn 会寻找这个 'application' 变量
application = app
