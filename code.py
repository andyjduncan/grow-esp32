# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import adafruit_dht
import adafruit_veml7700
import feathers2

import countio

import wifi
import socketpool
import ssl
import adafruit_minimqtt.adafruit_minimqtt as MQTT

import alarm

import analogio

time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + (30 * 60))

# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

feathers2.enable_LDO2(True)

# Initial the dht device, with data pin connected to:
dhtDevice = adafruit_dht.DHT22(board.IO5)

i2c = board.I2C()  # uses board.SCL and board.SDA
veml7700 = adafruit_veml7700.VEML7700(i2c)

sensor_1 = countio.Counter(board.D13)
sensor_2 = countio.Counter(board.D12)

start = time.monotonic()

time.sleep(5)

end = time.monotonic()

counts_1 = sensor_1.count / (end - start)

sensor_1.deinit()

counts_2 = sensor_2.count / (end - start)

sensor_2.deinit()

moisture_1 = (1 - (counts_1 / 27)) * 100

moisture_2 = (1 - (counts_2 / 27)) * 100

for _ in range(3):
    try:
        temperature_c = dhtDevice.temperature
        humidity = dhtDevice.humidity
        break
    except RuntimeError as error:
        # Errors happen fairly often, DHT's are hard to read, just keep going
        print(error.args[0])
        time.sleep(2.0)
        continue
    except Exception as error:
        dhtDevice.exit()
        raise error

lux = veml7700.lux

batt_pin = analogio.AnalogIn(board.A0)

batt_level = (batt_pin.value / 65535) * 100

print(
    "Temp: {:.1f} C    Humidity: {}%    Light: {} lux  Counts: {}  Batt: {}".format(
        temperature_c, humidity, lux, counts_1, batt_level
    )
)


print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])

# Define callback methods which are called when events occur
# pylint: disable=unused-argument, redefined-outer-name
def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    print("Connected to MQTT")

def disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("Disconnected from MQTT")

lux_topic = "grow/" + secrets["mqtt_client"] + "/lux"
temp_topic = "grow/" + secrets["mqtt_client"] + "/temp"
humidity_topic = "grow/" + secrets["mqtt_client"] + "/humidity"
battery_topic = "grow/" + secrets["mqtt_client"] + "/battery"
moisture_topic_1 = "grow/" + secrets["mqtt_client"] + "/moisture/1"
moisture_topic_2 = "grow/" + secrets["mqtt_client"] + "/moisture/2"

# Create a socket pool
pool = socketpool.SocketPool(wifi.radio)

# Set up a MiniMQTT Client
mqtt_client = MQTT.MQTT(
    broker=secrets["mqtt_hostname"],
    port=secrets["mqtt_port"],
    username=secrets["mqtt_username"],
    password=secrets["mqtt_password"],
    socket_pool=pool,
    ssl_context=ssl.create_default_context(),
)

# Setup the callback methods above
mqtt_client.on_connect = connected
mqtt_client.on_disconnect = disconnected

# Connect the client to the MQTT broker.
print("Connecting to MQTT...")
mqtt_client.connect()

mqtt_client.publish(lux_topic, lux)
mqtt_client.publish(temp_topic, temperature_c)
mqtt_client.publish(humidity_topic, humidity)
mqtt_client.publish(battery_topic, batt_level)
mqtt_client.publish(moisture_topic_1, moisture_1)
mqtt_client.publish(moisture_topic_2, moisture_2)

mqtt_client.disconnect()

alarm.exit_and_deep_sleep_until_alarms(time_alarm)