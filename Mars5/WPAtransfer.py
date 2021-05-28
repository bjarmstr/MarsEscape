from time import sleep, time
import sys
import subprocess

import redis

#rconfig.py, checkpipe.py etc need to be placed in same directory as this file
import rconfig as cfg #connection data for redis database
from checkpipe import get_light #light sensor function

from datetime import datetime

import board
import adafruit_dotstar as dotstar
dots = dotstar.DotStar(board.D23,board.D24, 8, brightness=0.1)  #default code brightness was .2
#hard to notice the difference between each step, blue is strongest of the 3 colors


import RPi.GPIO as GPIO
import threading


#for display
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont, ImageDraw
serial = i2c(port=1, address=0x3C)
#device = ssd1306(serial)
sizet = ImageFont.load_default()
size14= ImageFont.truetype("/home/pi/MarsOne/code2000.ttf", 14)
size15 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 15)
size13 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 13)
size12 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 12)

GPIO.setmode(GPIO.BCM)

#lspin = 18 #raspberry pi digital pin number that light sensor is wired to
#equip_id = 2 #Find equip_id in Equipment Table CDRA=1, WPA=2, SRA=3, =4
pipes = ('H2O','','', 'H2O', 'H2O','H2O') #labels on display
pipeDb = ('H2O-in-CDRA','','','H2O-in-SRA','H2O-in-LST','H2O-pot-out') #as designated in database
pipepin = (21,None,None,16,26,20)#99 designates no pipe in this location

connectAll = 0
pipevalue = [None]*6 #photocells starting values


redpin = 6
greenpin =7
bluepin = 5
pindict = {"blue": bluepin,"green": greenpin,"red": redpin,"none": "none"}
GPIO.setup(bluepin,GPIO.OUT) 
GPIO.setup(redpin,GPIO.OUT) 
GPIO.setup(greenpin,GPIO.OUT) 
GPIO.output(bluepin,GPIO.HIGH) #turn off to start
GPIO.output(redpin,GPIO.HIGH)
GPIO.output(greenpin,GPIO.HIGH)

SWITCH_PIN= 27
Wait_power = True

Enc_A = 17              # Encoder input A: input GPIO 4 
Enc_B = 18                      # Encoder input B: input GPIO 14
sbutton = 12

Menu_index = 0
Rotary_counter = 0              # Start counting from 0
Current_A = 1                   # Assume that rotary switch is not 
Current_B = 1                   # moving while we init software
LockRotary = threading.Lock()       # create lock for rotary switch

menu_status = ['NO', 'YES']

WPA_PREHEAT_CODE = 201
PREHEAT_TEMP = 130


def initGPIO():
    GPIO.setup(Enc_A, GPIO.IN)              
    GPIO.setup(Enc_B, GPIO.IN)
    GPIO.setup(sbutton,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(Enc_A, GPIO.RISING, callback=rotary_interrupt)                # NO bouncetime 
    GPIO.add_event_detect(Enc_B, GPIO.RISING, callback=rotary_interrupt)                # NO bouncetime
    GPIO.add_event_detect(sbutton, GPIO.FALLING, callback=button_interrupt, bouncetime=400)
    GPIO.add_event_detect(SWITCH_PIN, GPIO.BOTH, callback=pwr_detect, bouncetime=500)
    return

def pwr_detect(switched):
    global Wait_power
    print("callback", switched)
    if GPIO.input(SWITCH_PIN):
        print("power restored")
        Wait_power = False
    else:
        Wait_power = True
        print("external power switch off")

def wait_for_power():
    global Wait_power, OGArate
    if Wait_power == True:
        r.xadd("OGA",{"OGA-rate":"0"})
        OGArate = 0
        led_bulb("none")
        led_strip(0)
        Status = "shutdown"
    while Wait_power == True:      #waiting for external power 
        sleep(1)
        print("waiting")

def button_interrupt(sbutton):
    global Button_pressed
    if not GPIO.input(sbutton):
        print("button low")
        sleep(.05)
        if not GPIO.input(sbutton):
            print("button still low - button really pushed")
            Button_pressed = 1
    print ("button pressed")

# Rotarty encoder interrupt - I tried other simpler codes but had troubles with response/bouncing
def rotary_interrupt(A_or_B):
    global Rotary_counter, Current_A, Current_B, LockRotary
                                                    # read both of the switches
    Switch_A = GPIO.input(Enc_A)
    Switch_B = GPIO.input(Enc_B)
                                                    # now check if state of A or B has changed
                                                    # if not that means that bouncing caused it
    if Current_A == Switch_A and Current_B == Switch_B:     # Same interrupt as before (Bouncing)?
        return                                      # ignore interrupt!

    Current_A = Switch_A                                # remember new state
    Current_B = Switch_B                                # for next bouncing check


    if (Switch_A and Switch_B):                     # Both one active? Yes -> end of sequence
        LockRotary.acquire()                        # get lock 
        if A_or_B == Enc_B:                         # Turning direction depends on 
            Rotary_counter -= 1                     # which input gave last interrupt
        else:                                       # so depending on direction either
            Rotary_counter += 1                     # increase or decrease counter
        LockRotary.release()                        # and release lock
    return                                          # THAT'S IT


def main():
    global status, Wait_power, device 
    led_strip(0)
    led_bulb("none")
    initGPIO()   
    wait_for_power()      #waiting for external power 
    device = ssd1306(serial)                                    # Init interrupts, GPIO, ...
    boot_message()
    status = "startup"
    print("starting")
    while True:
        startup()
        
def boot_message():
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status:  ", font=size12, fill="white")
    sleep(2)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status:  ", font=size12, fill="white")
        draw.text((10, 23), "Initializing Boot", font=size12, fill="white")
    sleep(.5)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status:  ", font=size12, fill="white")
        draw.text((10, 23), "Initializing Boot", font=size12, fill="white")
        draw.text((10, 33), "Sequence ...", font=size12, fill="white")
    sleep(2)        
       
            
def startup():
    global connectAll, Button_pressed, status
    #print("top of startup", status)
    Button_pressed = 0
    piped = [0] * 6
    while connectAll < 6:
        for i in range(6):       #there are 6 squares that could have piping
            if pipepin[i] is not None: #if a pipe exists in this square
                pipe_key = "WPA-" + pipeDb[i]
                threshold = int(r.hget("threshold",pipe_key))
                print("threshold",threshold, pipe_key)
                led_bulb("blue")
                pipestat = get_light (pipepin[i],threshold)  #check if pipe is connected  this takes time    #added threshold   
                led_bulb("none")
                pipevalue[i] = pipestat[0]
                sudisplay(piped,pipevalue) 
                if piped[i] != pipestat[1]: #there is a change            
                    if pipestat[1] == 0:
                        piped[i] = 0
                    else:
                        piped[i]= 1
                        #W adding piped to db is a future consideration for the MarsControl Panel
                    sudisplay(piped,pipevalue)
            else:
                piped[i]=1  #treat nonexistant pipes as connected       
        connectAll = sum (piped)
        sleep(1) #time to read piped screen before displaying next screen
        status = "piped" 
    trained = r.get("trained")
    if trained == "True":  
        preheat = get_redis("WPA-preheat")
        if preheat >= PREHEAT_TEMP:
            status = "ready"
            led_bulb("blue")
        else:
            status = "piped"
            led_bulb("yellow")
        if status == "piped":
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((3, 2), "Status: Piped ", font=size15, fill="white")
                draw.text((22, 22), "Press START", font=size12, fill="white")
                draw.text((22, 33), "to Preheat", font=size12, fill="white")
        elif status == "ready":
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((3, 2), "Status:Preheated", font=size15, fill="white")
                draw.text((6, 32), "Press START to Run ", font=size12, fill="white")
        sleep(.3)    
        if Button_pressed == 1 :
            #connectAll = 0  #check piping next time unit shuts down
            running()
        
    else:
        Button_pressed = 0
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((3, 2), "Status: No Auth", font=size15, fill="white")
            draw.text((15, 14), "Need Training ", font=size13, fill="white")
            draw.text((14, 26), "Authorization", font=size13, fill="white") 
            draw.text((18, 38), "to Continue", font=size13, fill="white") 
        sleep(.3)
        
    
def running():
    global Rotary_index, Menu_index, Button_pressed, first, H2Olevel, WPArate, WPArateprev, trackMenu, status
    status = "running"
    led_bulb("green")
    Menu_index = 0
    Button_pressed = 0
    Rotary_index = 0
    first = True
    trackMenu = 0
    #when start button pressed -rate changed to 100 in database and WPArate
    dict_rate = {"WPA-rate":"100"}
    r.xadd("WPA",dict_rate)
    WPArate = 100
    WPArateprev = 100
    led_strip(WPArate) 
    
    while status == "running":
        H2Olevel = get_redis("H2O")
        #print("running H2Olevel",H2Olevel)
        run_selector()
        err = get_redis("WPA-error")   
        if err != 0:
            #if err == 900:  #***rate doesn't update if changed outside of WPA
            print ("error")
            status = "shutdown" 
        sleep(.05)
        
    shutdown(err)
            
def shutdown(err):
    global Button_pressed, Rotary_counter
    r.xadd(("WPA"),{"WPA-rate":"0"}) #tell the db that unit has shutdown ** this was not in origonal code
    if err == WPA_PREHEAT_CODE:
        display_preheat()
        print("preheating")
    else:
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
            draw.text((3, 2), "Status: ", font=size12, fill="white")
            draw.text((20, 12), "Shutting Down", font=size12, fill="white")
            if err == 100:
                 draw.text((22, 26), "Press Select", font=size12, fill="white")
                 draw.text((24, 37), "to return", font=size12, fill="white")
                 draw.text((8, 48), "to Startup Menu", font=size12, fill="white")
            else:
                draw.text((25,26),"ERROR CODE", font=size13, fill="white")
                draw.text((48,39),"{}".format(err), font=size13, fill="white") 
                draw.text((3,52),"Fix then Press Start", font=size12, fill="white") 
        Button_pressed = 0
        while Button_pressed == 0:
            led_bulb("none")
            led_strip(0)
            for i in range (10):   #number of times led flashes/2
                if i % 2 == 0:
                    led_bulb("none")
                    dots[0] = (70,0,0)
                else:
                    dots[0] = (0,0,0)
                    led_bulb("red")
                sleep(.2)
        start = time()  #long press to shutdown pi
        led_bulb("blue")
        while GPIO.input(sbutton) == GPIO.LOW:
            sleep(0.01)
        length = time() - start
        toggle_pressed = Rotary_counter
        if length > 4:
            r.xadd("WPA-error",{"WPA-error":"0"})
            Button_pressed = 0
            while (Button_pressed ==0):
                with canvas(device) as draw:
                    draw.rectangle(device.bounding_box, outline="black", fill="black")
                    draw.text((7, 14), "Start Button", font=size12, fill="white")
                    draw.text((11, 24), "to Shutdown ", font=size12, fill="white")
                    draw.text((7, 34), "Turn Dial", font=size12, fill="white")
                    draw.text((11, 44), "to Exit ", font=size12, fill="white")
                sleep(2)
                
                if (Rotary_counter != toggle_pressed):  
                    with canvas(device) as draw:
                        draw.rectangle(device.bounding_box, outline="black", fill="black")
                        draw.text((7, 15), "SSH or Use", font=size12, fill="white")
                        draw.text((11, 25), "Terminal", font=size12, fill="white") 
                        draw.text((11, 35), "to shutdown Pi", font=size12, fill="white") 
                    sleep(3)    
                    sys.exit()
                if (Button_pressed ==1):
                    with canvas(device) as draw:
                        draw.rectangle(device.bounding_box, outline="black", fill="black")
                        draw.text((7, 5), "Turn off Power", font=size14, fill="white")
                        draw.text((11, 30), "to Restart ", font=size14, fill="white")         
                    sleep(1)
                    subprocess.call(["sudo", "shutdown", "-h", "now"])  
                    sleep(3)
    if err ==100: #reset error to 0
        r.xadd("WPA-error",{"WPA-error":"0"})
        #err = 0
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
    Button_pressed = 0  #back to main function
  
            
def rotary_status(maxIndex,circular):
    global Rotary_counter, LockRotary, Rotary_index
    LockRotary.acquire()                    # global variables locked, can only be changed by this function until released
    NewCounter = Rotary_counter         # get counter value
    Rotary_counter = 0                      # RESET IT TO 0
    LockRotary.release()                    # and release lock
    if (NewCounter !=0):
        if (NewCounter > 0):
            Rotary_index += 1
        elif (NewCounter<0):
            Rotary_index -= 1 
        if (Rotary_index > maxIndex):
            Rotary_index = maxIndex
            if circular == True:
                Rotary_index = 0
        if (Rotary_index < 0):
            Rotary_index = 0
            if circular == True:
                Rotary_index = maxIndex

def run_selector():
    global Rotary_index, Menu_index, Button_pressed,first, WPArate, WPArateprev, trackMenu
    circular = True
    if (Menu_index == 0):
        newmenu = 0
        rotary_status(2,circular)
        display_main(Rotary_index)
        
        if (WPArateprev != WPArate) or (trackMenu != 0):
            if (WPArateprev != WPArate):
                WPArateprev = WPArate
            led_strip(WPArate)
            trackMenu = 0
            
        if (Button_pressed == 1):
            if (Rotary_index == 0):
                rotary_status(2,circular)
                display_shutdown()
                newmenu = 1
            if (Rotary_index == 1):
                Rotary_index = 0
                #display_rate()
                newmenu = 2
            if (Rotary_index == 2):
                newmenu = 3
        Menu_index = newmenu                    
        Button_pressed = 0
        
    elif (Menu_index == 1):
        rotary_status(1,circular)
        display_shutdown()
        if (Button_pressed == 1):
            print ("in shutdown menu with button pressed")
            if (Rotary_index == 0):
                Menu_index = 0
            else:
                r.xadd("WPA-error",{"WPA-error":"100"})
                led_strip(0)
            trackMenu = 1
            Button_pressed = 0
            
    elif (Menu_index == 2):
        if first:
            WPArate = get_redis("WPA")
            Rotary_index = int(WPArate/10)
            first = False
        circular = False
        rotary_status(15,circular)
        display_rate()
        if (Button_pressed == 1):
            WPArate = Rotary_index*10
            Rotary_index = 0
            Button_pressed = 0
            trackMenu = 2
            Menu_index = 0
            circular = True
            first = True
            dict_rate = {"WPA-rate":WPArate}
            r.xadd("WPA",dict_rate)      
                                           
    elif (Menu_index == 3):
        display_tank()
        if (Button_pressed == 1):
            Menu_index = 0
            trackMenu = 3
            Button_pressed = 0

def sudisplay (piped,pipevalue):           
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status: Startup ", font=size12, fill="white")
        draw.text((3,13), "piping connections", font=size12, fill="white")
        draw.line((1,25, 128,25),fill="white") #top horizontal line
        draw.line((43,25, 43,64),fill="white") #vertical line 1/3rd across screen
        draw.line((86,25, 86,64),fill="white") #vertial line 2/3rds across screen
        draw.line((1,44, 128,44),fill="white") #horizontal line for 6 piping boxes
        coordDict = {0:{"x":3,"y":30},1:{"x":46,"y":30},2:{"x":89,"y":30},
                     3:{"x":3,"y":51},4:{"x":46,"y":51},5:{"x":89,"y":51}}
        for count, coordItem in coordDict.items():
            x=coordItem["x"]
            y=coordItem["y"]  
            draw.text((x,y), "{}  ".format(pipes[count]), font=size13, fill="white")
            xcheckbox= x+21
            ycheckbox= y+10
            if pipes[count]: #if a value exists in pipes
                if piped[count] == 1:  #if piped place checkmark
                    draw.line((xcheckbox,ycheckbox-4, xcheckbox+4,ycheckbox), fill="white")  
                    draw.line((xcheckbox+5,ycheckbox, xcheckbox+13,ycheckbox-11), fill="white")
                else:
                    #add value instead of X for troublehooting
                    #if pipevalue[count]: #if this location has a pipe associated with it
                    #    draw.text((xcheckbox,ycheckbox-10), "{0:0.0f}".format(pipevalue[count]) , font=size12, fill="white") 
                    #else:
                    draw.line((xcheckbox+1,ycheckbox-11, xcheckbox+10,ycheckbox), fill="white") #x in checkbox
                    draw.line((xcheckbox+1,ycheckbox, xcheckbox+10,ycheckbox-11), fill="white")
                        

def invert(draw,x,y,text):
    length = len(text)
    if (length == 4): length = 3
    draw.rectangle((x-2, y, length*9+x, y+13), outline=255, fill=255)
    draw.text((x, y), text, font= size12, outline=0,fill="black")
    
def display_main(Rotary_index): 
    global H2Olevel, WPArate
    strH2Olevel = str(int(H2Olevel))
    strWPArate = str(WPArate)
    
    menustr = [['  Status: ','Running',''], ['    Rate:',strWPArate,'%'], [' H2OTank:',strH2Olevel,'%Full',]]
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        for i in range(len(menustr)):
            draw.text((4, i*15+10), menustr[i][0], font=size12, fill=255) 
            if( i == Rotary_index):
                invert(draw, 61, i*15+10, menustr[i][1])
                draw.text((87,i*15+10), menustr[i][2], font=size12, fill=255)
            else:
                draw.text((61, i*15+10), menustr[i][1], font=size12, fill=255)
                draw.text((87,i*15+10), menustr[i][2], font=size12, fill=255)
      

def display_shutdown():
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((12, 7), 'Shutdown?', font=size13, fill=255) 
        for i in range(len(menu_status)):
            if( i == Rotary_index):
                invert(draw, 22, i*14+25, menu_status[i])
            else:
                draw.text((22, i*14+25), menu_status[i], font=size12, fill=255) 

def display_rate():
    global Rotary_index
    rate = Rotary_index*10
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((5, 7), 'Production Rate ', font=size13, fill=255)  
        textstr = ' ' + str(rate) + ' '
        invert(draw, 49, 23, textstr)
        draw.text((95, 23), '% ', font=size13, fill=255)
        if rate > 100:
            draw.text((3, 40), '>100 not recommended', font=sizet, fill=255)
            draw.text((2, 49), 'Reduces Equipmnt Life', font=sizet, fill=255)
            
def display_tank():
    global H2Olevel
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((7, 3), 'H2O Tank Level ', font=size13, fill=255)
        H2Olevel = get_redis("H2O")
        led_strip_lvl(int(H2Olevel))
        OGArate = get_redis("OGA")
        if (WPArate - OGArate) == 0:
            direction = "stable"
        elif (WPArate - OGArate)< 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        draw.text((30, 13), "{}% Full".format(int(H2Olevel)), font=size14, fill=255)
        draw.text((3,30),  "H2O level {}.".format(direction), font=sizet, fill=255)
        if direction != "stable":
            draw.text((3,40),  "If WPArate=OGArate,", font=sizet, fill=255)
            draw.text((3,50), "level will stabilize.",font=sizet, fill=255)
        
def display_preheat():
    global Button_pressed
    preheat = get_redis("WPA-preheat")
    while preheat < PREHEAT_TEMP:
        preheat = get_redis("WPA-preheat")
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((7, 3), 'Status: Pre-heating ', font=size12, fill=255)
            draw.text((22, 21), 'TEMPERATURE', font=size12, fill=255)
            draw.text((10, 32),  "Required: {} degC".format(PREHEAT_TEMP), font=size12, fill=255)
            draw.text((10, 42),  "Actual: {} degC".format(preheat), font=size12, fill=255)
    
        led_bulb("none")
        led_strip(0)
        for i in range (2):   #number of times led flashes/2
            if i % 2 == 0:
                led_bulb("none")
            else:
                led_bulb("yellow")
            sleep(.4)
        


def led_bulb(color):
    if color != "none" and color !="yellow":
        GPIO.output((pindict[color]),GPIO.LOW)
    if color != "red":
        GPIO.output(redpin,GPIO.HIGH)
    if color != "green":
        GPIO.output(greenpin,GPIO.HIGH)
    if color != "blue":
        GPIO.output(bluepin,GPIO.HIGH)
    if color == "yellow":
        GPIO.output(redpin,GPIO.LOW)
        GPIO.output(greenpin,GPIO.LOW)
 

def led_strip(colorOn): 
    #print("led_strip called")
    for dot in range(8):
        dots[dot] = (0,0,0)
    if colorOn <= 100:
        lightdot = colorOn/12.5
        lightdot_int = int(lightdot)
        dotRemainder = lightdot - lightdot_int
        partialdot = int (80*dotRemainder)
        for dot in range(lightdot_int):
            dots[dot] = (0,80,0)
        if lightdot_int < 8:
            dots[lightdot_int] = (0,partialdot,0)
            
    elif (colorOn >100) and (colorOn <=150):
        lightdot = (colorOn-100)/12.5  #rate >100
        lightdot_int = int(lightdot)
        dotRemainder = lightdot - lightdot_int
        partialdot = int (80*dotRemainder)
        for dot in range(4):
            dots[dot] = (0,80,0)
        for dot in range(4, lightdot_int+4):
            dots[dot] = (80,0,0)    
        if lightdot_int < 4:
            dots[lightdot_int + 4] = (partialdot,0,0) 

def led_strip_lvl(colorOn):
    lightdots = colorOn/12.5
    for dot in range(int(lightdots+1),8):   
        dots[dot] = (0,0,0)
    
    for dot in range(int(lightdots)):
        dots[dot] = (0,0,80)
    
    dotRemainder = lightdots - int(lightdots)
    partialdot = int (60*dotRemainder)
    print(partialdot)
    
    dots[int(lightdots)] = (0,0,partialdot)


def get_redis(equip_stream):
    #Finds the newest rate/level from the stream and the time it was recorded
    #Redis stream id's starts with time from Unix Epoch
    #value is stored as the value in a dictionary datatype
    raw_data = r.xrevrange(equip_stream,"+","-",1)
    #print(raw_data,"raw data")
    dict_info = ((raw_data[0])[1])
    #print(dict_info)
    for (thevalue) in dict_info.values():  #A way to get values from key/values pairs in dict
        valueX = float(thevalue) #going to integer here was putting errors
        value = int(valueX)
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
        led_bulb("none")
        led_strip(0)
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
        pass
   
    finally:
        GPIO.cleanup()
