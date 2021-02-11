#!/usr/bin/env python
import datetime
import flask
import redis
import rconfig as cfg #connection data for redis database

app = flask.Flask(__name__)
app.secret_key = 'asdf'


outread = 0

red = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                 password=cfg.redis_signin["password"])
        


def event_stream():
    pubsub = red.pubsub()
    pubsub.subscribe('chat')
    # TODO: handle client disconnection.
    for message in pubsub.listen():
        print (message)
        if message['type']=='message':
            yield 'data: %s\n\n' % message['data'].decode('utf-8') 
            #don't decode here and in redis connection as well
            
@app.route('/hello')
def hello():
    print('hello to the console')
    return flask.render_template('hello.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask.request.method == 'POST':
        flask.session['user'] = flask.request.form['user']
        return flask.redirect('/')
    return '<form action="" method="post">user: <input name="user">'


@app.route('/post', methods=['POST'])
def post():
    message = flask.request.form['message']
    user = flask.session.get('user', 'anonymous')
    now = datetime.datetime.now().replace(microsecond=0).time()
    red.publish('chat', u'[%s] %s: %s' % (now.isoformat(), user, message))
    return flask.Response(status=204)


@app.route('/stream')
def stream():  
    print('hello from the stream route')
    return flask.Response(event_stream(),
                          mimetype="text/event-stream")


@app.route('/')
def home():
    if 'user' not in flask.session:
        return flask.redirect('/login')
    return """
        <!doctype html>
        <title>chat</title>
        <script src="http://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js"></script>
        <style>body { max-width: 500px; margin: auto; padding: 1em; background: black; color: #fff; font: 16px/1.6 menlo, monospace; }</style>
        <p><b>hi, %s!</b></p>
        <p>Message: <input id="in" /></p>
        <pre id="out"></pre>
        <script>
            function sse() {
                var source = new EventSource('/stream');
                var out = document.getElementById('out');
                source.onmessage = function(e) {
                    // XSS in chat prevented by using textContent instead of innerHTML
                    out.textContent= e.data + '\\n' + out.textContent;
                };
            }
            $('#in').keyup(function(e){
                if (e.keyCode == 13) {
                    $.post('/post', {'message': $(this).val()});
                    $(this).val('');
                }
            });
            sse();
        </script>
    """ % flask.session['user']


if __name__ == '__main__':
    app.debug = True
    app.run()

