'''
Created on Feb. 3, 2021

@author: Jean Armstrong


'''
from app import redis_client

def scenario_list(testingvar):
    together = testingvar + " functions from other modules"
    dbtestvar = redis_client.get('potato')
    print("we already know that potato returns", dbtestvar)
    return together



def isInteger(s):
    try: 
        int(s)
        return True
    except ValueError:
        print("not integer")
        return False
    