# Duck-Vision MQTT Broker Setup
# Installer på Pi 4 (Samantha)

## Installer Mosquitto MQTT Broker

```bash
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients
```

## Start og enable service

```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

## Test broker

```bash
# Terminal 1 - Subscribe
mosquitto_sub -t "test/topic" -v

# Terminal 2 - Publish
mosquitto_pub -t "test/topic" -m "Hello MQTT"
```

## Finn IP-adresse til Pi 4

```bash
hostname -I
```

Bruk denne IP-en i Duck-Vision's `.env` fil.
