import pcf8574
from   machine import I2C, Pin, Timer
import machine
import micropython # For emergency exception buffer
from   time        import sleep, sleep_ms
from   umqttsimple import MQTTClient
import ujson
import network
import os
import gc

micropython.alloc_emergency_exception_buf(100)

# Constants
TIMEOUT_MS         = 500
WIFI_TIMEOUT_MS    = 3200
LOOP_WAIT_MS       = 50
LOOP_SKIPS         = 10
MIN_FREE_MEM       = 15520
MQTT_KEEPALIVE_SEC = 3
I2C_PIN_NUMBER     = 8

internalLed        = machine.Pin(2, machine.Pin.OUT)

def timeout_callback(t):
    log("WARN", "Operation frozen...Reboot")
    internalLed.off()
    machine.reset()

class GeneralStruct:
    pass

GS             = GeneralStruct()
GS.LOG_LEVEL   = [ "DEBUG", "INFO", "WARN", "ERROR" ]

# Basic Function
def log( Level, msg ):
    if Level in GS.LOG_LEVEL:
        print( "Level: {} Msg: {} ".format(str(Level), str(msg)) )

def StringToList( sep, string, purpose="logLevel" ):
   log("INFO","preparing new list for "+purpose)
   try:
      newList = string.split( sep )
   except:
      log("WARN", ("StringToList No new list, keeping old list ",GS.LOG_LEVEL) )
      newList = []
      return GS.LOG_LEVEL
   if len(newList) > 0:
      log("INFO", ("new list is",newList) )
      return newList
   else:
      log("INFO", ("keeping old list ",GS.LOG_LEVEL) )
      return GS.LOG_LEVEL

def LoadConfig( GS ):
   with open( GS.ConfigFile ) as data_file:
      # data            = ujson.load( str(data_file.readlines()).strip() )
      log( "DEBUG", "Loading conf from file: ["+GS.ConfigFile+"]" )
      GS.data           = ujson.load( data_file )
      GS.CLIENTID       = GS.data["MQTTclientid"]
      GS.USER           = GS.data["MQTTuserid"]
      GS.PSWD           = GS.data["MQTTpasswd"]
      GS.SERVER         = GS.data["MQTTserver"]
      GS.statusMsg      = { "status":"ONLINE" }
      # TOPIC
      GS.IN_CMD_TOPIC   = str(GS.data["MQTT_IN_CMD_TOPIC"]).encode()
      GS.OUT_STATUS     = str(GS.data["MQTT_OUT_STATUS"]).encode()
      # Trigger Msg
      GS.LOG_LEVEL      = StringToList( ',', str( GS.data["LOG_LEVEL"] ) )
      # WIFI Config
      GS.SSIDWIFI       = GS.data["SSIDWIFI"]
      GS.PASSWIFI       = GS.data["PASSWIFI"]

# Messages from Mqtt subscriptions will be delivered to this callback
def sub_cb( topic, msg ):
    log( 'INFO', (topic, msg) )
    if topic == GS.IN_CMD_TOPIC:
       # MsgIn example : '{ "COMMAND": "REBOOT" }'  
       GS.statusMsg["rssi"] = str(GS.station.status('rssi'))
       log("INFO", ( "WIFI rssi: ", GS.statusMsg['rssi'] ) )
       try:
          cmd = ujson.loads( msg )
       except:
          cmd = {}
       if type( cmd ) is not dict:
          log( "WARN", "wrong command format! " + str( msg ))
          cmd = {}
       for k in cmd :
          if k == 'COMMAND' and cmd[k] == 'REBOOT': 
               log( "INFO", "Command is to reboot!" )
               machine.reset()
               sleep_ms( WIFI_TIMEOUT_MS )
       GS.c.publish( GS.OUT_STATUS, msg=ujson.dumps(GS.statusMsg), retain=True, qos=1 )
   
def WifiConnect( GS ):
    if GS.station.isconnected():
        log( "INFO", "I'm already connected" )
        return True
    log( "INFO", "I'm not connected" )
    GS.station.active( True )
    log( "DEBUG", "station.active(True) now connect" )
    GS.station.connect( GS.SSIDWIFI, GS.PASSWIFI )
    log( "DEBUG", "connect attempt DONE... waiting for the link" )
    cnt = 0
    while GS.station.isconnected() == False:
        log( "WARN2", ( "Waiting for link " + str(cnt) ) )
        internalLed.off()
        if cnt > WIFI_TIMEOUT_MS:
           log( "ERROR", "Link doesn't respond! reboot" )
           machine.reset()
           sleep_ms( WIFI_TIMEOUT_MS )
        cnt += 1
    log( "INFO", "Connection successful network details:" )
    log( "INFO", GS.station.ifconfig() )
    log( "INFO", "Network DONE\n" )

# MQTT SETUP
def MqttSetUP( GS ):
   GS.c = MQTTClient( GS.CLIENTID, GS.SERVER, user=GS.USER, password=GS.PSWD, keepalive=MQTT_KEEPALIVE_SEC )
   GS.c.set_last_will( topic=GS.OUT_STATUS, msg=b'{"status": "OFFLINE"}', retain=True, qos=1 )
   GS.c.set_callback( sub_cb )
   try:
      log( "INFO", "Connection to MQTT" )
      GS.c.connect()
   except Exception as e:
      log( "ERROR",'Error MqttSetUP {}'.format(e) )
      log( "ERROR", "MQTT doesn't respond! reboot" )  
      machine.reset()  
      sleep_ms( WIFI_TIMEOUT_MS )
   GS.c.subscribe( GS.IN_CMD_TOPIC, qos=1 )
   GS.c.publish( GS.OUT_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True, qos=1 )

def main(GS):
   GS.ConfigFile     = 'mycfng.json'
   # GS.data           = {}  
   LoadConfig( GS )
   # Init i2c
   i2c               = I2C( scl=Pin(5), sda=Pin(4) )
   pcfs              = i2c.scan()
   devices           = {}
   for p in pcfs:
      devices[p]             =  {} 
      devices[p]["Ist"]      = pcf8574.PCF8574(i2c, p)
      devices[p]["Ist"].port = 0
      devices[p]["Name"]     = p   
   # Station UP
   GS.station        = network.WLAN( network.STA_IF )
   # Disabilito AP 
   ap_if             = network.WLAN( network.AP_IF )
   ap_if.active( False )
   sleep_ms( LOOP_WAIT_MS ) 
   sleep_ms( LOOP_WAIT_MS ) 
   sleep_ms( LOOP_WAIT_MS ) 
   WifiConnect(GS)
   MqttSetUP(GS)
   internalLed.on()
   PrintCnt    = 0
   byteFields  = ''
   while True:
       newByteFields      = ''
       PrintCnt          += 1    
       for dev in devices:
           Name           = devices[dev]["Name"]
           pcf            = devices[dev]["Ist"] 
           newByteFields += str(pcf.port) 
           for x in range(I2C_PIN_NUMBER):
             value        = pcf.pin(x)
             msg          = "Pin: " + str( x ) + " is: [ " + str( value ) + " ]  On DEV: " + str(Name) 
             log( "VERBO", msg )
             PinOut       = str(Name) + "_" + str(x)
             GS.statusMsg[PinOut] = value
       if newByteFields != byteFields:  
          try:
             byteFields = newByteFields
             log("DEBUG", "Pub Status on: ["+str(GS.OUT_STATUS)+"]" )
             GS.statusMsg["rssi"] = str(GS.station.status('rssi'))
             GS.c.publish( GS.OUT_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True, qos=1 )
             msg = "Notifications DONE"
             log( "INFO", msg )
          except Exception as e:
             log( "ERROR",'Error MqttPub on OUT_STATUS {}'.format(e) )
             internalLed.off()
             machine.reset()
             sleep_ms(LOOP_WAIT_MS)
	   
       if PrintCnt == LOOP_SKIPS: # Limit console noise 
          PrintCnt = 0    
          log( "INFO","----- LOOOP MqttI2cInput -----" )
          timer = Timer(0)
          timer.init( period=( TIMEOUT_MS * 30 ), mode=Timer.ONE_SHOT, callback=timeout_callback )
          try:
             log( "DEBUG","NewCheck" )
             GS.c.check_msg()
             log( "DEBUG","NewCheck DONE" )
             log( "DEBUG","Ping Start" )
             GS.c.ping()
             log( "DEBUG","Ping DONE" )
             internalLed.on()
          except Exception as e:
             log( "ERROR",'Error MqttCallBack and MqttPing {}'.format(e) )
             internalLed.off()
             machine.reset()
             sleep_ms(LOOP_WAIT_MS)
          finally:  
             timer.deinit()
       sleep_ms(LOOP_WAIT_MS)
   GS.c.disconnect()

main(GS)
