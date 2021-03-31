#!/usr/bin/env python
import datetime
import flask
import redis
import rconfig as cfg #connection data for redis database

app = flask.Flask(__name__)
app.secret_key = 'asdf'


outread = 0

red = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                 password=cfg.redis_signin["password"],decode_responses=True)
        


@app.route('/hello')
def hello():
    dict_value = {}
    error_code = {}
    pipes = {"WPA-H2O-pot-out","WPA-H2O-in-CO2","WPA-H2O-in-CDRA","WPA-H2O-in-SRA",
             "SRA-H2O-out","SRA-H2-in","SRA-CH4-out","SRA-N2-in",
             "OGA-O2-out","OGA-H2-out","OGA-H2O-pot-in",
             "CDRA-H2O-out","CDRA-CO2-out"}
    #this will override the present redis dictionary threshold values
    #for pipe in pipes:
        #red.hset("threshold",pipe,"10000")
    #pipe_thresh_dict = red.hgetall("threshold") 
    #print('threshold',pipe_thresh_dict)
    
    error_stream = ["CDRA-error", "WPA-error","OGA-error","SRA-error","CO2-error","H2O-error"]
    for stream in error_stream:
        red.xadd(stream, {stream:"0"}) 

    for equip in error_stream:
        raw_data = red.xrevrange(equip,"+","-",1)
        dict_info = ((raw_data[0])[1]) #locate key:value in stream
        for key,value in dict_info.items():  
            error_code[key] = value
    print(error_code,"error-code dictionary for all error-streams")
    
   

   
    
    return flask.render_template('hello.html')


if __name__ == '__main__':
    app.debug = True
    app.run()

