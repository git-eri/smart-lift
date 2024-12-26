#!/bin/bash

read -p "Input the Hostname/IP address of the server: " ip

if [ ! -d ./certs ]; then
    mkdir -p ./certs;
fi
if [ ! -d ./binaries ]; then
    mkdir -p ./binaries;
fi

# Check if certificate is installed
if [ ! -f ./app/certs/server.crt ] || [ ! -f ./app/certs/server.key ]; then
    echo "Certificates not found"
    openssl req -x509 -nodes -days 730 -newkey rsa:2048 -keyout ./certs/server.key -out ./certs/server.crt -subj "/C=/ST=/L=/O=/CN=$ip" -addext "subjectAltName = DNS:smart-lift, DNS:$ip"
    if [ $? -ne 0 ]; then
        echo "Failed to generate certificates"
        exit
    fi
    echo "Certificates generated"
    cp -rf ./certs/server.crt ./esp12f/data/server.crt
else
    echo "Certificates found"
fi

# Copy certificates to esp12f
if [ ! -f ./esp12f/data/server.crt ]; then
    cp -rf ./certs/server.crt ./esp12f/data/server.crt
fi

# Check if the arduino-cli is installed
if ! command -v arduino-cli &> /dev/null
then
    echo "arduino-cli could not be found"
    exit
fi

# Compile esp binary file
echo "Compiling ESP binary file"
arduino-cli compile -e --fqbn esp8266:esp8266:nodemcuv2 esp12f
if [ $? -eq 0 ]; then
    echo Build ok
else
    echo Build failed
    exit
fi

cp -f ./esp12f/build/esp8266.esp8266.nodemcuv2/esp12f.ino.bin ./binaries/esp12f.ino.bin
version=$(grep '#define VERSION' esp12f/esp12f.ino | cut -d' ' -f3 | tail -c +2 | head -c -3)
mv ./binaries/esp12f.ino.bin ./binaries/$version.bin
