# 在导入任何其他模块之前，立即执行猴子补丁！
import gevent.monkey

gevent.monkey.patch_all()
from app import app

application = app
