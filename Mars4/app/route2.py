'''

Created on Jan. 29, 2021

@author: Jean Armstrong
'''
from app import app
from flask import render_template, request, flash
from app import redis_client



@app.route('/redisbox')
def redisbox():
    myvar = redis_client.get('potato')
    print(myvar)
    return render_template('redisbox.html', title='Redisbox', myvar=myvar)

@app.route('/')
def index():
    return 'Hello, World!'

@app.route('/lost')
def lost():
    return render_template('lost.html')