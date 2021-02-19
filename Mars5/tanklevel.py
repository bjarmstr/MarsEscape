'''
Created on Feb. 9, 2021

@author: bjarm
'''

import redis
import rconfig as cfg #connection data for redis database

import time



#a dict is required for a stream (a stream comes with the datestamp in the id)
#**change rates to 0 after troubleshooting is finished
START_RATE = {"rate" : "0"}
START_LEVEL = {"level" : "20"}
START_ECODE = {"error" : "0"}
ASSEMBLY = {"CDRA","SRA","OGA","WPA",} #tank required in tank equip names (to sort rate vs level)
TANK ={"H2Otank","CO2tank"}
ERROR_STREAMS = {"CDRA_error", "SRA_error", "WPA_error", "OGA_error"}

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
    
    #Determine which rates/levels will be reset
    for item in ASSEMBLY:
            start_value = START_RATE
            reset_data(item,start_value)
            reset_piping(item)
            
    for item in TANK:
            start_value= START_LEVEL
            reset_data(item,start_value)        
        
    for item in ERROR_STREAMS:
        start_value = START_ECODE
        reset_data(item,start_value)
    
    
        

    #**for testing need rates different**
    #reset_data("CDRA",{"rate":"100"})  
    reset_data("WPA",{"rate":"100"})  
    
    #control_level("CDRA","CDRA_error","SRA","SRA_error","CO2tank")
    
    control_level("WPA","WPA_error","OGA","OGA_error","H2Otank")
    
    
def reset_data(stream_name, start_value):   
    #Purge database of previous stream data and set starting rate/level
    #Can't use flush as database holds piping and other data
    r.xtrim(stream_name,0,False) 
    r.xadd(stream_name,start_value)
    
def reset_piping(equip_name):
    piping_name = equip_name + "_pipe"
    pipeDict = r.hgetall(piping_name) #find which pipes this equip has
    for key in pipeDict.keys():
        if ("threashold" not in key): #don't reset threshold values
            r.hset(piping_name,key,"False")
    

def control_level(producer_stream,producer_error, consumer_stream, 
                  consumer_error, tank_stream):
    prev_producertime, prev_producerrate = get_stream_info(producer_stream)
    prev_consumertime, prev_consumerrate = get_stream_info(consumer_stream)
    scenario_running = True  
    while scenario_running == True:
        ratechange_time, tanklevel = get_stream_info(tank_stream)
        if tanklevel > 100:
            #Producer must shutdown as there is no more storage space
            #****origonal code sent errors to both up and downstream*****
            r.xadd(producer_error,{"producerHighLevel":"113"}) 
        elif tanklevel < 0:
            #Consumer must shutdown as supply has run out
            r.xadd(consumer_error,{"consumerLowLevel":"313"}) 
        else:
            print("in the loop")
            producertime, producerrate = get_stream_info(producer_stream)
            consumertime, consumerrate = get_stream_info(consumer_stream)
            if consumerrate != prev_consumerrate or producerrate != prev_producerrate:
                ratechange_time = time.time() #when the rates are equal the time is not updated, reset before using in level change calculations
            if (consumerrate-producerrate) != 0: 
                deltatime = (time.time() - ratechange_time)
                print (deltatime, "time since last level update in seconds")
                levelincrease = (producerrate - consumerrate)*RATE_CONSTANT/1000*deltatime
                tanklevel = tanklevel + levelincrease
                print (tanklevel, "Co2level after change")
                dict_tanklevel = {"level" : tanklevel}
                r.xadd(tank_stream,dict_tanklevel)  
        prev_consumerrate=consumerrate
        prev_producerrate=producerrate
        #if scenario_running in db there could be a graceful stop
        time.sleep(3) #actual time between loops is ~2.1 seconds
        
    
        
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

