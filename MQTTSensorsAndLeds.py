# updated Tuesday Code 20/1/26
import sys, math
from time import sleep
import time

#set global variables
ledState = True
ledNewState = True
paused = False
button = None

def picocheck(): #this checks it's running on a pico
    assert('rp2' in sys.platform), "function for rasp Pico only"
    print("Raspberry pico confirmed")

def pauseFunc(topic, msg): # there's a button on the dashboard to pause until the button on the breadboard's pushed.
    global paused, button, client
    if msg == b'PAUSE':
        print("Pause! Press the yellow button to resume")
        while button.value() == 1: #button value 1 when not pressed, 0 when pressed
            sleep(0.05)
            client.check_msg()
        
def ledFunc(topic, msg): # this is to receive a message from the broker to turn LED on and off
    global ledState, client, ledTopic
    print(f'{topic} received with Message {msg}')
    if msg == b'ON':
        ledState = True
    elif msg == b'OFF':
        ledState = False
    print(f'News Flash! led is now {ledState}')
    client.publish(ledTopic, 'ON' if ledState else 'OFF')

def yellowFunc(topic, msg): # this is to receive a message from the broker to turn the LED on depending on light levels
    global yellowLed
    print(f'{topic} received with Message {msg}')
    if msg == b'ON':
        yellow.value(1)
    elif msg == b'OFF':
        yellow.value(0)
    print(f'News Flash! yellow led is now {msg}')

def talkFunc(topic, msg): # this is to receive a message from the app via the broker
    print(f'{topic} received with Message {msg}')   

def readTemp(adc): # Read the temp from the thermistor resistance
    Vout = (3.3/65535)*(adc)
    # Steinhart Constants
    A = 0.0009032679
    B = 0.000248772
    C = 0.0000002041094
        # Calculate Resistance
    Vin = 3.3
    Ro = 10000
    try:
        Rt = (Vout * Ro) / (Vin - Vout)
        # Rt = 10000  # Used for Testing. Setting Rt=10k should give TempC=25
    except:
        # probably had a divide by zero for Vin == Vout
        Rt = 200
    # Steinhart - Hart Equation
    TempKelvin = 1 / (A + (B * math.log(Rt)) + C * math.pow(math.log(Rt), 3))

    # Convert from Kelvin to Celsius
    TempCelsius = TempKelvin - 273.15
    return TempCelsius

def masterCallback(topic, msg):
    if b'ledNewState' in topic:
        ledFunc(topic, msg)
    elif b'talkBack' in topic:
        talkFunc(topic, msg)
    elif b'yellowLed' in topic: #@
        yellowFunc(topic, msg)
    elif b'pause' in topic:
        pauseFunc(topic, msg)


#this is the start of the programme
try: #1st check if it's running on a pico
    picocheck()
except:
    print("not running on a pico")
else: #import libraries
    from machine import Pin, PWM, ADC
    import network
    from mqtt import MQTTClient
   
    SSID = 'brackenhillc' #set-up wifi # college*
    PWD = '1broches'#*
    
#    SSID = 'PLUSNET-3PC2PM' #home settings*
#    PWD = 'GM67xEANVpT9gA'#*
    
    thingName = 'JennysThing' # change and make this unique. This is the address for this specific IoT device
    #broker = '192.168.2.207' #Andys box change for college
    #broker = 'test.mosquitto.org' #use this at home instead
    broker ="broker.emqx.io" #this is for the phone app. Doesn't work on college network - works at home
   
#set-up topics we're publishing to
    tempTopic = thingName+'/temperature'
    lightTopic = thingName+'/lightLevel'
    humidTopic = thingName+'/humidity'
    ledTopic = thingName+'/ledState'
    ledNewTopic = thingName+'/ledNewState'
    talkTopic = thingName+'/talkBack'
    pauseTopic = thingName+'/pause'
    yellowTopic = thingName+'/yellowLed'

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
   
# Connect to the wifi access point
   
    wlan.connect(SSID, PWD)
    print("Connecting to wifi")
    while not wlan.isconnected():
        sleep(0.001)
    print("Connected to wifi, Ip address is: ", wlan.ifconfig()[0])

    client = MQTTClient(thingName, broker)
   
    try:
        client.connect()
        print('Connected to broker successfully')
    except:
        print('Failed to connect to Broker')
        raise

# set up the pins
    lightLevel = ADC(26)
    tempVoltage = ADC(27)
    humidityVoltage = ADC(28)
    humidityDrive = PWM(22)
    humidityDrive.freq(1000)
    humidityDrive.duty_u16(32767)
    led = Pin(15, Pin.OUT)
    flashTimer = time.ticks_ms()
    flashInterval = 500 #ms
    button = Pin(14, Pin.IN, Pin.PULL_UP) # Button (PULL_UP means connect button to GND; pressed = 0)
    yellow = Pin(13, Pin.OUT)
    #led = PWM(15)
    #led.freq(100)

    client.set_callback(masterCallback)
    client.subscribe(ledNewTopic)
    client.subscribe(talkTopic)
    client.subscribe(pauseTopic)
    client.subscribe(yellowTopic)

    while True:
        now = time.ticks_ms()
# Set the Led flashing
        if ledState:
            if time.ticks_diff(now, flashTimer) > flashInterval:
                flashTimer = now
                led.toggle()
        else:
            led.value(0)
            #for d in range (0, 65536, 512): # increasing the brightness
                #led.duty_u16(d)
                #sleep(0.001)
            #for d in range (65536, 0, -512): # decrease the brightness
                #led.duty_u16(d)
                #sleep(0.001)
        client.check_msg()
        
#lightLevel lightTopic
        data = str(int(lightLevel.read_u16()/655.35))
        print(f"Light level voltage is {data}%")
        client.publish(lightTopic, data)
        client.check_msg()
        
#humidity humidTopic
        data = str(int(round(humidityVoltage.read_u16()/655.36))) # read the humidity sensor output
        print(f"The Relative Humidity is {data}%" )
        client.publish(humidTopic, data)
        client.check_msg()      
        
#temperature tempTopic
        data = str(round(readTemp(tempVoltage.read_u16()),1))
        print(f"Current temp is {data}C") # if using thermistor
        client.publish(tempTopic, data)
        client.check_msg()
        
        sleep(1)