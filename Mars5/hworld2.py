import flask
import redis

app = flask.Flask(__name__)
app.secret_key = 'asdf'
red = redis.StrictRedis()

redis_host = #look in rconfig file for required connection information
redis_port = 6379
redis_password = 
outread = 0

r = redis.Redis(host=redis_host, port=6379, password=redis_password, decode_responses=True)



   
r.publish('hello','testfeb8')
r.publish('hello','test2')
r.publish('hello','test3')
r.publish('hello','againfeb8')


@app.route('/')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.debug = True
    app.run()