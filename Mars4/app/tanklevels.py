'''
Created on Feb. 9, 2021

@author: bjarm
'''
from app import redis_client

def tank(testingvar):
    together = testingvar + " functions from other modules"
    dbtestvar = redis_client.get('potato')
    print("we already know that potato returns", dbtestvar)
    return together
