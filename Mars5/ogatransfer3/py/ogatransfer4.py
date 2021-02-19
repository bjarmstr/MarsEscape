from time import sleep, time
import subprocess

import redis

#rconfig.py, checkpipe.py etc need to be placed in same directory as this file
import rconfig as cfg #connection data for redis database
from checkpipe import get_light #light sensor function

import board
import adafruit_dotstar as dotstar
dots = dotstar.DotStar(board.SCK,board.MOSI, 40, brightness=0.05)

import RPi.GPIO as GPIO
import threading

#for display
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont, ImageDraw
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
sizet = ImageFont.load_default()
size14= ImageFont.truetype("code2000.ttf", 14)
size15 = ImageFont.truetype("FreePixel.ttf", 15)
size13 = ImageFont.truetype("FreePixel.ttf", 13)
size12 = ImageFont.truetype("FreePixel.ttf", 12)

GPIO.setmode(GPIO.BCM)

#lspin = 18 #raspberry pi digital pin number that light sensor is wired to
equip_id = 4 #Find equip_id in Equipment Table CDRA=1, WPA=2, SRA=3, OGA=4
pipes = ('H2','','', 'O2', '','H2O') #labels on display
pipeDb = ('H2_out','','','O2_out','','H2O_Pot_in') #as designated in database
pipepin = (21,None,None,26,None,19)

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


Enc_A = 17              # Encoder input A: input GPIO 4 
Enc_B = 18                      # Encoder input B: input GPIO 14
sbutton = 12

Menu_index = 0
Rotary_counter = 0              # Start counting from 0
Current_A = 1                   # Assume that rotary switch is not 
Current_B = 1                   # moving while we init software
LockRotary = threading.Lock()       # create lock for rotary switch

menu_status = ['NO', 'YES']


def init():
    GPIO.setup(Enc_A, GPIO.IN)              
    GPIO.setup(Enc_B, GPIO.IN)
    GPIO.setup(sbutton,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(Enc_A, GPIO.RISING, callback=rotary_interrupt)                # NO bouncetime 
    GPIO.add_event_detect(Enc_B, GPIO.RISING, callback=rotary_interrupt)                # NO bouncetime
    GPIO.add_event_detect(sbutton, GPIO.FALLING, callback=button_interrupt, bouncetime=400)
    return

def button_interrupt(sbutton):
    global Button_pressed
    Button_pressed = 1
    print("button pressed")

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
    global status
    status = "startup"
    #status = "running"
    led_strip(0)
    led_bulb("none")
    init()                                      # Init interrupts, GPIO, ...
    #running()
    
    while True:
        startup()
        
        
       
            
def startup():
    global connectAll, Button_pressed, status
    Button_pressed = 0
    piped = [0] * 6
    print("top of startup")
    while connectAll < 6:
        for i in range(6):       #there are 6 squares that could have piping
            if pipepin[i] is not None: #if a pipe exists in this square
                threshold = 10000 #W move this to database
                led_bulb("blue")
                pipestat = get_light (pipepin[i],threshold)  #check if pipe is connected  this takes time    #added threshold   
                led_bulb("none")
                print (pipestat,"pipestat", i)
                pipevalue[i] = pipestat[0]
                sudisplay(piped,pipevalue) 
                if piped[i] != pipestat[1]: #there is a change            
                    if pipestat[1] == 0:
                        piped[i] = 0
                    else:
                        piped[i]= 1
                        #update database
                        #Xinputs = (1, equip_id, pipeDb[i]) #connected - write status 1 to piping table
                        #Xupdate_pipe_db(inputs,db,c)
                        r.hset("OGA_pipe",pipes[i],"True")
                    sudisplay(piped,pipevalue)
            else:
                piped[i]=1  #treat nonexistant pipes as connected
               
        connectAll = sum (piped)
        
        sleep(3)
        status = "ready" #once piping is correct, it is not checked again
        
    if status == "ready":
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((3, 2), "Status: Ready ", font=size15, fill="white")
            draw.text((6, 33), "Press START to Run ", font=size12, fill="white")
    
    if Button_pressed == 1 :
        running()
        status = "startup"
        connectAll = 0
             
    
def running():
    global Rotary_index, Menu_index, Button_pressed, first, H2Olevel, OGArate, OGArateprev, trackMenu
    status = "running"
    led_bulb("green")
    Menu_index = 0
    Button_pressed = 0
    Rotary_index = 0
    first = True
    trackMenu = 0
    #when start button pressed rate changed to 100 in database and OGArate
    dict_rate = {"rate":"100"}
    r.xadd("OGA",dict_rate)
    OGArate = 100
    OGArateprev = 100
    led_strip(OGArate) 
    
    while status == "running":
        #Xinputs = ("14", "level") 
        #XH2Olevel,timestamp = query_op_parm(inputs,c)
        #print("running H2Olevel",H2Olevel)
        H2Olevel = get_redis("H2Otank")
        run_selector()
        #Xinputs = (equip_id, "error")
        #Xerr,timestamp = query_op_parm(inputs,c) #check db, change of conditions in external equipment (eg. power from teg), or override added from escape room supervisor 
        err = get_redis("OGA_error")
        if err != 0:
            print ("error")
            status = "shutdown" 
            
    shutdown(err)
            
def shutdown(err):
    global Button_pressed
    print ("finished running", err)
    with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
            draw.text((3, 2), "Status: ", font=size12, fill="white")
            draw.text((20, 12), "Shutting Down", font=size12, fill="white")
            if err != 100:
                draw.text((25,26),"ERROR CODE", font=size12, fill="white")
                draw.text((48,42),"{}".format(int(err)), font=size13, fill="white") 
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
    while GPIO.input(sbutton) == GPIO.LOW:
        sleep(0.01)
    length = time() - start
    print (length)
    if length > 4:
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
            draw.text((7, 5), "Turn off Power", font=size14, fill="white")
            draw.text((11, 30), "to Restart ", font=size14, fill="white")
        subprocess.call(["shutdown", "-h", "now"])  
   
    if err ==100: #reset error to 0
        r.xadd("OGA_error",{"reset":"0"})
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
    global Rotary_index, Menu_index, Button_pressed,first, OGArate, OGArateprev, trackMenu
    circular = True
    if (Menu_index == 0):
        newmenu = 0
        rotary_status(2,circular)
        display_main(Rotary_index)
        
        if (OGArateprev != OGArate) or (trackMenu != 0):
            if (OGArateprev != OGArate):
                OGArateprev = OGArate
            led_strip(OGArate)
            trackMenu = 0
            
        if (Button_pressed == 1):
            if (Rotary_index == 0):
                rotary_status(2,circular)
                display_shutdown()
                newmenu = 1
            if (Rotary_index == 1):
                Rotary_index = 0
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
                r.xadd("OGA_error",{"user":"100"})
                led_strip(0)
            trackMenu = 1
            Button_pressed = 0
            
    elif (Menu_index == 2):
        if first:
            #Xinputs = (equip_id, "rate") 
            #XOGArate,timestamp = query_op_parm(inputs,c)
            OGArate = get_redis("OGA")
            Rotary_index = int(OGArate/10)
            first = False
        circular = False
        rotary_status(15,circular)
        display_rate()
        if (Button_pressed == 1):
            OGArate = Rotary_index*10
            Rotary_index = 0
            Button_pressed = 0
            trackMenu = 2
            Menu_index = 0
            circular = True
            first = True      
            r.xadd(("OGA"),{"rate":OGArate})                             
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
            #for count in range (len(pipes)):
            coordDict = {0:{"x":3,"y":30},1:{"x":46,"y":30},2:{"x":89,"y":30},
                         3:{"x":3,"y":51},4:{"x":46,"y":51},5:{"x":89,"y":51}}
            for count in coordDict.values():
                x=count["x"]
                y=count["y"]  
                draw.text((x,y), "{}  ".format(pipes[count]), font=size13, fill="white")
                xcheckbox= x+21
                ycheckbox= y+10
                if pipes[count]: #if a value exists in pipes
                    if piped[count] == 1:  #if piped place checkmark
                        draw.line((xcheckbox,ycheckbox-4, xcheckbox+4,ycheckbox), fill="white")  
                        draw.line((xcheckbox+5,ycheckbox, xcheckbox+13,ycheckbox-11), fill="white")
                    else:
                        #T refactor after troublehooting
                        if pipevalue[count]: #if this location has a pipe associated with it
                            draw.text((xcheckbox,ycheckbox-10), "{0:0.0f}".format(pipevalue[count]) , font=size12, fill="white") 
                        else:
                            draw.line((xcheckbox+1,ycheckbox-11, xcheckbox+10,ycheckbox), fill="white") #x in checkbox
                            draw.line((xcheckbox+1,ycheckbox, xcheckbox+10,ycheckbox-11), fill="white")
                            
def invert(draw,x,y,text):
    length = len(text)
    if (length == 4): length = 3
    draw.rectangle((x-2, y, length*9+x, y+13), outline=255, fill=255)
    draw.text((x, y), text, font= size12, outline=0,fill="black")
    
def display_main(Rotary_index):
    global H2Olevel, OGArate
    strH2Olevel = str(int(H2Olevel))
    strOGArate = str(OGArate)
    menustr = [['  Status: ','Running',''], ['    Rate:',strOGArate,'%'], [' H2OTank:',strH2Olevel,'%Full',]]
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
    led_strip(rate)
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
        H2Olevel = get_redis("H2Otank")
        led_strip_lvl(int(H2Olevel))
        WPArate = get_redis("WPA")
        if (WPArate - OGArate) == 0:
            direction = "stable"
        elif (WPArate - OGArate)< 0:
            direction = "decreasing"
        else:
            direction = "increasing"
        draw.text((30, 13), "{}% Full".format(int(H2Olevel)), font=size14, fill=255)
        draw.text((3,30),  "H2O level {}.".format(direction), font=sizet, fill=255)
        if direction != "stable":
            draw.text((3,40),  "If WPArate=OGArate,", font=sizet, fill=255)
            draw.text((3,50), "level will stabilize.",font=sizet, fill=255)
        
def led_bulb(color):
    if color!= "none":
        GPIO.output((pindict[color]),GPIO.LOW)
    if color != "red":
        GPIO.output(redpin,GPIO.HIGH)
    if color != "green":
        GPIO.output(greenpin,GPIO.HIGH)
    if color != "blue":
        GPIO.output(bluepin,GPIO.HIGH)

def led_strip(colorOn):
    if colorOn == 0:
        for dot in range(40):
            dots[dot] = (0,0,0)
    elif colorOn <= 100:
        lightdots = int(colorOn/2.5)
        for dot in range(39,39-lightdots,-1):
            dots[dot] = (0,80,0)
        for dot in range (40-lightdots):
            dots[dot]=(0,0,0)
    elif (colorOn >100) and (colorOn <=150): 
        lightdots = int((colorOn-100)/2.5)
        if colorOn <=125:
            for dot in range(39,39-lightdots,-1):
                dots[dot] = (60,60,0)
        else:
            for dot in range(39,29,-1):
                dots[dot] = (60,60,0)
            for dot in range(29,39-lightdots,-1):
                dots[dot] =(80,0,0)     
        for dot in range(40-lightdots):
            dots[dot] = (0,80,0) #turn remainder green 


def led_strip_lvl(colorOn):
    lightdots = colorOn/2.5
    dotRemainder = lightdots - int(lightdots)
    lightdots = int(lightdots)
    for dot in range(40-lightdots):
        dots[dot] = (0,0,0)
    for dot in range(39,(39-lightdots),-1):
        dots[dot] = (0,0,80)
    print(dotRemainder,"dotRemainder -how many dots are lit")
    partialdot = int (60*dotRemainder)
    dots[(39-lightdots)] = (0,0,partialdot)

    
def get_redis(equip_stream):
    #Finds the newest rate/level from the stream and the time it was recorded
    #Redis stream id's starts with time from Unix Epoch
    #value is stored as the value in a dictionary datatype
    
    raw_data = r.xrevrange(equip_stream,"+","-",1)
    dict_info = ((raw_data[0])[1])
    print(dict_info)
    for (thevalue) in dict_info.values():  #A way to get values from key/values pairs in dict
        valueX = float(thevalue) #going to integer here was putting errors
        value = int(valueX)
    return value


if __name__ == '__main__':
    try:
        r = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                         password=cfg.redis_signin["password"], decode_responses=True)
        
    except Exception as e:
        print(e, "Trouble connecting to redis db")
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((10,15), "Server Error",font=size12, fill="white")
            draw.text((13,35), "- Check master Pi-", font=size12, fill="white")
        sleep(8)

    try:
        main()
    except KeyboardInterrupt:
        print ("keyboard interrupt - ending")
        led_bulb("none")
        led_strip(0)
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
        pass
   
    finally:
        GPIO.cleanup()
