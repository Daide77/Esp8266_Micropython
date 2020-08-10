import micropython # For emergency exception buffer
from   machine     import Pin, Timer
import machine
from   time        import sleep, sleep_ms
# from   umqttrobust import MQTTClient
from   umqttsimple import MQTTClient
import ujson
import network
import os
import gc

TIMEOUT_MS         = 500
WIFI_TIMEOUT_MS    = 3200
LOOP_WAIT_MS       = 50
LOOP_SKIPS         = 10
MIN_FREE_MEM       = 15520
MQTT_KEEPALIVE_SEC = 3

internalLed = machine.Pin(2, machine.Pin.OUT)
micropython.alloc_emergency_exception_buf(100)

# DONE Normalizzare i messaggi in modo tale
# che siano tutti in formato JSON

# class FunctTimeOutErr(Exception):
#     def __init__(self, m):
#         self.message = m
#     def __str__(self):
#         return self.message

def timeout_callback(t):
    log("WARN", "Operation frozen...Reboot")
    internalLed.off()
    machine.reset()
    # raise FunctTimeOutErr("FunctionTimeOut")

class GeneralStruct:
    pass

GS                = GeneralStruct()

# Basic Function
LOG_LEVEL      = [ "DEBUG", "INFO", "WARN", "ERROR" ]
def log( Level, msg ):
    if Level in LOG_LEVEL:
        print( "Level: {} Msg: {} ".format(str(Level), str(msg)) )

def StringToList( sep, string, purpose="logLevel" ):
   log("INFO","preparing new list for "+purpose)
   try:
      newList = string.split( sep )
   except:
      log("WARN", ("No new list, keeping old list ",LOG_LEVEL) )
      newList = []
      return LOG_LEVEL
   if len(newList) > 0:
      log("INFO", ("new list is",newList) )
      return newList
   else:
      log("INFO", ("keeping old list ",LOG_LEVEL) )
      return LOG_LEVEL

def fileExists(filename):
    try:
        os.stat(filename)
        return True;
    except OSError:
        return False

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
      GS.IN_CMD_TOPIC   = str(GS.data["MQTT_IN_CMD_TOPIC"]).encode()
      # TOPIC
      GS.OUT_PIR_STATUS = str(GS.data["MQTT_OUT_PIR_STATUS"]).encode()
      GS.OUT_TRG_NOTIFY = str(GS.data["MQTT_OUT_TRG_NOTIFY"]).encode()
      # Trigger Msg
      GS.OUT_TRG_MSG    = GS.data["MQTT_OUT_TRG_MSG"]
      LOG_LEVEL         = StringToList( ',', str( GS.data["LOG_LEVEL"] ) )
      # WIFI Config
      GS.SSIDWIFI       = GS.data["SSIDWIFI"]
      GS.PASSWIFI       = GS.data["PASSWIFI"]

# Functions
def SetNotify( GS ):
    if fileExists( GS.NotifyFile ):
        log("DEBUG","File conf for notification exists: ["+GS.NotifyFile+"]" ) 
        with open( GS.NotifyFile ) as data_file:
          GS.data2         = ujson.load( data_file )
          log("DEBUG", "Loading notification conf: "+str(GS.data2) )
          GS.IS_TO_NOTIFY  = GS.data2["MQTT_IS_TO_NOTIFY"]
    elif not fileExists( GS.NotifyFile ):
       IS_TO_NOTIFY    = GS.data["MQTT_DEFAULT_IS_TO_NOTIFY"]
       with open( GS.NotifyFile,  'w' ) as f:
         log( "DEBUG", "Notification file doesn't exists... writing of notification file: ["+GS.NotifyFile+"]")
         GS.data2["MQTT_IS_TO_NOTIFY"] = GS.IS_TO_NOTIFY 
         ujson.dump( GS.data2, f )
    GS.statusMsg['MQTT_IS_TO_NOTIFY'] = GS.IS_TO_NOTIFY 

# Received messages from subscriptions will be delivered to this callback
def sub_cb( topic, msg ):
    log( 'INFO', (topic, msg) )
    if topic == GS.IN_CMD_TOPIC:
       # Comando in entrata : '{ "MQTT_IS_TO_NOTIFY" : 0, "COMMAND": "REBOOT" }'  
       # Normalizzare il messaggio in uscita inserire ad esempio '{ "rssi":-65 , "MQTT_IS_TO_NOTIFY" : 1 }'
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
          if   k == 'MQTT_IS_TO_NOTIFY':
             GS.statusMsg[k] = int(cmd[k])
             GS.IS_TO_NOTIFY = int(cmd[k]) 
             with open( GS.NotifyFile, 'w' ) as f:
               log( "DEBUG", "Overwrinting on notification conf: ["+GS.NotifyFile+"]")
               GS.data2["MQTT_IS_TO_NOTIFY"] = cmd[k]
               GS.data["MQTT_IS_TO_NOTIFY"]  = cmd[k]
               ujson.dump( GS.data2, f )
          elif k == 'COMMAND' and cmd[k] == 'REBOOT': 
               log( "INFO", "Command is to reboot!" )
               machine.reset()
               sleep_ms( WIFI_TIMEOUT_MS )
       GS.c.publish( GS.OUT_PIR_STATUS, msg=ujson.dumps(GS.statusMsg), retain=True, qos=1 )
   
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
# End Functions

# MQTT SETUP
def MqttSetUP( GS ):
   GS.c = MQTTClient( GS.CLIENTID, GS.SERVER, user=GS.USER, password=GS.PSWD, keepalive=MQTT_KEEPALIVE_SEC )
   GS.c.set_last_will( topic=GS.OUT_PIR_STATUS, msg=b'{"status": "OFFLINE"}', retain=True, qos=1 )
   GS.c.set_callback( sub_cb )
   try:
      log( "INFO", "Connection to MQTT" )
      GS.c.connect()
   except Exception as e:
      log( "ERROR", "MQTT doesn't respond! reboot" )  
      machine.reset()  
      sleep_ms( WIFI_TIMEOUT_MS )
   GS.c.subscribe( GS.IN_CMD_TOPIC, qos=1 )
   GS.c.publish( GS.OUT_PIR_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True, qos=1 )

def main(GS):
   try:
      GS.ConfigFile     = 'mycfng.json'
      GS.NotifyFile     = 'NotifyStatus.json'
      GS.data           = {}  
      GS.data2          = {}  
      LoadConfig( GS )
      SetNotify( GS )
      # PIR SETUP Connettore D5
      button            = Pin( 14, Pin.IN, Pin.PULL_UP )
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
      while True:
          if PrintCnt == LOOP_SKIPS: # Limit console noise 
             log( "INFO","----- LOOOP MqttPIR -----" )
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
                log( "ERROR",'Error {}'.format(e) )
                internalLed.off()
                machine.reset()
                # GS.c.disconnect()
                # WifiConnect(GS)
                # MqttSetUP(GS)
                sleep_ms(LOOP_WAIT_MS)
             finally:  
                timer.deinit()

          if not button.value():
              if PrintCnt == LOOP_SKIPS: # Limit console noise 
                GS.statusMsg["Circut"] = "closed"
                msg      = "Circut closed"
                log( "DEBUG", msg )
                PrintCnt = 0
              else:
                PrintCnt += 1    
          else:		
              msg = "Circut opened!"
              log( "INFO", msg )
              GS.statusMsg["Circut"] = "opened"
              if int(GS.IS_TO_NOTIFY) == 1:
                 try:
                    log("DEBUG", "Pub on Trigger: ["+str(GS.OUT_TRG_NOTIFY)+"]" )
                    GS.c.publish( GS.OUT_TRG_NOTIFY, ujson.dumps(GS.OUT_TRG_MSG), qos=1 )
                    log("DEBUG", "Pub Status on: ["+str(GS.OUT_PIR_STATUS)+"]" )
                    GS.c.publish( GS.OUT_PIR_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True, qos=1 )
                    msg = "Notifications DONE"
                    log( "DEBUG", msg )
                 except Exception as e:
                    log( "ERROR",'Error {}'.format(e) )
                    internalLed.off()
                    machine.reset()
                    sleep_ms(LOOP_WAIT_MS)
              else:
                 log("DEBUG", "IS TO NOTIFY: ["+str(GS.IS_TO_NOTIFY)+"]" )
                 msg = "Notification not sent. Notification disabled"
                 log( "DEBUG", msg )
      
          sleep_ms(LOOP_WAIT_MS)
   except Exception as e:
      log( "ERROR",'Error {}'.format(e) )
      internalLed.off()
      machine.reset()
      sleep_ms(LOOP_WAIT_MS)
   GS.c.disconnect()

main(GS)
