#!/usr/bin/python3
import RFUtils
import SimpliSafe
import time
import datetime

RX_433MHZ_GPIO = 22 # Connected to DATA pin of 433MHz receiver

# 433MHz traffic monitor:

while True:
    try:
        msg = RFUtils.recv(RX_433MHZ_GPIO) # Returns when a valid message is received and parsed
        print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+"\n"+str(msg))
    except Exception as error: 
        print("Exception " + str(error))
    except KeyboardInterrupt:
        break
print ("Exiting")
