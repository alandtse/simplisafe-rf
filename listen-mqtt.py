#!/usr/bin/python3

"""
listen-mqtt - Simple simplisafe-rf to MQTT bridge. Requires config.json based off of config.json.template
"""

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
import RFUtils
import SimpliSafe
import time
import datetime
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import threading
from threading import Thread
import sys

#MQTT callbacks
def on_connect(client, userdata, flags, rc):
    print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+" Connected to " + auth["username"]+ "@"+ host+":"+ str(port)+ " with result code "+str(rc))
def on_message(client, userdata, message):
    print("message received " ,str(message.payload.decode("utf-8")))
    print("message topic=",message.topic)
    print("message qos=",message.qos)
    print("message retain flag=",message.retain)
    if (message.topic == "simplisafe/command/stop"):
       print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+" Received stop command; exiting") 
       sys.exit()

# Monitor function
def monitorSimplisafe():
    count = 0
    while True:
        try:
            msg = RFUtils.recv(RX_433MHZ_GPIO) # Returns when a valid message is received and parsed
            count += 1 
            print(str(count) + "\t" + datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+"\n"+str(msg))
            origin_type = msg.origin_type.__class__.key(msg.origin_type)
            sn = msg.sn
            event_type = msg.event_type.__class__.key(msg.event_type)
            seq = msg.sequence
            topic = "simplisafe/" + origin_type + "/" + sn
            publish.single(topic, payload=json.dumps({'origin_type':origin_type, 'event':event_type, 'seq':seq}), client_id="simplisafe", auth=auth, port=port, hostname=host)
            if event_type in offdelay:
                t1 = threading.Timer(offdelay[event_type], publish.single, [topic], {'payload':json.dumps({'origin_type':origin_type, 'event':'OFF', 'seq':seq}), 'client_id':"simplisafe", 'auth':auth, 'port':port, 'hostname':host}) 
                t1.start() 
        except Exception as error: 
            print("Exception " + str(error))

#Main
if __name__ == "__main__":
# Load json config
    try:
        with open('config.json') as json_data_file:
            cfg = json.load(json_data_file)
        RX_433MHZ_GPIO = cfg["receive_GPIO"] 
        auth = cfg["auth"]
        host = cfg["host"]
        port = cfg["port"]
        offdelay = cfg["offdelay"]
    except (FileNotFoundError, IOError):
        print("config.json not found")
        sys.exit(1)
    except KeyError as e:
        print("Value missing from config.json:" + str(e))
        sys.exit(1)
#Start monitoring
    simplisafeThread = Thread(target = monitorSimplisafe)
    simplisafeThread.setDaemon(True)
    simplisafeThread.start()
#Connect to MQTT
    client = mqtt.Client()
    client.on_message = on_message  
    client.on_connect = on_connect
    client.username_pw_set(auth["username"], auth["password"])
    client.connect(host, port)
    client.subscribe("simplisafe/#", 0)
    while True:
        try:
            client.loop()
            time.sleep(1)
        except Exception as error:
            print("Exception " + str(error))
        except KeyboardInterrupt:
            break
            print ("Exiting")
