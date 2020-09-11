this is a simple controller for reading pins using i2c unexpensive devices 
like:

https://www.gmelectronic.com/modul-expander-i2c-pcf8574

as the others firmwares I wrote it speaks trought mqtt.
it sends the pins status on the configurated topic on Mqtt at every change
it generates a JSON { "BoardAddress_PinNumber" : "value"   } like this:
my/topic/Status: {"33_6": 0, "32_3": 0, "32_2": 0, "32_1": 0, "32_0": 0, "32_7": 0, "32_6": 0, "32_5": 0, "status": "ONLINE", "32_4": 0, "33_4": 0, "33_5": 0, "33_7": 0, "33_2": 0, "33_3": 0, "33_0": 0, "33_1": 0}
my/topic/Status: {"status": "OFFLINE"}

once you connected it to the esp8266 
it scans for the pcf8574 adresses ( set the jumpers to have different adresses if you have multiple pcf8574 boards )

Connections:
3V  => VCC
GND => GND
D1  => SCL
D2  => SDA

it could be useful for PIRS, door/windows switches
