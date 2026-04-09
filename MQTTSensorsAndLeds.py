import sys, math
#sys allows us to check we're on a Pico. math is needed for temperature calculations
from time import sleep
#sleep allows us to slow things down with a pause after each round
from machine import ADC, Pin, PWM
#ADC and Pin tell the code where to look for hardware
import network #needed for wifi set-up
from mqtt import MQTTClient #needed for mqtt

#preset thresholds
tempThreshold = 20 #degrees C
lightThreshold = 50 #percent
humidityThreshold = 40 #percent

#set-up MQTT info
SSID = 'PLUSNET-3PC2PM' #home settings*
PWD = 'GM67xEANVpT9gA'#*
thingName = 'JennysThing' # change and make this unique. This is the address for this specific IoT device
broker ="broker.emqx.io" #this is for the phone app.

#set-up topics we're publishing to
tempTopic = thingName+'/temperature'
lightTopic = thingName+'/lightLevel'
humidTopic = thingName+'/humidity'
tempThresholdTopic = thingName + '/tempThreshold'
lightThresholdTopic = thingName + '/lightThreshold'
humidThresholdTopic = thingName + '/humidThreshold'

#setup hardware
#sensors
tempLevel = ADC(27) # thermister as a voltage divider into pin 27
lightLevel = ADC(26) # Photodiode as a voltage divider into pin 26
humidityLevel = ADC(28) # humidity sensor on pin 28
humidityDrive = PWM(11) #humidity sensor is driven by a pulse from pin 11
humidityDrive.freq(1000) #this sets the frequency of the pulse to 1kHz
humidityDrive.duty_u16(32767) #this sets PWM to be on 50% (32767/65535)

#actuators
redLed = Pin(15, Pin.OUT) #red LED into pin 15 responds to temp
yellowLed = Pin(14, Pin.OUT) #yellow LED into pin 14 responds to light level
blueLed = Pin(13, Pin.OUT) #blue LED into pin 13 responds to humidity level

#Check it's running on a pico
def picocheck():
    assert('rp2' in sys.platform), "function for rasp Pico only"
    print("Raspberry pico confirmed")

# Connect to the wifi access point
def wifi():
    #sets up the wifi info and request a connection
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PWD)
    #Wait for connection
    print("Connecting to wifi")
    while not wlan.isconnected():
        sleep(0.2)
        print("connecting....")
    #Once connected let me know
    print("Connected to wifi, Ip address is: ", wlan.ifconfig()[0])
    #Create MQTT client to send and receive
    client = MQTTClient(thingName, broker, 1883
    )
    client.set_callback(masterCallback)
    #connect to broker   
    try:
        client.connect()
        print('Connected to MQTT broker successfully')
    except:
        print('Failed to connect to Broker')
        raise
    #Subscribe to topics - this tells it to look out for messages with this in it's topic section
    client.subscribe(tempThresholdTopic)
    client.subscribe(lightThresholdTopic)
    client.subscribe(humidThresholdTopic)
    
    return client

#This tells the Pico what to do when it receives a message that it's subscribed to
def masterCallback(topic, msg):
#make variables global so they are modified throughout the code
    global tempThreshold, lightThreshold, humidityThreshold

#convert bytes to strings so they can be compared
    topic = topic.decode()
    msg = msg.decode()
    
#let's me know we've received a message and what it says
    print("Received:", topic, msg)
    
#update thresholds accordingly & immediately. Uses 'try' and 'except' in case it receives something unexpected in the data field
    if "tempThreshold" in topic:
        try:
            tempThreshold = int(msg)
            print("New temperature threshold:", tempThreshold)
        except:
            print("Invalid temp threshold received")
    elif "lightThreshold" in topic:
        try:
            lightThreshold = int(msg)
            print("New light threshold:", lightThreshold)
        except:
            print("Invalid light threshold received")
    elif "humidThreshold" in topic:
        try:
            humidityThreshold = int(msg)
            print("New humidity threshold:", humidityThreshold)
        except:
            print("Invalid humidity threshold received")

#read thermistor, calibrate and convert to degrees C
def readTemp(adc_value):
    Vout = (3.3/65535)*(adc_value)
    # Steinhart Constants as set by hardware datasheet
    A = -0.00212447066499

    B = 0.00072486479719

    C = -0.00000150782459

        # Calculate Resistance
    Vin = 3.3
    Ro = 10200 #this is the size of resistor in voltage divider circuit
    try:
        Rt = (Vout * Ro) / (Vin - Vout)
    except:
        Rt = 200 #this is a work around in case Vin-Vout = o
    
    # Steinhart - Hart Equation
    TempKelvin = 1 / (A + (B * math.log(Rt)) + (C * math.pow(math.log(Rt), 3)))

    # Convert from Kelvin to Celsius
    TempCelsius = TempKelvin - 273.15
    return TempCelsius

# Start of main loop
#check  that it's running on the correct hardware
try:
    picocheck()
except:
    print("not running on a pico")


try:
    client = wifi()
except:
    print("wifi not connecting")

while True:
# This helps me to see when we return to this point in the code
    print("****")     
    
#start by reading the sensors
    #for each sensor:
      #read the sensor
      #convert to useful figure inc rounding to appropriate dp
      #print the reading (useful for debugging!)
      #send the reading out as a message via MQTT jennysThing/___Topic
      #check if any messages received
    
    #TEMPERATURE - tempTopic
    tempC = round(readTemp(tempLevel.read_u16()),1)
    print(f"Current temp is {tempC}C")
    client.publish(tempTopic, str(tempC))
    client.check_msg()
    
    #LIGHT LEVEL - lightTopic
    lightPct = int(lightLevel.read_u16())/655.35
    print(f"Light level is {lightPct}%")
    client.publish(lightTopic, str(int(lightPct)))
    client.check_msg()    

    #HUMIDITY LEVEL - humidTopic
    humidityPct = int(100-(humidityLevel.read_u16())/655.35)
    print(f"Relative humidity is {humidityPct}%")
    client.publish(humidTopic, str(int(humidityPct)))
    client.check_msg()     

#now instruct the activator to respond depending on comparison of reading with threshold
    #TEMPERATURE - heater represented here by red LED. Turn on if tempC<threshold, otherwise off
    redLed.value(tempC < tempThreshold)
    if tempC < tempThreshold:
        print("Temperature lower than threshold - turn heater (Red LED) on")
    else:
        print ("Temperature exceeds threshold - turn heater (Red LED) off")
    
    #LIGHT main light represented by yellow LED. Turn on if light level is dim     
    yellowLed.value(lightPct < lightThreshold)
    if lightPct < lightThreshold:
        print("Light is dimmer than threshold - turn main light (Yellow LED) on")
    else:
        print ("Light is brighter than threshold - turn main light (Yellow LED) off")
    
    #HUMIDITY extractor represeted by blue LED. turn on if too humid    
    blueLed.value(humidityPct > humidityThreshold)
    if humidityPct < humidityThreshold:
        print("Humidity is lower than threshold - turn extractor fan (Blue LED) off")
    else:
        print ("Humidity is higher than threshold - turn extractor fan (blue LED) on")
            
#A pause to slow it all down a little before it returns to the start of this main loop.
    sleep(1)
    