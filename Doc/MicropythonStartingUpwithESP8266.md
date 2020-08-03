pip install esptool

The code that I used here it's all running on esp8266-20191220-v1.12.bin firmware
https://micropython.org/download/esp8266/

Direct link to get the firmware: 
https://micropython.org/resources/firmware/esp8266-20191220-v1.12.bin


to flash the firmware:

esptool.py --port /dev/ttyUSB0 erase_flash

esptool.py --port /dev/ttyUSB0 --baud 460800 write_flash --flash_size=detect 0 esp8266-20191220-v1.12.bin


Connect to usb serial:

sudo picocom /dev/ttyUSB0 -b115200

To upload your software on the board you may use:

https://learn.adafruit.com/micropython-basics-esp8266-webrepl/access-webrepl

