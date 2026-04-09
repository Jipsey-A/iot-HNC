#Code 1. This measures temperature, compares it to a pre-set threshold, and illuminates an LED accordingly.

import sys, math
#sys allows us to check we're on a Pico. math is needed for temperature calculations
from time import sleep
#sleep allows us to slow things down with a pause after each round
from machine import ADC, Pin
#ADC and Pin tell the code where to look for hardware

#preset thresholds
tempThreshold = 20 #degrees C

#setup hardware
tempLevel = ADC(27) # thermister into pin 27
redLed = Pin(15, Pin.OUT) #red LED into pin 15 responds to temp

#Check it's running on a pico
def picocheck():
    assert('rp2' in sys.platform), "function for rasp Pico only"
    print("Raspberry pico confirmed")

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
picocheck()

while True:
#start by reading the sensor
    
    #read the temperature from the thermistor
    #use readTemp() to calibrate and convert to C. Rnd to 1 dp
    #print the temp reading
    tempC = round(readTemp(tempLevel.read_u16()),1)
    print(f"Current temp is {tempC}C")

#now instruct the activator (in this case a red LED)
#to respond depending on comparison of reading with threshold
    #if tempC is less than temp threshold turn heater (represented here by red LED) on
    #if tempC is not less than temp threshold then turn red LED off
    redLed.value(tempC < tempThreshold)
    if tempC < tempThreshold:
        print("Temperature lower than threshold - turn heater (Red LED) on")
    else:
        print ("Temperature exceeds threshold - turn heater (Red LED) off")
#A pause to slow it all down a little before it returns to the start of this main loop.
    sleep(1)
    print("****")
    
