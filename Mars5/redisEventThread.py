import redis

redis_host = '192.168.1.101'
redis_port = 6379
rpass = ""
r = redis.Redis(host=redis_host, port=redis_port, password = rpass)

def event_handler(msg):
    print(msg, "event handler")
    thread.stop()

pubsub = r.pubsub()
pubsub.psubscribe(**{'__keyevent@0__:expired':event_handler})
thread=pubsub.run_in_thread(sleep_time=.001)