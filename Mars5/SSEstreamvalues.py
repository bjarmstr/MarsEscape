#!/usr/bin/env python
import datetime
import flask
import redis
import rconfig as cfg #connection data for redis database


app = flask.Flask(__name__)
app.secret_key = 'asdf'


outread = 0

red = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                 password=cfg.redis_signin["password"], decode_responses=True)


@app.route('/stream')
def stream():  
    def event_stream():
        while True:
            new_stream_data = red.xread({'chat': '$', 'chat2':'$'}, block=0, count=10)
            yield 'data: %s\n\n' % new_stream_data   
    return flask.Response(event_stream(),
                          mimetype="text/event-stream")


@app.route('/')
def home():
    return flask.render_template('sse.html', title='real time updates')


if __name__ == '__main__':
    app.debug = True
    app.run()


