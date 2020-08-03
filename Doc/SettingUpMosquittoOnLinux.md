sudo apt-get update
sudo apt-get install mosquitto

sudo apt-get install mosquitto-clients

# hint command to generate random password
openssl rand -base64 10

# this creates the file ad the first user
sudo mosquitto_passwd -c /etc/mosquitto/passwd MyFirstUser
# this for the other users
sudo mosquitto_passwd /etc/mosquitto/passwd Myotherusers

# After you created all the needed users
sudo vim /etc/mosquitto/conf.d/default.conf
# Content of the file must be:

allow_anonymous false
password_file /etc/mosquitto/passwd

# Restart the service
sudo systemctl restart mosquitto

