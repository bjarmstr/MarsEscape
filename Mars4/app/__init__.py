'''
Created on Jan. 29, 2021

@author: bjarm
'''
from flask import Flask
from flask_redis import FlaskRedis
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
redis_client = FlaskRedis(app, decode_responses=True)

#this must stay at the bottom or circular import troubles arise
from app import routes