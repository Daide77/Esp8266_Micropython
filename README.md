# Esp8266_Micropython

This project includes firmwares written in Micropython for ESP8266 board, they are complementary to a Discord-nodejs-bot that I wrote to interact with
Shinobi Cctv ( see https://shinobi.video/ ) and to prevent my garden to get thirsty.


MqttGarden2 it controls a board with 2 relays to handle two valves in my garden

MqttPir     its goal is to trigger an allarm on Shinobi when someone passes under the sensor

MqttI2cInput its goal is to interact with one or more pcf8574 to read pins status

All the comunications are done using Mqtt protocol, the boards are WiFi connected 
