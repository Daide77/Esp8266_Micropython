from   machine     import Pin, Timer
import machine
from   time        import sleep, sleep_ms
from   umqttrobust import MQTTClient
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

def timeout_callback(t):
    log("ERROR", "Operation frozen... forced to exit")
    internalLed.off()
    machine.reset()

class GeneralStruct:
    pass

GS             = GeneralStruct()

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
   GS.data                      = {}  
   with open( GS.ConfigFile ) as data_file:
      log( "INFO", "Loading conf from file: ["+GS.ConfigFile+"]" )
      GS.data                   = ujson.load( data_file )
      GS.CLIENTID               = GS.data["MQTTclientid"]
      GS.USER                   = GS.data["MQTTuserid"]
      GS.PSWD                   = GS.data["MQTTpasswd"]
      GS.SERVER                 = GS.data["MQTTserver"]
      # TOPIC must be in binary format
      GS.IN_CMD_TOPIC           = str( GS.data["MQTT_IN_CMD_TOPIC"]      ).encode()
      GS.MQTT_OUT_DEVICE_STATUS = str( GS.data["MQTT_OUT_DEVICE_STATUS"] ).encode()
      # WIFI Config
      GS.SSIDWIFI               = GS.data["SSIDWIFI"]
      GS.PASSWIFI               = GS.data["PASSWIFI"]
      # Format  { "status":"OFFLINE|ONLINE", "rssi":"-65", "rele1":1, "rele2":1 }
      GS.statusMsg              = { "status":"ONLINE" } 
      LOG_LEVEL                 = StringToList( ',', str( GS.data["LOG_LEVEL"] ) ) 
      log( "INFO", "Loading config DONE\n" )

# Functions
def sub_cb( topic, msg ):
    log( 'INFO', (topic, msg) )
    if topic == GS.IN_CMD_TOPIC:
       GS.statusMsg["rssi"] = str(GS.station.status('rssi'))
       log("INFO", ( "WIFI rssi: ", GS.statusMsg['rssi'] ) )
       try:   
          cmd = ujson.loads( msg )
       except:
          cmd = {}
       if type( cmd ) is not dict:
          log( "WARN", "wrong command format! " + str( msg ))
          cmd = {}    
       # Esempio cmd { "rele1" : 0 , "rele2" : 0 } 
       for k in cmd :
          if   k == 'rele1':
             log( "DEBUG", "ricevuta notifica per " + k + " nuovo stato " + str(cmd[k]) )
             GS.statusMsg[k] = int(cmd[k]) 
             GS.button1.value( int(cmd[k]) ) 
             GS.c.publish( topic=GS.MQTT_OUT_DEVICE_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True )
          elif k == 'rele2':
             log( "DEBUG", "ricevuta notifica per " + k + " nuovo stato " + str(cmd[k]) )
             GS.statusMsg[k] = int(cmd[k]) 
             GS.button2.value( int(cmd[k]) ) 
             GS.c.publish( topic=GS.MQTT_OUT_DEVICE_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True )
          elif k == 'status':
             if cmd[k] == 'REBOOT':
                log("INFO", "Reboot the system" )
                machine.reset()
                sleep_ms(LOOP_WAIT_MS)
             else:
                log("INFO", ( "WIFI rssi: ", GS.statusMsg['rssi'] ) )
                GS.c.publish( topic=GS.MQTT_OUT_DEVICE_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True )

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
        log( "WARN", ( "Waiting for link " + str(cnt) ) ) 
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
   log( "INFO", "Setting up MQTT client" )
   GS.c = MQTTClient( GS.CLIENTID, GS.SERVER, user=GS.USER, password=GS.PSWD, keepalive=MQTT_KEEPALIVE_SEC ) 
   log( "DEBUG", "Setting up MQTT client DONE" )
   log( "DEBUG", "Setting up MQTT callback and last_will" )
   GS.c.set_callback( sub_cb )
   GS.c.set_last_will( topic=GS.MQTT_OUT_DEVICE_STATUS, msg=b'{"status": "OFFLINE"}', retain=True )
   log( "DEBUG", "Setting up MQTT callback and last_will DONE" )
   # Connect
   try:
      log( "INFO", "Connection to MQTT" )
      GS.c.connect()
   except Exception as e:
      log( "ERROR", "MQTT doesn't respond! reboot" )  
      machine.reset()  
      sleep_ms( WIFI_TIMEOUT_MS )
   log( "INFO", "Connection to MQTT DONE" )
   log( "DEBUG", "MQTT subscribe" )
   # Sottoscrizione TODO mettere in array
   GS.c.subscribe( GS.IN_CMD_TOPIC )
   log( "DEBUG", "MQTT subscribe DONE" )
   log( "DEBUG", "MQTT pubblish status" )
   GS.c.publish( topic=GS.MQTT_OUT_DEVICE_STATUS, msg=ujson.dumps( GS.statusMsg ), retain=True )
   log( "INFO", "MQTT pubblish status DONE\n" )

def main( GS ):
   GS.ConfigFile     = 'mycfng.json'
   LoadConfig( GS )
   log( "INFO", "Setting up hardware...." )
   # PIR SETUP Connettore D5
   GS.button1        = Pin( 14, Pin.OUT )
   GS.button1.on()   
   # PIR SETUP Connettore D6
   GS.button2        = Pin( 12, Pin.OUT )
   GS.button2.on()   
   log( "INFO", "Setting up hardware successful" )
   # Station UP
   GS.station        = network.WLAN( network.STA_IF )
   # Disabilito AP 
   ap_if             = network.WLAN( network.AP_IF )
   ap_if.active( False )

   WifiConnect( GS )
   MqttSetUP( GS )
   internalLed.on()
   PrintCnt = 0
   log( "INFO", "Entering Main_Loop!" )
   while True:
       if PrintCnt == LOOP_SKIPS:     # Limit console noise and operations rate
         PrintCnt  = 0
         log( "DEBUG","---- Long Loop START ----" )
         if gc.mem_free() < MIN_FREE_MEM:
            log( "INFO", gc.mem_free() ) 
            log( "INFO","gc cleans memory" )
            gc.collect()
            log( "INFO", gc.mem_free() ) 
            log( "INFO","gc cleans memory DONE" )
         
         log( "DEBUG","NewCheck" )
         try:
            timer = Timer(0)
            timer.init( period=TIMEOUT_MS, mode=Timer.ONE_SHOT, callback=timeout_callback )
            GS.c.check_msg()
            timer.deinit()
         except Exception as e:
            log( "ERROR",'Error {}'.format(e) )
            internalLed.off()
            machine.reset()
            sleep_ms(LOOP_WAIT_MS)
         log( "DEBUG","NewCheck DONE" )

         log( "DEBUG","Ping Start" )
         try:
            timer = Timer(0)
            timer.init( period=TIMEOUT_MS, mode=Timer.ONE_SHOT, callback=timeout_callback )
            GS.c.ping()
            timer.deinit()
         except OSError as e :
            log( "ERROR","Mqtt ping Failed!"  )
            log( "ERROR",'Error {}'.format(e) )
            internalLed.off()
            machine.reset()
            sleep_ms(LOOP_WAIT_MS)
         except Exception as e:
            log( "ERROR",'Error {}'.format(e) )
            internalLed.off()
            machine.reset()
            sleep_ms(LOOP_WAIT_MS)
         log( "DEBUG","Ping DONE" )
         log( "DEBUG","---- Long Loop END ----" )

       else:
         PrintCnt += 1
       sleep_ms(LOOP_WAIT_MS)
   GS.c.disconnect()

main(GS)
