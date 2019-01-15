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
import socket

#MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc==0:
        client.connected_flag=True #set flag
        client.bad_connection_flag=False
        print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+" Connected to " + auth["username"]+ "@"+ host+":"+ str(port)+ " with result code "+str(rc))
        client.subscribe("simplisafe/#", 0)
    else:
        print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+" Unable to connect to " + auth["username"]+ "@"+ host+":"+ str(port)+ " with result code "+str(rc))
        client.bad_connection_flag=True

def on_message(client, userdata, message):
    payload = json.loads(message.payload.decode("utf-8"));
    # skip any messages published by this node
    if ("reporting_node" in payload and payload["reporting_node"] == computername):
        return
    print("message from: ", payload['reporting_node']);
    print("message received " ,str(payload))
    print("message topic=",message.topic)
    print("message qos=",message.qos)
    print("message retain flag=",message.retain)
    if (message.topic == "simplisafe/command/stop"):
        print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+" Received stop command; exiting")
        exit_flag=True

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+" Unexpected disconnect; retrying")
    else:
        client.connected_flag=False
        client.disconnect_flag=True

# Monitor function
def monitorSimplisafe():
    count = 0
    while True:
        try:
            msg = RFUtils.recv(RX_433MHZ_GPIO) # Returns when a valid message is received and parsed
            time.sleep(1)
            count += 1 
            print(str(count) + "\t" + datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+"\n"+str(msg))
            origin_type = msg.origin_type.__class__.key(msg.origin_type)
            sn = msg.sn
            event_type = msg.event_type.__class__.key(msg.event_type)
            seq = msg.sequence
            topic = "simplisafe/" + origin_type + "/" + sn
            publish.single(topic, payload=json.dumps({'origin_type':origin_type, 'event':event_type, 'seq':seq, 'reporting_node':computername}), client_id=computername, auth=auth, port=port, hostname=host, retain=True)
            if event_type in offdelay:
                t1 = threading.Timer(offdelay[event_type], publish.single, [topic], {'payload':json.dumps({'origin_type':origin_type, 'event':'OFF', 'seq':seq, 'reporting_node':computername}), 'client_id':computername, 'auth':auth, 'port':port, 'hostname':host, 'retain':True})
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
    exit_flag = False
    computername = socket.gethostname()
    simplisafeThread = Thread(target = monitorSimplisafe)
    simplisafeThread.setDaemon(True)
    simplisafeThread.start()
#Connect to MQTT
    mqtt.Client.connected_flag=False
    mqtt.Client.bad_connection_flag=False #
    client = mqtt.Client()
    client.on_message = on_message  
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.username_pw_set(auth["username"], auth["password"])
    try:
        client.connect(host, port)
    except:
        print("Connection failed")
    client.loop_start()
    while not exit_flag: #wait in loop
        try:
            time.sleep(1)
        except Exception as error:
            print("Exception " + str(error))
        except KeyboardInterrupt:
            print ("Exiting")
            break
    client.loop_stop()
    client.disconnect()
    sys.exit()
