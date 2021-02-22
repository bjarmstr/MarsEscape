'''
Created on Jan. 31, 2021

@author: Jean Armstrong
'''
import os

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or "roots2stem"
    REDIS_URL = "redis://:roots2stemMarsEscapeRoom@192.168.1.101:6379/0"

    