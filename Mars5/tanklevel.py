'''
Created on Feb. 9, 2021

@author: bjarm
'''

import redis
import rconfig as cfg #connection data for redis database

import time
import threading


#a dict is required for a stream (a stream comes with the datestamp in the id)
#**change rates to 0 after troubleshooting is finished
START_RATE = "100"
START_LEVEL = "50"
ASSEMBLY = {"CDRA","SRA","OGA","WPA"} 
TANK ={"H2O","CO2"} 
ERROR_STREAMS = {"CDRA-error", "SRA-error", "WPA-error", "OGA-error"}
PIPES = {"WPA-H2O-pot-out","WPA-H2O-in-LST","WPA-H2O-in-CDRA","WPA-H2O-in-SRA",
        "SRA-H2O-out","SRA-H2-in","SRA-CH4-out","SRA-N2-in", "SRA-CO2-in",
        "OGA-O2-out","OGA-H2-out","OGA-H2O-pot-in",
        "CDRA-H2O-out","CDRA-CO2-out"}

error_code = 0
RATE_CONSTANT = 3 #increase value to change level faster



def main():
    try:
        """From redis-py documentation:
        Redis client instances can safely be shared between threads. 
        Internally, connection instances are only retrieved from the connection pool during command execution, 
        and returned to the pool directly after. 
        """
        #Decode is set to true. if is is set here don't decode again elsewhere
        global r
        r = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                         password=cfg.redis_signin["password"], decode_responses=True)
        
    except Exception as e:
        print(e, "Trouble connecting to redis db")
        
    r.flushdb()
    
    #Determine which rates/levels will be reset
    for item in ASSEMBLY:
        key = item + '-rate'
        dict_rate = {key : START_RATE}
        reset_data(item,dict_rate) #eg (CDRA,{CDRA-rate:START_RATE})
            
    for item in TANK:
        key = item + '-level'
        dict_rate = {key : START_LEVEL}
        reset_data(item,dict_rate) #eg (CO2,{CO2-level:START_LEVEL})       
        
    for item in ERROR_STREAMS:
        reset_data(item,{item:error_code})
    

    for pipe in PIPES:
        r.hset("threshold",pipe,"10000")
    #use the following format to change default threshold value
    r.hset("threshold","CDRA-H2O-out","120000")   
         
    
    CO2thread = threading.Thread(target=control_level, )
    H2Othread = threading.Thread(target=, )
    
    control_level("CDRA","CDRA-error","SRA","SRA-error","CO2")
    
    #control_level("WPA","WPA-error","OGA","OGA-error","H2O")
    
    
def reset_data(stream_name, start_value):   
    r.xadd(stream_name,start_value)
    

def control_level(producer_stream,producer_error, consumer_stream, 
                  consumer_error, tank_stream):
    _, prev_producerrate = get_stream_info(producer_stream) #use _ for unused variable
    _, prev_consumerrate = get_stream_info(consumer_stream)
    scenario_running = True  
    ratechange_time = time.time()
    tank_stream_key = tank_stream + "-level"
    while scenario_running == True:
        _, tanklevel = get_stream_info(tank_stream) #db check to watch for overide from MarsControl
        _, producerrate = get_stream_info(producer_stream)
        _, consumerrate = get_stream_info(consumer_stream)
        if consumerrate != prev_consumerrate or producerrate != prev_producerrate:
            ratechange_time = time.time() #when the rates are equal the time is not updated, reset before using in level change calculations
            if tanklevel == 100 and producerrate == 0:
                r.xadd(producer_error,{producer_error:"0"})
                print("reset error to 0")
            if tanklevel == 0 and consumerrate == 0:
                r.xadd(consumer_error,{consumer_error:"0"})
                print("reset error to 0")
        if (consumerrate-producerrate) != 0: 
            if tanklevel == 100 and producerrate != 0:  #acccount for lag between tank reaching 100 and assembly shutting down
                r.xadd(producer_error,{producer_error:"113"})
                #print(r.xrevrange(producer_error,"+","-",1))
                print("producer error")
            elif tanklevel == 0 and consumerrate != 0:
                r.xadd(consumer_error,{consumer_error:"313"}) 
            else:
                deltatime = (time.time() - ratechange_time)
                print (deltatime, "time since last level update in seconds")
                levelincrease = (producerrate - consumerrate)*RATE_CONSTANT/1000*deltatime
                tanklevel = tanklevel + levelincrease
                if tanklevel > 100:
                    print("producer shutdown")
                    #Producer must shutdown as there is no more storage space
                    r.xadd(producer_error,{producer_error:"113"}) 
                    tanklevel = 100
                if tanklevel < 0:
                    #Consumer must shutdown as supply has run out
                    r.xadd(consumer_error,{consumer_error:"313"}) 
                    tanklevel = 0
                dict_tanklevel = {tank_stream_key : tanklevel}
                r.xadd(tank_stream,dict_tanklevel)
                print("tank level to stream", dict_tanklevel)
            
        prev_consumerrate=consumerrate
        prev_producerrate=producerrate
        #if scenario_running in db there could be a graceful stop
        time.sleep(2) 
        
    
        
def get_stream_info(equip_stream):
    #Finds the newest rate/level from the stream and the time it was recorded
    #Redis stream id's starts with time from Unix Epoch
    #value is stored as the value in a dictionary datatype
    raw_data = r.xrevrange(equip_stream,"+","-",1)
    #print(raw_data,"this is the raw format of the stream data")
    extract_id = ((raw_data[0])[0]) 
    endof_timestamp=extract_id.find("-")
    timestamp_offby3 = int(extract_id[0:(endof_timestamp)]) 
    timestamp = timestamp_offby3/1000 #decimal point is 3 digits from end of redis timestamp id
    dict_info = ((raw_data[0])[1])
    for (thevalue) in dict_info.values():  #A way to get values from key/values pairs in dict
        value = float(thevalue)
    return timestamp, value
    
if __name__ == '__main__':
    main()

