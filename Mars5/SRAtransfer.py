from time import sleep,time
import subprocess

import redis
from datetime import datetime
import rconfig as cfg #connection data for redis database
from checkpipe import get_light #light sensor function

import board
import adafruit_dotstar as dotstar
dots = dotstar.DotStar(board.SCK,board.MOSI, 8, brightness=0.1)  #default code brightness was .2
#hard to notice the difference between each step, blue is strongest of the 3 colors


import RPi.GPIO as GPIO
import threading

import serial

#ser.baudrate=9600

#for display
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
serial_display = i2c(port=1, address=0x3C)

sizet = ImageFont.load_default()
size14= ImageFont.truetype("/home/pi/MarsOne/code2000.ttf", 14)
size15 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 15)
size13 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 13)
size12 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 12)

GPIO.setmode(GPIO.BCM)
equip_id = 3 #Find equip_id in Equipment Table CDRA=1, WPA=2, SRA=3, OGA=4
pipes = ('CO2','','H2', 'CH4', 'N2','H2O') #labels on display
pipeDb = ('CO2-in','','H2-in','CH4-out','N2-in','H2O-out') #as designated in database
pipepin = (99,99,19,21,20,26)#99 designates no pipe in this location

#Error Codes as defined in marscontrol.py
LOCAL_ERROR_CODES = [100, 308, 313, 113, 534]


connectAll = 0
pipevalue = [666,666,666,666,666,666]



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
nbutton = 16
SWITCH_PIN = 23

Menu_index = 0
Selector_counter = 0              # Start counting from 0
Current_A = 1                   # Assume that rotary switch is not 
Current_B = 1                   # moving while we init software
LockSelector = threading.Lock()       # create lock for rotary switch

Button_pressed = 0        #initialize global variables
N2_purge = 0
Selector_index = 0
SRArateprev = 0
SRArate = 0
CO2level = 0
trackMenu = 0
Status = "startup"
Wait_power = True
first = True

menu_status = ['NO', 'YES']


def init():
    serialThread = threading.Thread(target=serial_compile, daemon=True)
    serialThread.start()

    return

def serial_compile():
    global Selector_counter,  Button_pressed
    print("serial_compile")
    buffer_string = ''
    add_to_buff = ''
    t_end = time() + 3
    while True:
        try:
            buffer_string = str(ser.read(ser.inWaiting()))
            buffer_string = buffer_string[2:-1] #removes 'b off the front and ' off the back
            buffer_string = add_to_buff + buffer_string
            add_to_buff = ''
            #print (buffer_string,"buff string")    
            if '\\r\\n' in buffer_string:
                lines = buffer_string.split('\\r\\n')
                last_received = lines[-2] #last item in list is empty and second last contains latest data 
                #print(last_received,"last received")
                if "Left" in last_received:
                    Selector_counter = Selector_counter -1
                    print("down")
                elif "Right" in last_received:
                    Selector_counter = Selector_counter +1
                    print("up")
                elif "Middle" in last_received:
                    print("button select")
                    Button_pressed = 1  #what if button and middle selector pushed at same time 
            elif buffer_string !="":
                add_to_buff = buffer_string
            sleep(.03)
        except Exception as e:
            #wait_for_power()
            print("added pause")
            sleep(1)
            
            sleep(1)
 
            print(e,"startup caught error arduino ")

def sbutton_interrupt(_pinNum):   #pinNum never used
    global Button_pressed
    if not GPIO.input(sbutton):
        print("button low")
        sleep(.05)
        if not GPIO.input(sbutton):
            print("button still low - button really pushed")
            Button_pressed = 1
    print ("button triggered")
    
def nbutton_interrupt(_pinNum):   #pinNum never used
    global N2_purge, Status
    if not GPIO.input(sbutton):
        print("button low")
        sleep(.05)
        if not GPIO.input(sbutton):
            print("button still low - button really pushed")
            Button_pressed = 1
            N2_purge = 1
            if Status == "startup":
                r.xadd("SRA-purge",{"SRA-purge":"1"})
                print("N2purge button - ready for startup")
            #can't purge while unit is running only in startup mode
            #reset purge to 0 when restarting startup
    print("N2purge button")

def selector_interrupt():
    global Selector_counter
    
    #if up button is pressed:
    Selector_counter = Selector_counter +1
    #if down button is pressed:
    Selector_counter = Selector_counter-1
    
def pwr_detect(switched):
    global Wait_power
    print("callback", switched)
    if GPIO.input(SWITCH_PIN):
        print("power detected")
        Wait_power = False
    else:
        Wait_power = True
        print("external power switch off")

def wait_for_power():
    global Wait_power, SRArate
    if Wait_power == True:
        r.xadd("SRA",{"SRA-rate":"0"})
        SRArate = 0
        led_bulb("none")
        led_strip(0)
        Status = "shutdown"
    while Wait_power == True:      #waiting for external power 
        sleep(1)
        pwr_detect(SWITCH_PIN)
        print("waiting for power switch")
    print("power restored")


def main():
    global ser, device
    led_strip(0)
    led_bulb("none")
    GPIO.setup(sbutton,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(sbutton, GPIO.FALLING, callback=sbutton_interrupt, bouncetime=400)
    GPIO.setup(nbutton,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(nbutton, GPIO.FALLING, callback=nbutton_interrupt, bouncetime=400)
    GPIO.setup(SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(SWITCH_PIN, GPIO.BOTH, callback=pwr_detect, bouncetime=500)
    first_startup = True
    init_database()
    wait_for_power()      #waiting for external power 
    device = ssd1306(serial_display)
    sleep(1)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
    print("call arduino")
    
    try:
        ser=serial.Serial("/dev/ttyACM0",9600)
        print("try")
    except Exception as e:
        print("wont initialize",e)
        ser.close()
    finally:
        print("in the finally we survived")

        ser=serial.Serial("/dev/ttyACM0",9600)

    print("survived try statement ")
    #ser=serial.Serial("/dev/ttyACM0",9600)  #serial needs power to load
    #ser.baudrate=9600
    print("arduino working")
    boot_message()
    i = 0
    while True:
        try:
            i += 1
            print("start startup", i)
            startup(first_startup)
        except Exception as e:
            wait_for_power()
            print("added pause")
            sleep(1)
            device = ssd1306(serial)
            sleep(1)
            with canvas(device)as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((3, 2), "Recovered from Power Outage", font=size12, fill="white")
                
            print(e,"startup caught error inside with device re-initialized")
        
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
    sleep(4)
    print("end of boot")
        
def init_database():
    global r
    for i in range(5):
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
        break
            
def startup(first_start):
    global connectAll, Button_pressed, Status
    Status = "startup" 
    Button_pressed = 0
    if N2_purge == 1: 
        led_bulb("blue")
    else: 
        led_bulb("yellow")
        print("yellow - sstartup")
    #connectAll = 0
    piped = [0] * 6
    #print("top of startup")
    while connectAll < 6:
        for i in range(6):       #there are 6 squares that could have piping
            if pipepin[i] != 99: #if a pipe exists in this square
                pipe_key = "SRA-" + pipeDb[i]
                threshold = int(r.hget("threshold",pipe_key))
                #print(threshold,"threshold")
                pipestat = get_light (pipepin[i],threshold)  #check if pipe is connected  this takes time       
                pipevalue[i] = pipestat[0]
                if piped[i] != pipestat[1]: #there is a change            
                    if pipestat[1] == 0:
                        piped[i] = 0
                    else:
                        piped[i]= 1
                        #inputs = (1, equip_id, pipeDb[i]) #connected - write status 1 to piping table
                        #update_pipe_db(inputs,db,c)
                    sudisplay(piped,pipevalue)
            else:
                piped[i]=1  #treat nonexistant pipes as connected 
            #print (connectAll, "connectAll", piped)
        connectAll = sum (piped)
    if N2_purge: status = "ready"
    if N2_purge != 1:
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((3, 2), "Status: Piped ", font=size15, fill="white")
            draw.text((22, 22), "N2 Purge", font=size12, fill="white")
            draw.text((22, 33), "Required", font=size12, fill="white")
    else:
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((3, 2), "Status: Ready", font=size15, fill="white")
            draw.text((6, 32), "Press START to Run ", font=size12, fill="white")
    sleep(.3)
    print ("piping is connected, ready for startup, waiting for button press")
    if Button_pressed == 1 :
        if first_start == True:
            init()
        first_start = False
        led_strip(0)
        connectAll = 0  #check piping next time unit shuts down
        running()
        
            
    
def running():
    global Selector_index, Menu_index, Button_pressed, first, CO2level, SRArate, SRArateprev, trackMenu, Status
    Status = "running"
    led_bulb("green")
    Menu_index = 0
    Button_pressed = 0
    Selector_index = 0
    first = True
    trackMenu = 0
    #when start button pressed -rate changed to 100 in database and SRArate
   #inputs = (3,"rate", 100, datetime.now())
    #insert_op_parm(inputs,db,c)
    r.xadd("SRA",{"SRA-rate":"100"})
    SRArate = 100
    SRArateprev = 100
    led_strip(SRArate)

    
    while Status == "running":
        CO2level = get_redis("CO2")
        run_selector() 
        err = get_redis("SRA-error")
        if err != 0:
            print ("error")
            Status = "shutdown" 
        sleep(.05)
        
    
    shutdown(err)

            
def shutdown(err):
    global Button_pressed, N2_purge
    print ("top of shutdown, finished running", err)
    r.xadd(("SRA"),{"SRA-rate":"0"}) #tell the db that SRA has shutdown ** this was not in origonal code
    r.xadd("SRA-purge",{"SRA-purge":"0"})
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
        draw.text((3, 2), "Status: ", font=size12, fill="white")
        draw.text((20, 12), "Shutting Down", font=size12, fill="white")
        if err == 100:
             draw.text((22, 25), "Press Select", font=size12, fill="white")
             draw.text((24, 36), "to return", font=size12, fill="white")
             draw.text((8, 47), "to Startup Menu", font=size12, fill="white")
        else:    
            draw.text((25,26),"ERROR CODE", font=size13, fill="white")
            draw.text((48,39),"{}".format(err), font=size13, fill="white") 
            draw.text((3,52),"Fix then Press Start", font=size12, fill="white") 
    if err in LOCAL_ERROR_CODES : #reset error to 0
        r.xadd("SRA-error",{"SRA-error":"0"})
        err = 0
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
    print("before button while loop")
    while GPIO.input(sbutton) == GPIO.LOW:
        sleep(0.01)
    length = time() - start
    if length > 4:
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
            draw.text((7, 5), "Turn off Power", font=size14, fill="white")
            draw.text((11, 30), "to Restart ", font=size14, fill="white")
        subprocess.call(["shutdown", "-h", "now"])  
    N2_purge = 0
    Button_pressed = 0  #back to main function
    
    print(Status,"status, bottom of shutdown")
            
def selector_status(maxIndex,circular):
    global Selector_counter, LockSelector, Selector_index
    LockSelector.acquire()                    # global variables locked, can only be changed by this function until released
    NewCounter = Selector_counter         # get counter value
    Selector_counter = 0                      # RESET IT TO 0
    LockSelector.release()                    # and release lock
    if (NewCounter !=0):
        if (NewCounter > 0):
            Selector_index += 1
        elif (NewCounter<0):
            Selector_index -= 1 
        if (Selector_index > maxIndex):
            Selector_index = maxIndex
            if circular == True:
                Selector_index = 0
        if (Selector_index < 0):
            Selector_index = 0
            if circular == True:
                Selector_index = maxIndex

def run_selector():
    global Selector_index, Menu_index, Button_pressed,first, SRArate, SRArateprev, trackMenu
    circular = True
    if (Menu_index == 0):
        newmenu = 0
        selector_status(2,circular)
        display_main(Selector_index)
        
        if (SRArateprev != SRArate) or (trackMenu != 0):
            if (SRArateprev != SRArate):
                SRArateprev = SRArate
            led_strip(SRArate)
            trackMenu = 0
            
        if (Button_pressed == 1):
            if (Selector_index == 0):
                selector_status(2,circular)
                display_shutdown()
                newmenu = 1
            if (Selector_index == 1):
                Selector_index = 0
                #display_rate()
                newmenu = 2
            if (Selector_index == 2):
                newmenu = 3
        Menu_index = newmenu                    
        Button_pressed = 0
        
    elif (Menu_index == 1):
        selector_status(1,circular)
        display_shutdown()
        if (Button_pressed == 1):
            print ("in shutdown menu with button pressed")
            if (Selector_index == 0):
                Menu_index = 0
            else:
                #inputs = (equip_id,"error", 100, datetime.now())
                #insert_op_parm(inputs,db,c)
                r.xadd("SRA-error",{"SRA-error":"100"})
                led_strip(0)
            trackMenu = 1
            Button_pressed = 0
            
    elif (Menu_index == 2):
        if first:
            SRArate = get_redis("SRA")
            Selector_index = int(SRArate/10)
            first = False
        circular = False
        selector_status(15,circular)
        display_rate()
        if (Button_pressed == 1):
            SRArate = Selector_index*10
            Selector_index = 0
            Button_pressed = 0
            trackMenu = 2
            Menu_index = 0
            circular = True
            first = True
            r.xadd("SRA",{"SRA-rate":SRArate})
             
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
            for count in range (len(pipes)):
                x = 3
                y =30
                if count == 1:
                    x = 46
                elif count == 2:
                    x = 89
                elif count == 3:
                    y = 51
                elif count == 4:
                    x = 46
                    y = 51
                elif count == 5:
                    x = 89
                    y = 51
                draw.text((x,y), "{}  ".format(pipes[count]), font=size13, fill="white")
                xcheckbox= x+21
                ycheckbox= y+10
                if pipes[count]: #if a value exists in pipes
                    if piped[count] == 1:  #if piped place checkmark
                        draw.line((xcheckbox,ycheckbox-4, xcheckbox+4,ycheckbox), fill="white")  
                        draw.line((xcheckbox+5,ycheckbox, xcheckbox+13,ycheckbox-11), fill="white")
                    else:
                        #if pipevalue[count] != 666:
                        #    draw.text((xcheckbox,ycheckbox-10), "{0:0.0f}".format(pipevalue[count]) , font=size12, fill="white") #replace after troublehooting
                        #else:
                        draw.line((xcheckbox+1,ycheckbox-11, xcheckbox+10,ycheckbox), fill="white") #x in checkbox
                        draw.line((xcheckbox+1,ycheckbox, xcheckbox+10,ycheckbox-11), fill="white")
                 

def invert(draw,x,y,text):
    length = len(text)
    if (length == 4): length = 3
    draw.rectangle((x-2, y, length*9+x, y+13), outline=255, fill=255)
    draw.text((x, y), text, font= size12, outline=0,fill="black")
    
def display_main(Selector_index):
    
    global CO2level, SRArate
    strCO2level = str(int(CO2level))
    strSRArate = str(SRArate)
    
    menustr = [['  Status: ','Running',''], ['    Rate:',strSRArate,'%'], [' CO2Tank:',strCO2level,'%Full',]]
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        for i in range(len(menustr)):
            draw.text((4, i*15+6), menustr[i][0], font=size12, fill=255) 
            if( i == Selector_index):
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
            if( i == Selector_index):
                invert(draw, 22, i*14+25, menu_status[i])
            else:
                draw.text((22, i*14+25), menu_status[i], font=size12, fill=255) 

def display_rate():
    global Selector_index
    rate = Selector_index*10
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
    global CO2level
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((7, 3), 'CO2 Tank Level ', font=size13, fill=255)
        #inputs = ("13", "level") #CO2 tank id 13
        #CO2level,TimeT = query_op_parm(inputs,c)
        CO2level = get_redis("CO2")
        led_strip_lvl(int(CO2level))
        CDRArate = get_redis("CDRA")
       # WPArate = int(strWPArate)
        if (CDRArate - SRArate) == 0:
            direction = "stable"
        elif (CDRArate - SRArate)< 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        draw.text((30, 13), "{}% Full".format(int(CO2level)), font=size14, fill=255)
        draw.text((3,30),  "CO2 level {}.".format(direction), font=sizet, fill=255)
        if direction != "stable":
            draw.text((3,40),  "If CDRArate=SRArate,", font=sizet, fill=255)
            draw.text((3,50), "level will stabilize.",font=sizet, fill=255)
            
        
        
def led_bulb(color):
    if color!= "none" and color!="yellow":
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
    for dot in range(8):
        dots[dot] = (0,0,0)
    if colorOn <= 100:
        lightdot = colorOn/12.5
        lightdot_int = int(lightdot)
        dotRemainder = lightdot - lightdot_int
        partialdot = int (80*dotRemainder)
        for dot in range(lightdot_int):
            print(dot, "out of", lightdot_int)
            dots[dot] = (0,80,0)
        print(partialdot, "partialdot")
        if lightdot_int < 8:
            dots[lightdot_int] = (0,partialdot,0)
            
    elif (colorOn >100) and (colorOn <=150):
        lightdot = (colorOn-100)/12.5  #rate >100
        lightdot_int = int(lightdot)
        dotRemainder = lightdot - lightdot_int
        partialdot = int (80*dotRemainder)
        print(partialdot)
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
    
    dots[int(lightdots)] = (0,0,partialdot)
    
def get_redis(equip_stream):
    raw_data = r.xrevrange(equip_stream,"+","-",1)
    dict_info=((raw_data[0][1]))
    for (thevalue) in dict_info.values():
        valueX = float(thevalue) #going to integer here was putting errors
        value = int(valueX)
    return value

if __name__ == '__main__':
   
    try:
        main()
    except KeyboardInterrupt:
        print ("keyboard interrupt - ending")
        
   
    finally:
        r.xadd("SRA",{"SRA-rate":"0"})
        led_bulb("none")
        led_strip(0)
        ser.close()
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
        GPIO.cleanup()
