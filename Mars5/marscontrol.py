'''
Created on Mar. 27, 2021

@author: bjarm
'''

import redis
import rconfig as cfg #connection data for redis database

import threading
from time import sleep, time


#a dict is required for a stream (a stream comes with the datestamp in the id)


ASSEMBLIES = {"CDRA","SRA","OGA","WPA"} 

PIPES = {"WPA-H2O-pot-out","WPA-H2O-in-LST","WPA-H2O-in-CDRA","WPA-H2O-in-SRA",
        "SRA-H2O-out","SRA-H2-in","SRA-CH4-out","SRA-N2-in", "SRA-CO2-in",
        "OGA-O2-out","OGA-H2-out","OGA-H2O-pot-in",
        "CDRA-H2O-out","CDRA-CO2-out"}

RATE_CONSTANT = 3 #increase value to change level faster



MIN_TEMP = 25
PREHEAT_TEMP = 130
WPA_HOLD_TIME = 15 #seconds
DEG_INC = 5 #5 degrees per increment
TIME_INC = .1  #1 second delay between increments
#(PREHEAT_TEMP-MIN_TEMP)/DEG_INC*TIME_INC = Wait time of preheat cycle
SRA_OGA_SYNC_TIME = 5 #seconds

ERR = {"CO2_high_level": 113, "WPA_preheat": 201, "H2O_high_level":214, "SRA_purge": 308, "CO2_low_level":313,
       "H2O_low_level":414, "OGA_not_ready":534, "SRA_not_ready":543}


sync_start = 0

hold_start_time = 0
temp_cycle = "off"   #values: off, preheat or cooling
preheating = True


user_str = ""
next_val = False

prev_rate = { "CDRA" : 0 ,"OGA" : 0 , "SRA" : 0 , "WPA" : 0 }




def main():

    r.flushdb()
    
    for assembly in ASSEMBLIES:
        xadd_redis(assembly,"rate",0)
        xadd_redis(assembly,"error",0)
    
    xadd_redis("SRA","purge",0)
    xadd_redis("WPA","preheat",MIN_TEMP)
    xadd_redis("CO2", "level",0)
    xadd_redis("H2O", "level", 0)

    for pipe in PIPES:
        r.hset("threshold",pipe,"10000")
    #use the following format to change default threshold value
    r.hset("threshold","CDRA-H2O-out","120000")
    r.hset("threshold","SRA-H2O-out","120000")
    r.hset("threshold","SRA-H2-in","120000")
    r.hset("threshold","SRA-N2-in","120000")
    r.hset("threshold","SRA-CH4-out","140000")
         
    
    CO2thread = threading.Thread(target=control_level_CO2, args=("CDRA","CDRA-error","SRA","SRA-error","CO2"), daemon= True)
    H2Othread = threading.Thread(target=control_level_H2O, args=("WPA","WPA-error","OGA","OGA-error","H2O"), daemon= True)
    CO2thread.start()
    H2Othread.start()
    
    wpa_temp_status_thread = threading.Thread(target=wpa_temp_status, daemon=True)
    wpa_temp_status_thread.start()
    
    startup()


def startup():
    while True:
        set_status()
        #wpa_temp_status() is running in a separate thread
        #tank_conditions() running in separate thread
        sleep(.3)


def set_status():
    global temp_cycle, sync_start, prev_rate
    for assembly in ASSEMBLIES:
        new_rate = get_redis(assembly)
        if assembly == "SRA": SRA_rate  = new_rate
        if assembly == "OGA": OGA_rate  = new_rate
        if prev_rate[assembly] == 0 and new_rate != 0: #if we try to start this box
            xadd_redis(assembly,"rate", 0) #set rate back to zero while determining if conditions are met
            if assembly == "SRA": SRA_rate  = 0
            if assembly == "OGA": OGA_rate  = 0
            
            err_code = pre_conditions(assembly)
            xadd_redis(assembly,"error", err_code)
            if (assembly =="WPA"):  #WPA needs a preheat before starting
                print("wpa")
                if temp_cycle == "off":
                    temp_cycle = "start_preheat"
                elif temp_cycle == "cooling":
                    temp_cycle = "start_preheat" 
            if (err_code == 0):
                #start-up unit
                print(assembly, " starting up")
                if assembly == "SRA":
                    sync_start = time()
                    print("sra starting sync timing")
                if assembly == "OGA": 
                    sync_start = time()
                    print("oga starting sync timing")
                  #no change
                xadd_redis(assembly,"rate", new_rate)
            else:
                print(assembly,"failed conditions for rate change")
                  #failed conditions for rate change  -- can remove this after troubleshooting
        prev_rate[assembly] = new_rate                    
    #oga/sra dependency
    if (SRA_rate > 0) and (OGA_rate == 0):
        if (time()-sync_start) > SRA_OGA_SYNC_TIME: 
            print("sra/oga", time(), sync_start, time()-sync_start, prev_rate["SRA"])
            xadd_redis("SRA","rate", 0)
            xadd_redis("SRA","purge", 0)
            xadd_redis("SRA","error", ERR["OGA_not_ready"])
    if OGA_rate > 0  and SRA_rate == 0:
        if (time()-sync_start) > SRA_OGA_SYNC_TIME:
            xadd_redis("OGA","rate", 0) 
            xadd_redis("OGA","error", ERR["SRA_not_ready"])
        

def pre_conditions(assembly):
    global temp_cycle
    if (assembly == "WPA") and (get_redis("WPA") == 0):
        if (temp_cycle != "holding"):
            xadd_redis(assembly,"error", ERR["WPA_preheat"])
        else: xadd_redis(assembly,"error", 0)
    elif (assembly == "SRA"):  
        if (get_redis("SRA-purge")== 0):
            xadd_redis(assembly,"error", ERR["SRA_purge"])  
    else: xadd_redis(assembly,"error", 0)           
    err_code = get_redis(assembly+"-error")
    return err_code   

def sra_oga_dependency():
    global sync_start
    if (get_redis("SRA")>0) and (get_redis("OGA")==0):
        if (time()-sync_start) > SRA_OGA_SYNC_TIME:
            
            print("sra/oga", time(), sync_start, time()-sync_start, prev_rate["SRA"])
            xadd_redis("SRA","rate", 0)
            xadd_redis("SRA","purge", 0)
            xadd_redis("SRA","error", ERR["OGA_not_ready"])
    if (get_redis("OGA")>0) and (get_redis("SRA")==0):
        if (time()-sync_start) > SRA_OGA_SYNC_TIME:
            xadd_redis("OGA","rate", 0) 
            xadd_redis("OGA","error", ERR["SRA_not_ready"])

def wpa_temp_status():
    global temp_cycle, hold_start_time, preheating
    while preheating:
        if temp_cycle == "start_preheat":
            temp_cycle = "preheat"
            wpa_preheat()   
        elif temp_cycle == "start_holding":
            hold_start_time = time()
            xadd_redis("WPA","error", 0)
            temp_cycle = "holding"
        elif temp_cycle == "holding":
            elapsed_time = time() - hold_start_time
            if elapsed_time > WPA_HOLD_TIME:
                temp_cycle = "cooling"
                wpa_cooling()
        elif temp_cycle == "off":
            sleep(.3)
    

def wpa_preheat():
    global temp_cycle
    temperature = get_redis("WPA-preheat")
    while temp_cycle == "preheat":
        while temperature < PREHEAT_TEMP:
            temperature += DEG_INC
            xadd_redis("WPA","preheat", temperature)
            sleep(1)
        temp_cycle = "start_holding"
    return

       
def wpa_cooling():
    global temp_cycle
    temp_cycle = "cooling"
    temperature = get_redis("WPA-preheat")
    while temp_cycle== "cooling":  
        temperature -= DEG_INC
        xadd_redis("WPA","preheat", temperature)
        if (temperature <= MIN_TEMP):
            temp_cycle = "off"
        sleep(1)   
    return

def control_level_CO2(producer_stream,producer_error, consumer_stream, 
                  consumer_error, tank_stream):
    _, prev_producerrate = get_stream_CO2(producer_stream) #use _ for unused variable
    _, prev_consumerrate = get_stream_CO2(consumer_stream)
    scenario_running = True  
    ratechange_time = time()
    tank_stream_key = tank_stream + "-level"
    while scenario_running == True:
        _, tanklevel = get_stream_CO2(tank_stream) #db check to watch for overide from MarsControl
        _, producerrate = get_stream_CO2(producer_stream)
        _, consumerrate = get_stream_CO2(consumer_stream)
        if consumerrate != prev_consumerrate or producerrate != prev_producerrate:
            ratechange_time = time() #when the rates are equal the time is not updated, reset before using in level change calculations
            if tanklevel == 100 and producerrate == 0:
                r.xadd(producer_error,{producer_error:"0"})
                print("reset error to 0")
            if tanklevel == 0 and consumerrate == 0:
                r.xadd(consumer_error,{consumer_error:"0"})
                print("reset error to 0")
        if (consumerrate-producerrate) != 0: 
            if tanklevel == 100 and producerrate != 0:  #acccount for lag between tank reaching 100 and assembly shutting down
                r.xadd(producer_error,{producer_error: ERR["CO2_high_level"]})
                #print(r.xrevrange(producer_error,"+","-",1))
                print("producer error")
            elif tanklevel == 0 and consumerrate != 0:
                r.xadd(consumer_error,{consumer_error: ERR["CO2_low_level"]}) 
            else:
                deltatime = (time() - ratechange_time)
               #print (deltatime, "time since last level update in seconds")
                levelincrease = (producerrate - consumerrate)*RATE_CONSTANT/1000*deltatime
                tanklevel = tanklevel + levelincrease
                if tanklevel > 100:
                    print("producer shutdown")
                    #Producer must shutdown as there is no more storage space
                    r.xadd(producer_error,{producer_error: ERR["CO2_high_level"]})
                    tanklevel = 100
                if tanklevel < 0:
                    #Consumer must shutdown as supply has run out
                    r.xadd(consumer_error,{consumer_error: ERR["CO2_low_level"]}) 
                    tanklevel = 0
                dict_tanklevel = {tank_stream_key : tanklevel}
                r.xadd(tank_stream,dict_tanklevel)
                #print("tank level to stream", dict_tanklevel)
            
        prev_consumerrate=consumerrate
        prev_producerrate=producerrate
        #if scenario_running in db there could be a graceful stop
        sleep(2) 


def control_level_H2O(producer_stream,producer_error, consumer_stream, 
                  consumer_error, tank_stream):
    _, prev_producerrate = get_stream_H2O(producer_stream) #use _ for unused variable
    _, prev_consumerrate = get_stream_H2O(consumer_stream)
    scenario_running = True  
    ratechange_time = time()
    tank_stream_key = tank_stream + "-level"
    while scenario_running == True:
        _, tanklevel = get_stream_H2O(tank_stream) #db check to watch for overide from MarsControl
        _, producerrate = get_stream_H2O(producer_stream)
        _, consumerrate = get_stream_H2O(consumer_stream)
        if consumerrate != prev_consumerrate or producerrate != prev_producerrate:
            #print("H2O rates not equal")
            ratechange_time = time() #when the rates are equal the time is not updated, reset before using in level change calculations
            if tanklevel == 100 and producerrate == 0:
                r.xadd(producer_error,{producer_error:"0"})
                print("reset error to 0")
            if tanklevel == 0 and consumerrate == 0:
                r.xadd(consumer_error,{consumer_error:"0"})
                print("reset error to 0")
        if (consumerrate-producerrate) != 0: 
            if tanklevel == 100 and producerrate != 0:  #acccount for lag between tank reaching 100 and assembly shutting down
                r.xadd(producer_error,{producer_error: ERR["H2O_high_level"]})
                #print(r.xrevrange(producer_error,"+","-",1))
                print("producer error")
            elif tanklevel == 0 and consumerrate != 0:
                r.xadd(consumer_error,{consumer_error:ERR["H2O_low_level"]})
                print("consumer error H2O 414 low level")
            else:
                deltatime = (time() - ratechange_time)
                #print (deltatime, "time since last level update in seconds")
                levelincrease = (producerrate - consumerrate)*RATE_CONSTANT/1000*deltatime
                tanklevel = tanklevel + levelincrease
                if tanklevel > 100:
                    print("producer shutdown")
                    #Producer must shutdown as there is no more storage space
                    r.xadd(producer_error,{producer_error: ERR["H2O_high_level"]}) 
                    tanklevel = 100
                if tanklevel < 0:
                    print("consumer shutdown")
                    #Consumer must shutdown as supply has run out
                    r.xadd(consumer_error,{consumer_error: ERR["H2O_low_level"]}) 
                    tanklevel = 0
                dict_tanklevel = {tank_stream_key : tanklevel}
                r.xadd(tank_stream,dict_tanklevel)
                #print("tank level to stream", dict_tanklevel)
            
        prev_consumerrate=consumerrate
        prev_producerrate=producerrate
        #if scenario_running in db there could be a graceful stop
        sleep(2) 
        
def get_stream_CO2(equip_stream):
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
        
def get_stream_H2O(equip_stream):
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


def xadd_redis(assembly,stream_type,value):
    stream = assembly + "-" + stream_type
    if stream_type == "rate" or stream_type == "level":
        r.xadd((assembly),{stream:value})
    else:
        r.xadd((stream),{stream:value})

def get_redis(equip_stream):
    #Finds the newest rate/level from the stream
    raw_data = r.xrevrange(equip_stream,"+","-",1)
    dict_info = ((raw_data[0])[1])
    for (thevalue) in dict_info.values():  #A way to get values from key/values pairs in dict
        value = int(thevalue) 
    return value  
        
        
if __name__ == '__main__':
    
    try:
        r = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                         password=cfg.redis_signin["password"], decode_responses=True)
        print("redis connected")
        
    except Exception as e:
        print(e, "Trouble connecting to redis db")

    try:
        main()
    except KeyboardInterrupt:
        print ("interrupt - ending")

    
