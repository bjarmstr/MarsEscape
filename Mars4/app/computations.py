'''
Created on Feb. 3, 2021

@author: Jean Armstrong


'''
from app import redis_client
import time

def reset_threshold():
    pipes = {"WPA-H2O-pot-out","WPA-H2O-in-CO2","WPA-H2O-in-CDRA","WPA-H2O-in-SRA",
             "SRA-H2O-out","SRA-H2-in","SRA-CH4-out","SRA-N2-in",
             "OGA-O2-out","OGA-H2-out","OGA-H2O-pot-in",
             "CDRA-H2O-out","CDRA-CO2-out"}
    for pipe in pipes:
        redis_client.hset("threshold",pipe,"10000")
    pipe_thresh_dict = redis_client.hgetall("threshold") 
    print('threshold',pipe_thresh_dict)

def op_data_from_db(): 
    op_data ={}      
    equip_stream = ["CDRA", "WPA","OGA","SRA","CO2","H2O"]
    for equip in equip_stream:
        raw_data = redis_client.xrevrange(equip,"+","-",1)
        dict_info = ((raw_data[0])[1]) #locate key:value in stream
        for key,value in dict_info.items():  
            op_data[key] = value
    return op_data

def error_codes_from_db():
    error_codes ={}      
    error_stream = ["CDRA-error", "WPA-error","OGA-error","SRA-error"]
    for equip in error_stream:
        raw_data = redis_client.xrevrange(equip,"+","-",1)
        dict_info = ((raw_data[0])[1]) #locate key:value in stream
        for key,value in dict_info.items():  
            error_codes[key] = value
    return error_codes

def isInteger(s):
    try: 
        int(s)
        return True
    except ValueError:
        print("not integer")
        return False
    
def tester():
    time.sleep(10)  
    print("sleep10")  
    
    time.sleep(5)  
    print("sleep5") 
    time.sleep(15)  
    print("sleep15") 