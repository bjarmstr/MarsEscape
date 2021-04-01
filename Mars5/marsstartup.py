'''
Created on Mar. 27, 2021

@author: bjarm
'''

import threading
from time import sleep, time

MIN_TEMP = 25
PREHEAT_TEMP = 130
WPA_HOLD_TIME = 10 #20seconds
DEG_INC = 5 #5 degrees per increment
TIME_INC = .3  #1 second delay between increments
#(PREHEAT_TEMP-MIN_TEMP)/DEG_INC*TIME_INC = Wait time of preheat cycle
SRA_OGA_SYNC_TIME = 5

hold_start_time = 0
temp_cycle = "off"
preheating = True


user_str = ""
next_val = False
assemblies = {"OGA":{"rate":0,"start_time":time(), "error_code":0}, 
              "SRA":{"rate":0,"start_time":time(),"error_code":0, "N2":False}, 
              "WPA":{"rate":0,"start_time":time(), "error_code":0, "temp":MIN_TEMP}, 
              "CDRA":{"rate":0,"start_time":time(), "error_code":0}}

temp_cycle = "off"   #values: off, preheat or cooling


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
        #tank_conditions()
        print_status()
        next_val = False
        sleep(.3)


def set_status():
    global user_str,next_val, temp_cycle
    if (next_val == True):
        for assembly in assemblies:
            if assembly in user_str:
                if (assemblies[assembly]["rate"] == 0):
                    assemblies[assembly]["error_code"] = pre_conditions(assembly) 
                    if (assembly =="WPA"):  #WPA needs a preheat before starting
                        if temp_cycle == "off":
                            temp_cycle = "start_preheat"
                        elif temp_cycle == "cooling":
                            temp_cycle = "start_preheat"
                    
                    if (assemblies[assembly]["error_code"] == 0):  
                        assemblies[assembly]["start_time"] = time()
                        assemblies[assembly]["rate"] = 100  
                    
        if "N2" in user_str:  #SRA needs N2 purge before starting
            if (assemblies["SRA"]["error_code"] == 308):
                assemblies["SRA"]["error_code"] = 0
            print(assemblies["SRA"]["N2"],"purge")
            if (assemblies["SRA"]["rate"] == 0):
                assemblies["SRA"]["N2"]= True
            else: print("SRA lines can't be purged while it is running")

            
        
def print_status():
    global next_val
    if (next_val == True):
        for assembly in assemblies:
            print(assembly, "rate", assemblies[assembly]["rate"],"%",assemblies[assembly]["error_code"],"Error")
        print("N2",assemblies["SRA"]["N2"])
        if (assemblies["WPA"]["error_code"] == 101):
            print("WPA Preheating Temp Required: 130 C, Actual: ", assemblies["WPA"]["temp"], "C")
        if (assemblies["WPA"]["rate"] == 0) & (temp_cycle == "holding") :
            print("WPA preheated, ready for start-up")
        if (assemblies["SRA"]["error_code"] == 308):
            print("N2 purge required before SRA start-up")
    next_val = False

def pre_conditions(assembly):
    global temp_cycle
    if (assembly == "WPA") & (assemblies["WPA"]["rate"] == 0):
        if (temp_cycle != "holding"):
            assemblies[assembly]["error_code"]  = 101
        else: assemblies[assembly]["error_code"]  = 0
    elif (assembly == "SRA") & (assemblies["SRA"]["rate"] == 0):
        if (assemblies["SRA"]["N2"]==False):
            assemblies[assembly]["error_code"]  = 308
    else: assemblies[assembly]["error_code"]  = 0  #no error codes - allow startup
            
    return assemblies[assembly]["error_code"]     

def wpa_temp_status():
    global temp_cycle, hold_start_time, preheating
    while preheating:
        if temp_cycle == "start_preheat":
            temp_cycle = "preheat"
            wpa_preheat()   
        elif temp_cycle == "start_holding":
            hold_start_time = time()
            assemblies["WPA"]["error_code"]=0
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
    while temp_cycle == "preheat":
        while (assemblies["WPA"]["temp"] < PREHEAT_TEMP):
            assemblies["WPA"]["temp"] += DEG_INC
            sleep(1)
        temp_cycle = "start_holding"
    return

       
def wpa_cooling():
    global temp_cycle
    temp_cycle = "cooling"
    #print("cooling")
    while temp_cycle== "cooling":  
        assemblies["WPA"]["temp"] -= DEG_INC
        if (assemblies["WPA"]["temp"] <= MIN_TEMP):
            temp_cycle = "off"
        sleep(1)
    
    return
        
        
    
    
    
wpa_temp_status_thread = threading.Thread(target=wpa_temp_status, daemon=True)
wpa_temp_status_thread.start()
    
user_thread = threading.Thread(target=user_input, daemon=True)
user_thread.start()
startup()
