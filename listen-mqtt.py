#!/usr/bin/python3

"""
listen-mqtt - Simple simplisafe-rf to MQTT bridge. Requires config.json based off of config.json.template
"""

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
from simplisafe.pigpio import Transceiver
from simplisafe.messages import KeypadHomeRequest, KeypadAwayRequest, KeypadAlarmPinRequest

import time
import datetime
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import threading
from threading import Thread
import sys
import socket

sequence = 0x1
published_serials = []

#MQTT callbacks
def on_connect(client, userdata, flags, rc):
    if rc==0:
        client.connected_flag=True #set flag
        client.bad_connection_flag=False
        tprint("Connected to " + auth["username"]+ "@"+ host+":"+ str(port)+ " with result code "+str(rc))
        client.subscribe("simplisafe/#", 0)
    else:
        tprint("Unable to connect to " + auth["username"]+ "@"+ host+":"+ str(port)+ " with result code "+str(rc))
        client.bad_connection_flag=True

def on_message(client, userdata, message):
    global exit_flag
    try:
        if message.payload:
            payload = json.loads(message.payload.decode("utf-8"));
        else:
            payload = None
    except Exception as error:
        print("Exception " + str(error))
        payload = None
    # skip any messages published by this node
    if payload:
        if ("reporting_node" in payload and payload["reporting_node"] == computername):
            return
        print("message from: ", payload['reporting_node']);
        print("message received " ,str(payload))
    print("message topic=",message.topic)
    print("message qos=",message.qos)
    print("message retain flag=",message.retain)
    if (message.topic == "simplisafe/command/stop"):
        tprint("Received stop command; exiting")
        exit_flag=True
    elif (message.topic == "simplisafe/command/disarm"):
        tprint("Received disarm command")
        disarm()
    elif (message.topic == "simplisafe/command/arm"):
        tprint("Received arm command")
        disarm()
        arm()
    elif (message.topic == "simplisafe/command/armaway"):
        tprint("Received arm away command")
        disarm()
        arm(away=True)

def on_disconnect(client, userdata, rc):
    if rc != 0:
        tprint("Unexpected disconnect; retrying")
    else:
        client.connected_flag=False
        client.disconnect_flag=True

# Monitor function
def monitorSimplisafe():
    count = 0
    global published_serials
    global txr433
    while True:
        try:
            msg = txr433.recv() # Returns when a valid message is received and parsed
            time.sleep(1)
            count += 1
            print(str(count) + "\t" + datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+"\n"+str(msg))
            origin_type = msg.origin_type.__class__.key(msg.origin_type)
            sn = msg.sn
            event_type = msg.event_type.__class__.key(msg.event_type)
            seq = msg.sequence
            topic = "simplisafe/" + origin_type + "/" + sn
            payload = {'origin_type':origin_type, 'event':event_type, 'seq':seq, 'reporting_node':computername}
            if sn.lower() not in published_serials:
                publish_discovery(origin_type, sn, payload, topic)
            publish.single(topic, payload=json.dumps(payload), client_id=computername, auth=auth, port=port, hostname=host, retain=True)
            if event_type in offdelay:
                t1 = threading.Timer(offdelay[event_type], publish.single, [topic], {'payload':json.dumps({'origin_type':origin_type, 'event':'OFF', 'seq':seq, 'reporting_node':computername}), 'client_id':computername, 'auth':auth, 'port':port, 'hostname':host, 'retain':True})
                t1.start()
        except Exception as error:
            print("Exception " + str(error))

def publish_discovery(origin_type, sn, payload, topic):
    global published_serials
    global known_serials
    if not autodiscovery_topic and (not discover_serials or
        (sn.lower() not in known_serials)):
        print("Not publishing discovery for " + str(sn))
        return
    print("Publishing discovery for " + str(sn))
    simplisafe_key = {
        "ENTRY_SENSOR": {
            "device_class":"opening",
            "payload_on":"OPEN",
            "payload_off":"CLOSED",
        },
        "MOTION_SENSOR": {
            "device_class":"motion",
            "payload_on":"MOTION",
            "payload_off":"OFF",
            "off_delay": 15,
        },
        "SMOKE_DETECTOR": {
            "device_class":"smoke",
            "payload_on":"SMOKE",
            "payload_off":"OFF",
            "off_delay": 15,
        },
        "GLASSBREAK_SENSOR": {
            "device_class":"sound",
            "payload_on":"GLASSBREAK",
            "payload_off":"OFF",
            "off_delay": 15,
        }
    }
    manufacturer="SimpliSafe"
    device_name = "{} {}".format(
        origin_type,
        sn
    )
    device_topic = "{}_{}".format(
    origin_type,
    sn
    )
    unique_id = "simplisafe_{}_{}".format(
        origin_type.lower(),
        sn.lower()
    )
    # "$AUTODISCOVERY_PREFIX/binary_sensor/$DEVICE_NAME/motion/config"
    config_topic = "{}/binary_sensor/{}/{}/config".format(
        autodiscovery_topic,
        device_topic,
        simplisafe_key[origin_type]['device_class']
    )
    payload = {
        "name": unique_id,
        "unique_id": unique_id,
        "value_template" : "{{ value_json.event }}",
        "device": {
            "identifiers": (manufacturer, manufacturer),
            "manufacturer": manufacturer,
            "name": manufacturer,
            "sw_version": 1
            },
        "state_topic": topic,
        "device_class": simplisafe_key[origin_type]['device_class']
    }
    payload.update(simplisafe_key[origin_type])
    publish.single(config_topic, payload=json.dumps(payload), client_id=computername, auth=auth, port=port, hostname=host, retain=True)
    published_serials.append(sn.lower())

def arm(away=False, retry=3):
    if not pin:
        print("Pin is empty; arm ignored")
        return
    if not sn:
        print("Serialnumber is empty; arm ignored")
        return
    try:
        msg = (KeypadHomeRequest(sn, sequence) if not away else
            KeypadAwayRequest(sn, sequence))
        send(msg, retry)
    except Exception as error:
        print("Exception " + str(error))

def send(msg, retry=3, delay=3):
    global sequence
    global txr433
    try:
        for x in range(0, retry):
            sequence = (sequence + 1 % 16)
            txr433.send(msg)
            time.sleep(delay)
    except Exception as error:
            print("Exception " + str(error))
    except pigpio.error as error:
            print("Retrying due to pigpio error " + str(error))
            send(msg, retry, delay)

def disarm(retry=3, delay=0.1):
    if not pin:
        print("Pin is empty; disarm ignored")
        return
    if not sn:
        print("Serialnumber is empty; disarm ignored")
        return
    try:
        msg = KeypadAlarmPinRequest(sn, sequence, pin=pin)
        send(msg, retry, delay)
    except Exception as error:
        print("Exception " + str(error))

def tprint(msg):
    print(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')+ ": " + msg)

#Main
if __name__ == "__main__":
# Load json config
    try:
        with open('config.json') as json_data_file:
            cfg = json.load(json_data_file)
        RX_433MHZ_GPIO = cfg["receive_GPIO"]
        TX_433MHZ_GPIO = cfg["transmit_GPIO"]
        sn = cfg["keypad_SN"]
        pin = cfg["disarm_pin"]
        autodiscovery_topic = cfg["autodiscovery_topic"]
        discover_serials = cfg["discover_serials"]
        known_serials = cfg["known_serials"]
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
    global txr433
    txr433 = Transceiver(rx=RX_433MHZ_GPIO, tx=TX_433MHZ_GPIO)
    simplisafeThread = Thread(target = monitorSimplisafe)
    simplisafeThread.setDaemon(True)
    simplisafeThread.start()
#Connect to MQTT
    client = mqtt.Client()
    client.connected_flag=False #set flag
    client.bad_connection_flag=False
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
            print ("Keyboard interrupt detected")
            break
    client.loop_stop()
    client.disconnect()
    print ("Exiting")
    sys.exit()
