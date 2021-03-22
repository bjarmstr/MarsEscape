
/* 

Operates the pressure transducer and the relay valve to the air compressor
The pressure is sent to the raspberry pi using serial communication



*/
/*
  Library for the CAP1203
  By: Andrea DeVore
  SparkFun Electronics

  Do you like this library? Help support SparkFun. Buy a board!

  This sketch uses the SparkFun_CAP1203 library to initialize
  the capacitive touch sensor and to stream which pad detects
  a touch. This sketch waits until user removes finger from the
  pad to detect the next touch.

  License: This code is public domain, but if you see me
  (or any other SparkFun employee) at the local, and you've
  found our code helpful, please buy us a round (Beerware
  license).

  Distributed as is; no warrenty given.
*/

#include <SparkFun_CAP1203_Registers.h>
#include <SparkFun_CAP1203_Types.h>
#include <Wire.h>

CAP1203 sensor;     // Initialize capacitive touch sensor

bool piReady = false;

//******for CO2 Leak Scenario *********//
const int numVals = 50;  //number of readings in average pressure calc

const int maxPressure = 135;   //275 pressure relief value goes
const int lowPressure = 110;  //105 no pressure
const int highPressure = 125; 
const int allowableDrop = 5; //the pipe is leaking if pressure drops more than this value during check
const int waitTime = 8000; // duration of pressure check to determine pressure drop

int analogPin = A0; // pressureSensor
                    // other wires to ground and +5V
int K1in = 7; // pin for relay K1 for compressor control
              // no ground wire to arduino just pin7 & VCC. JD-VCC & ground to 5V power source

int valvePin = 8; //pressure valve pin

int fusePin = 6; // pin to detect if fuse has been replaced
int LEDPin = 5; //pin provides power to the power switch LED

              
int pressureChk = 0;  // 
bool compressorOn = false;
unsigned long checkTime = millis();
unsigned long previousTime = millis();

bool CO2LeakCheck = false;

int countVals = 1;
int pressureVal;      // the readings from the analog input
int valIndex = 0;     // the index of the current reading
int total = 0;      // the running total
int avPressure = 0;    // the average

unsigned long startleakTimer = millis();
int firstCheck = false;
int startPressure = 0;



      

void setup() {
  Wire.begin();         // Join I2C bus
  Serial.begin(9600);   // Start serial for output
  // Setup sensor
  if (sensor.begin() == false) {
    Serial.println("Not connected. Please check connections and read the hookup guide.");
    while (1);
  }
  else {
    Serial.println("Connected!");
  }
  sensor.setSensitivity(SENSITIVITY_8X);

  
  digitalWrite(K1in, HIGH);
  pinMode(K1in, OUTPUT);  //pin defaults to INPUT, set to high first so it doesn't go low while initializing
  pinMode(valvePin,OUTPUT);
  digitalWrite(valvePin, HIGH);
  pinMode(fusePin, INPUT_PULLUP);
  pinMode (LEDPin, OUTPUT);
  startupPressure();
  startupFuseCheck();
  
}



void loop(){
    touchSensor();
    if (piReady == true){  //don't write to serial until pi program is running
      if (CO2LeakCheck == true){
        avgPressureVal();
        if (countVals == 1){   //new average value is available
        checkLeak();
        }
      }
      else {
        checkTime = millis();
        if (checkTime - previousTime > 2000){
           pressureCheck();
           previousTime = checkTime;
        }
      }
    }
    instructionsFromPi();
}



void instructionsFromPi() {
 if (Serial.available() > 0) {
   char incomingCharacter = Serial.read();
   switch (incomingCharacter) {
     case 'A':
        piReady = false;
     break;
     case 'B':
        piReady = true;
        Serial.println("pi Ready");
     break;
     
     case 'L':
        //CO2 Leak - Open Pressure Valve
        Serial.println("CO2Leak");
        digitalWrite(valvePin, LOW);

      break;

      case 'C':
        //check if leak fixed
        CO2LeakCheck = true;
        firstCheck = true;
        Serial.println("C Arduino Leak Check");
      break;

      
     case 'S':
        //Circuit Board Failure 
        Serial.println("CircuitBoardFailure");
        digitalWrite(LEDPin, LOW);
        int fuseCircuit = digitalRead(fusePin);
        if (fuseCircuit == 1){
          Serial.println("FuseFixed");
          digitalWrite(LEDPin, HIGH);
        }
     break;
  }
 }
}

void avgPressureVal(){
    pressureVal = analogRead(analogPin);  
    total = total + pressureVal;
     if (countVals == numVals){
        avPressure = total / numVals;
        //Serial.println(average);
        total = 0;
        countVals = 0;
     }
   countVals++;
}


void checkLeak(){
    if (firstCheck == true){
        pressureUp(); 
        delay(500); //allow pressure to maximize before checking
        firstCheck = false;
        int ptotal = 0;
        for (int i = 1; i<= numVals; i++){
            pressureVal = analogRead(analogPin);  
            ptotal = ptotal + pressureVal;
        }
        avPressure = ptotal / numVals;
        //Serial.println(average);     
      startPressure = avPressure;
      Serial.print("startPressure");
      Serial.println(startPressure);
      startleakTimer = millis();   
    }
    unsigned long timeNow = millis();
    unsigned long timer = startleakTimer + waitTime;
    if ( (startleakTimer + waitTime) < timeNow ){
             if ((startPressure-avPressure)>allowableDrop){  
                Serial.print("STILL LEAKING");
                Serial.print(avPressure); Serial.print("avP,startP"); Serial.print(startPressure);
                Serial.println("F");
                delay(250);
                Serial.println("F");
             }       
             else {
                   Serial.print(avPressure); Serial.print("avP,startP"); Serial.print(startPressure);
                   Serial.println("leak fixed");
                   Serial.println("OK");
                   
             }
            CO2LeakCheck = false;   
        
          delay(100);
  }
}

  

void pressureCheck(){
  //keep the pressure between the low and high pressure values

  pressureChk = analogRead(analogPin);  // read the input pin
  Serial.println(pressureChk);          // send pressure data to the pi for tracking  
  if (pressureChk < lowPressure) {
      digitalWrite(K1in, LOW);
      compressorOn = true;
    }
    else if (pressureChk > highPressure) {
      digitalWrite(K1in, HIGH);  //the relay is off in HIGH state
      compressorOn = false;
    }
}


void touchSensor(){
  if (sensor.isLeftTouched() == true) {
    Serial.println("Left");
    while (sensor.isLeftTouched() == true);   // Wait until user removes finger
  }

  if (sensor.isMiddleTouched() == true) {
    Serial.println("Middle");
    while (sensor.isMiddleTouched() == true); // Wait until user removes finger
  }

  if (sensor.isRightTouched() == true) {
    Serial.println("Right");
    while (sensor.isRightTouched() == true); // Wait until user removes finger
  }
}





void startupPressure(){
  //set-up pressure in tank to maxPressure
 
  if (piReady == false){
    delay(15000);  //compressor pulls too much power to run when power is first turned on*******put back to higher number****
    Serial.println ("done 15k");
    pressureUp();
   }
  
}

void pressureUp(){
    unsigned long startTime;
    unsigned long presentTime;
    startTime = millis();
    pressureChk = analogRead(analogPin); 
    while (pressureChk < maxPressure){
        int ptotal = 0;
        for (int i = 1; i<= numVals; i++){
            pressureChk = analogRead(analogPin);  
            ptotal = ptotal + pressureChk;
        }
        pressureChk = ptotal / numVals;
        //Serial.println(pressureChk);          // debug value
           if (pressureChk < maxPressure) {
              digitalWrite(K1in, LOW);
           }
           else {
              digitalWrite(K1in, HIGH); //turn off compressor
              delay(1000);  //wait so signal has time to turn compressor off
           }
        presentTime = millis();
        if ( (presentTime - startTime) > 5000) { //something is wrong -stop the compressor it has been running too long
           pressureChk = maxPressure;
           digitalWrite(K1in, HIGH); //turn off compressor
           Serial.println ("compressor running too long, is pressure sensor working correctly?");
        }  
    }
    Serial.println("pressure good");
  
  }

void startupFuseCheck(){
  int fuseCircuit = digitalRead(fusePin);
  digitalWrite(LEDPin, HIGH);
  if (fuseCircuit == 1){
      Serial.println("Fuse Functioning");  
      
  }
  else if (fuseCircuit == 0) {
      Serial.println("Fuse is Blown");
      delay(2000);
      digitalWrite(LEDPin, LOW);
      delay(1000);
      digitalWrite(LEDPin, HIGH);
  }

}

 

  
    
