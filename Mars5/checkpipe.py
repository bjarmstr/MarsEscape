#using resistive light photocell sensor and a 1 micro F capacitor
#lspin is the pin the photocell is connected to on the raspberrypi
import time
import board
from digitalio import DigitalInOut, Direction

def get_light(lspin,threshold):
    
    iterate = 1 #loop iterate times for an average to stabalize readings?
    #threshold = 10000 #resistance value - increase if reading pipe connected when pipe isn't connected  3000?
    reading = 0
    dark = False
    average = 0
    digitalpin = 'D' + str(lspin)
    pinfunc = getattr(board, digitalpin)
    #for i in range(6,iterate): 
    with DigitalInOut(pinfunc) as ls:  #light sensor pin
         # setup pin as output and direction low value
        ls.direction = Direction.OUTPUT
        ls.value = False
        time.sleep(0.1)
        # setup pin as input and wait for low value
        ls.direction = Direction.INPUT
        # This takes about 1 millisecond per loop cycle
        while dark is False:
            if ls.value == False:
                reading += 1
                if reading > threshold:
                    print("you are here",ls.value)
                    dark = True
            else:
                dark = True
            
    #average = reading/iterate
    average = reading
    if average > threshold:
        #good to go
        #return(1)
        return average/100, 1  #return a value to display for troubleshooting
    else:
        #not dark enough
        #return(0)
        return average/100, 0
        

