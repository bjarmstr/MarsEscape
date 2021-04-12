from time import sleep,time
import subprocess
import sys

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
ser=serial.Serial("/dev/ttyACM0",9600)
#ser.baudrate=9600

#for display
from luma.core.interface.serial import i2c  
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)    #128x60 pixels
sizet = ImageFont.load_default()
size14= ImageFont.truetype("/home/pi/MarsOne/code2000.ttf", 14)
size15 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 15)
size13 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 13)
size12 = ImageFont.truetype("/home/pi/MarsOne/FreePixel.ttf", 12)

GPIO.setmode(GPIO.BCM)

#lspin = 18 #raspberry pi digital pin number that light sensor is wired to
equip_id = 1 #Find equip_id in Equipment Table CDRA=1, WPA=2, SRA=3, OGA=4
pipes = ('','','CO2', '', '','H2O') #labels on display
pipeDb = ('CO2_in','','H2_in','CH4_out','N2_in','H2O_out') #as designated in database
pipepin = (99,99,99,99,99,21)#99 designates no pipe in this location
CO2_LEAK_CODE = 111

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

FUSE = 24
GPIO.setup(FUSE, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
Fuse_fixed = False
FUSE_CODE = 107

SWITCH = 16
SWITCH_LED = 20
GPIO.setup(SWITCH_LED, GPIO.OUT)
GPIO.output(SWITCH_LED,GPIO.HIGH)


Enc_A = 17              # Encoder input A: input GPIO 4 
Enc_B = 18                      # Encoder input B: input GPIO 14
sbutton = 12

Menu_index = 0
Selector_counter = 0              # Start counting from 0
Current_A = 1                   # Assume that rotary switch is not 
Current_B = 1                   # moving while we init software
LockSelector = threading.Lock()       # create lock for rotary switch

Button_pressed = 0        #initialize global variables
Selector_index = 0
CDRArateprev = 0
CDRArate = 0
CO2level = 0
trackMenu = 0
Status = "startup"
first = True
arduino_connect = False
test_leak_Arduino = False
menu_status = ['NO', 'YES'] #shutdown menu


def init():
    serialThread = threading.Thread(target=serial_compile, daemon=True)
    serialThread.start()

    return

def serial_compile():
    global Selector_counter,  Button_pressed, test_leak_Arduino, CO2_leak_Arduino, arduino_connect
    print("serial_compile")
    buffer_string = ''
    add_to_buff = ''
    #ser.reset_input_buffer()
    print("buffer reset")
    while True:
        buffer_string = str(ser.read(ser.inWaiting()))
        buffer_string = buffer_string[2:-1] #removes 'b off the front and ' off the back
        buffer_string = add_to_buff + buffer_string
        add_to_buff = ''
        #print (buffer_string,"buff string")    
        if '\\r\\n' in buffer_string:
            lines = buffer_string.split('\\r\\n')
            last_received = lines[-2] #last item in list is empty and second last contains latest data 
            #print(last_received,"last received")
            print(lines,"Uno")
            if "C" in last_received:  #arduino sends Connected
                arduino_connect = True
            elif "Left" in last_received:
                Selector_counter = Selector_counter +1
                print("down")
            elif "Right" in last_received:
                Selector_counter = Selector_counter -1
                print("up")
            elif "Middle" in last_received:
                print("button select")
                Button_pressed = 1  #what if button and middle selector pushed at same time 
            elif "OK" in last_received:  #arduino sends OK
                CO2_leak_Arduino = False
                print("CO2 leak Fixed")
            elif "F" in last_received:
                test_leak_Arduino = False
                print("received F from Arduino")
        elif buffer_string !="":
            add_to_buff = buffer_string
            
        
        sleep(.03)

def sbutton_interrupt(pinNum):   #pinNum never used
    global Button_pressed
    Button_pressed = 1
    print("button pressed")
    

def selector_interrupt():
    global Selector_counter
    
    #if up button is pressed:
    Selector_counter = Selector_counter +1
    #if down button is pressed:
    Selector_counter = Selector_counter-1


def main():
    led_strip(0)
    led_bulb("none")
    GPIO.setup(sbutton,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(sbutton, GPIO.FALLING, callback=sbutton_interrupt, bouncetime=400)
    GPIO.setup(SWITCH, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(SWITCH, GPIO.BOTH, callback=pwr_detect, bouncetime=500)
    first_startup = True
    boot_message() #initialize serial
    init_database()
    with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
    while GPIO.input(SWITCH) == False:      #waiting for external power 
        sleep(1)
        print("waiting for power switch") 
    GPIO.output(SWITCH_LED,GPIO.LOW) 
     
    
    while True:
        startup(first_startup)
        
def boot_message():
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status:  ", font=size12, fill="white")
    sleep(3)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status:  ", font=size12, fill="white")
        draw.text((10, 23), "Initializing Boot", font=size12, fill="white")
    sleep(1)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status:  ", font=size12, fill="white")
        draw.text((10, 23), "Initializing Boot", font=size12, fill="white")
        draw.text((10, 33), "Sequence ...", font=size12, fill="white")
    sleep(3)
    init() #this was in firststart of startup ~line230
    print(arduino_connect, "arduino connection after boot message")
        
def init_database():
    global r
    for i in range(5):
        try:
            r = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                         password=cfg.redis_signin["password"], decode_responses=True)
        
        except:
            print("Trouble connecting to redis db")
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((10,15), "Server Error",font=size12, fill="white")
                draw.text((13,35), "- Check master Pi-", font=size12, fill="white")
        sleep(8)
        break
            
def startup(first_start):
    global Button_pressed, Status, connectAll
    Button_pressed = 0
    
    piped = [0] * 6
    print("top of startup")
    while connectAll < 6:
        led_bulb("blue")
        for i in range(6):       #there are 6 squares that could have piping
            
            if pipepin[i] != 99: #if a pipe exists in this square
                #pipe_key = "CDRA-" + pipeDb[i]
                #threshold = int(r.hget("threshold",pipe_key))
                threshold = int(r.hget("threshold", "CDRA-H2O-out"))
                #threshold = 120000
                #print("threshold", threshold)
                pipestat = get_light (pipepin[i],threshold)  #check if pipe is connected  this takes time       
                pipevalue[i] = pipestat[0]
                #print(pipevalue[i], "pipe value")
                sudisplay(piped,pipevalue) #remove after troubleshooting
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
                
            print (connectAll, "connectAll", piped)
        connectAll = sum (piped)
        
    Status = "ready" #once piping is correct, it is not checked again
    led_bulb("none")
    print(arduino_connect, "arduino connection in start-up")
    if (arduino_connect == False):
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((3, 2), "Status:  ", font=size15, fill="white")
            draw.text((6, 33), "Communication Error ", font=size12, fill="white")
            draw.text((6, 33), "Rebooting ", font=size12, fill="white")
        sleep(3)
    if (arduino_connect == False):
        ser.close()
        ser.open()
        #ser=serial.Serial("/dev/ttyACM0",9600)
        print("restarted serial connection hopefully")
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((3, 2), "Status:  ", font=size15, fill="white")
            draw.text((6, 33), "Rebooting", font=size12, fill="white")
        sleep(6)
        print(arduino_connect, "arduino connection 6seconds after reboot")
        for i in range(30):
            progress_led(i)
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="white", fill="black")
                draw.text((3, 2), "Status:  ", font=size15, fill="white")
                draw.text((6, 23), "Reboot", font=size12, fill="white")
                draw.text((6, 33), "in Progress", font=size12, fill="white")
            sleep(.2)
        sudisplay(piped,pipevalue)
    print ("piping is connected, ready for startup, waiting for button press")
    sleep(2)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((3, 2), "Status: Ready ", font=size15, fill="white")
        draw.text((6, 33), "Press START to Run ", font=size12, fill="white")
    
    if Button_pressed == 1 :
        if first_start == True:
            print("initialize here?")
            ser.write(b'B')
        first_start = False
        Status = "startup"
        running()
        
            
    
def running():
    global Selector_index, Menu_index, Button_pressed, first, CO2level, CDRArate, CDRArateprev, trackMenu, Status
    Status = "running"
    led_bulb("green")
    Menu_index = 0
    Button_pressed = 0
    Selector_index = 0
    first = True
    trackMenu = 0
    #when start button pressed -rate changed to 100 in database and CDRArate
    #inputs = (3,"rate", 100, datetime.now())
    #insert_op_parm(inputs,db,c)
    dict_rate = {"CDRA-rate":"100"}
    r.xadd("CDRA",dict_rate)
    CDRArate = 100
    CDRArateprev = 100
    led_strip(CDRArate)

    
    while Status == "running":
        #inputs = ("13", "level") #CO2 tank id 13
        #CO2level,timestamp = query_op_parm(inputs,c)
        CO2level = get_redis("CO2")
        sleep(.05)
        run_selector()
        #inputs = (equip_id, "error")
        #err,timestamp = query_op_parm(inputs,c) #check db, change of conditions in external equipment (eg. power from teg), or override added from escape room supervisor 
        err = get_redis("CDRA-error")
        if err != 0:
            print ("error")
            Status = "shutdown" 
            if err == CO2_LEAK_CODE:
                scenario_CO2_leak()
                Status = "running"
                CDRArate = get_redis("CDRA")  #
            if err == FUSE_CODE:
                scenario_fuse_blown()
                Status = "running"
                
    
    shutdown(err)

def scenario_CO2_leak(): 
    global Button_pressed, test_leak_Arduino, CO2_leak_Arduino
    ser.write(b'L')
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
        draw.text((20, 2), "ERROR", font=size12, fill="white")#y12 too high
        draw.text((20, 14),"CODE {}".format(CO2_LEAK_CODE), font=size12, fill="white")#y12
        draw.text((25,28),"Fix Problem", font=size12, fill="white")
        draw.text((25,40), "then press start",font=size12, fill="white") 
    CDRArate = get_redis("CDRA")
    led_bulb("blue")
    led_strip(0)
    sleep(.2)
    while Button_pressed == 0:
        CDRArate = reduce_rate(CDRArate)
        for i in range (10):   
            if i % 2 == 0:
                #led_bulb("none")
                dots[0] = (30,0,0)
            else:
                dots[0] = (0,0,0)
                #led_bulb("red")
    Button_pressed = 0
    test_leak_Arduino = True 
    CO2_leak_Arduino = True
    #led_bulb("none")
    led_strip(0)
    while CO2_leak_Arduino == True:  
        ser.write(b'C')
        sleep(.8)
        print("above leak test")
        j,i = 0,0
        startTimer = time()
        while test_leak_Arduino == True:
            if ((startTimer + 25)< time()):
                print("Ardunio taking too long - lost communication?", startTimer)
            CDRArate = reduce_rate(CDRArate) #CDRArate is no longer an integer
            j += 1
            i += 1
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="black", fill="black")
                draw.text((3, 1), "Checking Status: ", font=size13, fill="white")
                draw.text((3, 16),"{},{}".format(j,CDRArate), font=size12, fill="white")
                draw.text((36, 26),"12345678", font=size12, fill="white")
             
            err = get_redis("CDRA-error")  #MarsOne Operator can override pressure error
            if err != 111:  #any error code will reset CO2 error to 0
                CO2_leak_Arduino = False
            progress_led(i)
            if (i >8):
                i = 0
            if CO2_leak_Arduino == False:  #leak fixed 
                test_leak_Arduino = False    #leave loop
            elif test_leak_Arduino == False: #leak wasn't fixed - need to try again
                Button_pressed = 0
                with canvas(device) as draw:
                    draw.rectangle(device.bounding_box, outline="black", fill="black")
                    draw.text((3, 2), "Still Detecting", font=size12, fill="white")
                    draw.text((20, 14),"ERROR {}".format(CO2_LEAK_CODE), font=size12, fill="white")#y12
                    draw.text((15,28),"Fix Problem", font=size12, fill="white")
                    draw.text((10,40), "then press start",font=size12, fill="white")  
                sleep(.1)
                while Button_pressed == 0:
                    sleep(.2)  #need to sleep to give other threads priority
                Button_pressed = 0
                test_leak_Arduino = True
                ser.write(b'C')
                startTimer = time()
                sleep(.2)

    #Leak Fixed
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
        draw.text((3, 2), "Pressure Restored: ", font=size12, fill="white")
        draw.text((25,28),"Continue?", font=size12, fill="white")
    r.xadd("CDRA-error",{"CDRA-error":"0"})
    while Button_pressed ==0:      
        for i in range (8):
            dots[i] = (0,0,50)
            led_bulb("blue") #green not working?
    led_bulb("none")
    led_strip(0)
    Button_pressed = 0
    test_leak_Arduino = False  
     
def scenario_fuse_blown():
    global CDRArate
    led_bulb("none")
    led_strip(0)
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
    CDRArate = 0
    dict_rate = {"CDRA-rate":"0"}
    r.xadd("CDRA",dict_rate)
    err = get_redis("CDRA-error")
    while GPIO.input(FUSE) == False or err == 117:      #fuse needs replacement 
        print("waiting for fuse to be fixed")
        err = get_redis("CDRA-error")
        sleep(1)
    r.xadd("CDRA-error",{"CDRA-error":"0"})
    print("fuse fixed")
            
            
def shutdown(err):
    global Button_pressed, Selector_counter
    r.xadd(("CDRA"),{"CDRA-rate":"0"}) #tell the db that unit has shutdown ** this was not in origonal code
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
        draw.text((3, 2), "Status: ", font=size12, fill="white")
        draw.text((20, 17), "Shutting Down", font=size12, fill="white") #y12 too high
        if err != 100:
            err = int(err)
            draw.text((25,26),"ERROR CODE", font=size12, fill="white")
            draw.text((48,42),"{}".format(err), font=size13, fill="white") 
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
        dots[0]=(0,50,50)
        sleep(2)
    start = time()  #long press to shutdown pi
    led_bulb("blue")
    print("before button while loop")
    while GPIO.input(sbutton) == GPIO.LOW:
        sleep(0.01)
    length = time() - start
    print (length,"after while loop")
    toggle_pressed = Selector_counter
    if length > 4:
        Button_pressed = 0
        while (Button_pressed ==0):
            
            with canvas(device) as draw:
                draw.rectangle(device.bounding_box, outline="black", fill="black")
                draw.text((7, 14), "Start Button", font=size12, fill="white")
                draw.text((11, 24), "to Shutdown ", font=size12, fill="white")
                draw.text((7, 34), "Left/Right Pad", font=size12, fill="white")
                draw.text((11, 44), "to Exit ", font=size12, fill="white")
            sleep(2)
            
            if (Selector_counter != toggle_pressed):  
                with canvas(device) as draw:
                    draw.rectangle(device.bounding_box, outline="black", fill="black")
                    draw.text((7, 15), "SSH or Use", font=size12, fill="white")
                    draw.text((11, 25), "Terminal", font=size12, fill="white") 
                    draw.text((11, 35), "to shutdown Pi", font=size12, fill="white")
                r.xadd("CDRA-error",{"CDRA-error":"0"})  
                sleep(2)    
                sys.exit()
            if (Button_pressed ==1):
                with canvas(device) as draw:
                    draw.rectangle(device.bounding_box, outline="black", fill="black")
                    draw.text((7, 5), "Turn off Power", font=size14, fill="white")
                    draw.text((11, 30), "to Restart ", font=size14, fill="white")
                r.xadd("CDRA-error",{"CDRA-error":"0"})
                sleep(1)
                subprocess.call(["shutdown", "-h", "now"])  
                sleep(1)
    if err ==100: #reset error to 0
        r.xadd("CDRA-error",{"CDRA-error":"0"})
        err = 0
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="black", fill="black")
        draw.text((7, 15), "CDRA Rate = 0%", font=size13, fill="white")#y 5 too high

    Button_pressed = 0  #back to main function
    print(Status,"status, bottom of shutdown")

def pwr_detect(_pin):
    sleep(.5)
    if GPIO.input(SWITCH):
        print("power on")
        GPIO.output(SWITCH_LED,GPIO.LOW)
        
    else:
        print("power switch off")
        GPIO.output(SWITCH_LED,GPIO.HIGH)
        
def fuse_detect(_pin):
    global Fuse_fixed
    sleep(.2)
    if GPIO.input(FUSE):
        print("fuse is fixed")
        Fuse_fixed = True
    else:
        print("fuse still needs replacement")
        Fuse_fixed = False
    
            
def selector_status(maxIndex,circular):
    global Selector_counter, LockSelector, Selector_index
    LockSelector.acquire()                    # global variables locked, can only be changed by this function until released
    NewCounter = Selector_counter         # get counter value
    Selector_counter = 0                      # RESET IT TO 0
    LockSelector.release()                    # and release lock
    if (NewCounter !=0):
        if (NewCounter > 0):
            Selector_index += 1
            if circular == False:  #this is to get the rate to decrease with down button
                Selector_index -= 2
        elif (NewCounter<0):
            Selector_index -= 1 
            if circular == False:  #this is to get the rate to increase with up button
                Selector_index += 2
        if (Selector_index > maxIndex):
            Selector_index = maxIndex
            if circular == True:
                Selector_index = 0
        if (Selector_index < 0):
            Selector_index = 0
            if circular == True:
                Selector_index = maxIndex

def run_selector():
    global Selector_index, Menu_index, Button_pressed,first, CDRArate, CDRArateprev, trackMenu
    circular = True
    if (Menu_index == 0):
        newmenu = 0
        selector_status(2,circular)
        display_main(Selector_index)
        
        if (CDRArateprev != CDRArate) or (trackMenu != 0):
            if (CDRArateprev != CDRArate):
                CDRArateprev = CDRArate
            led_strip(CDRArate)
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
                r.xadd("CDRA-error",{"CDRA-error":"100"})
                led_strip(0)
            trackMenu = 1
            Button_pressed = 0
            
    elif (Menu_index == 2):
        if first:
            #inputs = (equip_id, "rate") 
            #CDRArate,timestamp = query_op_parm(inputs,c)
            CDRArate = get_redis("CDRA")
            Selector_index = int(CDRArate/10) # negative so top button increases rate
            first = False
        circular = False
        selector_status(15,circular)
        display_rate()
        if (Button_pressed == 1):
            CDRArate = Selector_index*10
            Selector_index = 0
            Button_pressed = 0
            trackMenu = 2
            Menu_index = 0
            circular = True
            first = True
            #inputs = (3,"rate", CDRArate, datetime.now())
            #insert_op_parm(inputs,db,c)
            dict_rate = {"CDRA-rate":CDRArate}
            r.xadd("CDRA",dict_rate)
             
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
        draw.text((3,14), "piping connections", font=size12, fill="white") #Y13 too high,16 too low
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
                    if pipevalue[count] != 666:
                        draw.text((xcheckbox,ycheckbox-10), "{0:0.0f}".format(pipevalue[count]) , font=size12, fill="white") #replace after troublehooting
                    else:
                        draw.line((xcheckbox+1,ycheckbox-11, xcheckbox+10,ycheckbox), fill="white") #x in checkbox
                        draw.line((xcheckbox+1,ycheckbox, xcheckbox+10,ycheckbox-11), fill="white")
                        

def invert(draw,x,y,text):
    length = len(text)
    if (length == 4): length = 3
    draw.rectangle((x-2, y, length*9+x, y+13), outline=255, fill=255)
    draw.text((x, y), text, font= size12, outline=0,fill="black")
    
def display_main(Selector_index):
    
    global CO2level, CDRArate
    strCO2level = str(int(CO2level))
    strCDRArate = str(CDRArate)
    
    menustr = [['  Status: ','Running',''], ['    Rate:',strCDRArate,'%'], [' CO2Tank:',strCO2level,'%Full',]]
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        for i in range(len(menustr)):
            draw.text((4, i*15+5), menustr[i][0], font=size12, fill=255) 
            if( i == Selector_index):
                invert(draw, 61, i*15+5, menustr[i][1])
                draw.text((87,i*15+5), menustr[i][2], font=size12, fill=255)
            else:
                draw.text((61, i*15+5), menustr[i][1], font=size12, fill=255)
                draw.text((87,i*15+5), menustr[i][2], font=size12, fill=255)
      

def display_shutdown():
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((8, 5), 'Shutdown?', font=size13, fill=255) #Y7 too low
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
        draw.text((5, 4), 'Production Rate ', font=size13, fill=255)  #Y7 too low
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
        #inputs = ("2", "rate") 
        #strWPArate,TimeT = query_op_parm(inputs,c)
        #******************change to CO2 **********************
        SRArate = get_redis("SRA")
       # WPArate = int(strWPArate)
        if (SRArate - CDRArate) == 0:
            direction = "stable"
        elif (SRArate - CDRArate)< 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        draw.text((30, 13), "{}% Full".format(int(CO2level)), font=size14, fill=255)
        draw.text((3,30),  "CO2 level {}.".format(direction), font=sizet, fill=255)
        if direction != "stable":
            draw.text((3,40),  "If CDRArate=SRArate,", font=sizet, fill=255)
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
   
   #if colorOn == 0:
    for dot in range(8):
        dots[dot] = (0,0,0)
    if colorOn <= 100:
        lightdots = colorOn/20
        for dot in range(int(lightdots)):
            dots[dot] = (0,80,0)
    elif (colorOn >100) and (colorOn <=200):
        lightdot = (colorOn-100)/16.7  #rate >100
        dotRemainder = lightdot - int(lightdot)
        partialdot = int (80*dotRemainder)
        print(partialdot)
        for dot in range(5):
            dots[dot] = (50,50,0)
        if lightdot < 1:
            dots[5] = (partialdot,0,0)
        else:
            dots[5] =(80,0,0)
            if lightdot <2:
                dots[6] = (partialdot,0,0)
            else:
                dots[6]=(80,0,0)
                dots[7] = (partialdot,0,0)

def led_strip_lvl(colorOn):
    lightdots = colorOn/12.5
    for dot in range(int(lightdots+1),8):   
        dots[dot] = (0,0,0)
    
    for dot in range(int(lightdots)):
        dots[dot] = (0,0,80)
    
    dotRemainder = lightdots - int(lightdots)
    partialdot = int (60*dotRemainder)
    
    dots[int(lightdots)] = (0,0,partialdot)
    
def progress_led(j):
    j= j% 8 
    for i in range (8):         
        if i <= j:
            dots[i] = (0,0,30)
        else:
            dots[i] = (0,0,0)
            

def reduce_rate(CDRArate):
    
    if (CDRArate > 0):
        CDRArate -= .5
        dict_rate = {"CDRA-rate":int(CDRArate)}
        r.xadd("CDRA",dict_rate)
    return CDRArate
    
def get_redis(equip_stream):
    raw_data = r.xrevrange(equip_stream,"+","-",1)
    #print(raw_data, "raw data")
    dict_info=((raw_data[0][1]))
    #print(dict_info)
    for (thevalue) in dict_info.values():
        valueX = float(thevalue)
        value = int(valueX)
    return value

if __name__ == '__main__':
   
    try:
        main()
    except KeyboardInterrupt:
        print ("interrupt - ending")
        ser.write(b'A')
        sleep(1)
        print("write A to arduino  ABORT!")
        led_bulb("none")
        led_strip(0)
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="black", fill="black")
        pass
   
    finally:
        GPIO.cleanup()
