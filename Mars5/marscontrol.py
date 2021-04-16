'''
Created on Mar. 27, 2021

@author: bjarm
'''

import redis
import rconfig as cfg #connection data for redis database

import threading
from time import sleep, time

MIN_TEMP = 25
PREHEAT_TEMP = 130
WPA_HOLD_TIME = 10 #20seconds
DEG_INC = 5 #5 degrees per increment
TIME_INC = .1  #1 second delay between increments
#(PREHEAT_TEMP-MIN_TEMP)/DEG_INC*TIME_INC = Wait time of preheat cycle
SRA_OGA_SYNC_TIME = 4 #seconds


sync_start = 0

hold_start_time = 0
temp_cycle = "off"
preheating = True


user_str = ""
next_val = False


temp_cycle = "off"   #values: off, preheat or cooling


assemblies = {"CDRA","SRA","OGA","WPA"}


def main():
    wpa_temp_status_thread = threading.Thread(target=wpa_temp_status, daemon=True)
    wpa_temp_status_thread.start()
    
    user_thread = threading.Thread(target=user_input, daemon=True)
    user_thread.start()
    xadd_redis("SRA","error",0)
    xadd_redis("OGA","error",0)
    xadd_redis("WPA","error",0)
    xadd_redis("CDRA","error",0)
    xadd_redis("SRA","purge",0)
    xadd_redis("WPA","preheat",MIN_TEMP)
    xadd_redis("SRA","rate",0)
    xadd_redis("OGA","rate",0)
    xadd_redis("WPA","rate",0)
    xadd_redis("CDRA","rate",0)
    startup()




def user_input():
    global user_str, next_val
    while True:
        if (next_val == False):
            print("Enter the Assembly Name to Start the Box?  Options: CDRA, OGA, SRA or WPA")
            print("Enter N2 to purge the SRA unit")
            user_str = input()
            next_val = True
        sleep(.3)
        

def startup():
    global next_val
    while True:
        set_status()
        sra_oga_dependency()
        #wpa_temp_status() is running in a separate thread
        #tank_conditions()
        print_status()
        next_val = False
        sleep(.3)


def set_status():
    global user_str,next_val, temp_cycle, sync_start
    if (next_val == True):
        for assembly in assemblies:
            if assembly in user_str: #if we try to start this box
                if (get_redis(assembly) == 0):  #make sure it is not already started
                    err_code = pre_conditions(assembly)
                    xadd_redis(assembly,"error", err_code)
                    if (assembly =="WPA"):  #WPA needs a preheat before starting
                        if temp_cycle == "off":
                            temp_cycle = "start_preheat"
                        elif temp_cycle == "cooling":
                            temp_cycle = "start_preheat" 
                    if (err_code == 0):
                        #start-up unit
                        if assembly == "SRA":
                            SRA_start = time()
                            sync_start = time()
                            print("sync_start SRA", sync_start)
                        if assembly == "OGA":
                            OGA_start = time()  
                            sync_start = time()
                            print("start timer - OGA")
                        xadd_redis(assembly,"rate", 100)
                    
        if "N2" in user_str:  #SRA needs N2 purge before starting
            err_code = get_redis("SRA-error")
            if err_code == 308:
                xadd_redis("SRA","error", 0)
            print(get_redis("SRA-purge"))
            if get_redis("SRA") == 0:
                xadd_redis("SRA","purge", 1)
            else: print("SRA lines can't be purged while it is running")

            
        
def print_status():
    global next_val
    if (next_val == True):
        completed = True
        for assembly in assemblies:
            print(assembly, "rate", get_redis(assembly),"%",get_redis(assembly+"-error"),"Error")
            if get_redis(assembly) == 0:
                completed = False
        if completed == True:
            print("CONGRATULATIONS!  You are now making oxygen")
        print("N2",get_redis("SRA-purge"))  #light led to indicate this
        if (get_redis("WPA-error") == 101):
            print("WPA Preheating Temp Required: 130 C, Actual: ", get_redis("WPA-preheat"), "C")
        if (get_redis("WPA") == 0) and (temp_cycle == "holding") :
            print("WPA preheated, ready for start-up")
        if (get_redis("SRA-error") == 308):
            print("N2 purge required before SRA start-up")
        if (get_redis("SRA-error") == 534) or (get_redis("OGA-error") == 543):
            print("OGA/SRA must be started within ",SRA_OGA_SYNC_TIME," seconds of each other" )
            print("H2 gas needs to be safely consumed after creation")
            xadd_redis("OGA","error",0)
            xadd_redis("SRA","error",0)
        if get_redis("SRA-error") == 313:
            print("No CO2 available for startup")
            xadd_redis("SRA","error",0)
            
        if get_redis("OGA-error") == 414:
            print("No potable water available for startup")
            xadd_redis("OGA","error",0)
        
    next_val = False


def pre_conditions(assembly):
    global temp_cycle
    if (assembly == "WPA") and (get_redis("WPA") == 0):
        if (temp_cycle != "holding"):
            xadd_redis(assembly,"error", 101)
        else: xadd_redis(assembly,"error", 0)
    elif (assembly == "SRA") and (get_redis("SRA") == 0):  
        if (get_redis("SRA-purge")== 0):
            xadd_redis(assembly,"error", 308)  
        elif (get_redis("CDRA") == 0):
            ##build for level changes
            xadd_redis(assembly,"error", 313)
    elif (assembly == "OGA") and (get_redis("WPA") == 0):
        ##build for level changes
        xadd_redis(assembly,"error", 414)
    else: xadd_redis(assembly,"error", 0)           
    err_code = get_redis(assembly+"-error")
    return err_code   

def sra_oga_dependency():
    global sync_start
    if (get_redis("SRA")>0) and (get_redis("OGA")==0):
        if (time()-sync_start) > SRA_OGA_SYNC_TIME:
            
            print("sra/oga", time(), sync_start, time()-sync_start)
            xadd_redis("SRA","rate", 0)
            xadd_redis("SRA","purge", 0)
            xadd_redis("SRA","error", 534)
    if (get_redis("OGA")>0) and (get_redis("SRA")==0):
        if (time()-sync_start) > SRA_OGA_SYNC_TIME:
            xadd_redis("OGA","rate", 0) 
            xadd_redis("OGA","error", 543)

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

def xadd_redis(assembly,stream_type,value):
    stream = assembly + "-" + stream_type
    if stream_type == "rate":
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

    
