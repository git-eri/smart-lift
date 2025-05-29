#!/bin/bash

read -p "Input the Hostname/IP address of the server: " hostname
if [[ -z "$hostname" ]]; then
    echo "Hostname/IP address cannot be empty."
    exit 1
fi

# check if https should be used
read -p "Use HTTPS? (y/n): " use_https
if [[ "$use_https" != "y" && "$use_https" != "n" ]]; then
    echo "Invalid input. Please enter 'y' or 'n'."
    exit 1
fi
if [ "$use_https" == "y" ]; then
    echo "Using HTTPS"
    # check if using self-signed certificate
    read -p "Use self-signed certificate? (y/n): " use_self_signed
    if [[ "$use_self_signed" != "y" && "$use_self_signed" != "n" ]]; then
        echo "Invalid input. Please enter 'y' or 'n'."
        exit 1
    fi
    if [ "$use_self_signed" == "y" ]; then
        echo "Using self-signed certificate"
        # check if openssl is installed
        if ! command -v openssl &> /dev/null
        then
            echo "openssl could not be found"
            exit 1
        fi
        if [ ! -d ./certs ]; then
            mkdir -p ./certs;
        fi
        # Check if certificate is installed
        if [ ! -f ./app/certs/server.crt ] || [ ! -f ./app/certs/server.key ]; then
            echo "Certificates not found"
            openssl req -x509 -nodes -days 730 -newkey rsa:2048 -keyout ./certs/server.key -out ./certs/server.crt -subj "/C=/ST=/L=/O=/CN=$hostname" -addext "subjectAltName = DNS:smart-lift, DNS:$hostname"
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
    else
        echo "Using CA signed certificate"
    fi
else
    echo "Using HTTP"
fi
# check if .env file exists
if [ ! -f ./.env ]; then
    echo "Creating .env file"
    echo "HOSTNAME=$hostname" > ./.env
    if [ "$use_https" == "y" ]; then
        echo "USE_HTTPS=true" >> ./.env
        if [ "$use_self_signed" == "y" ]; then
            echo "USE_SELF_SIGNED_CERT=true" >> ./.env
        else
            echo "USE_SELF_SIGNED_CERT=false" >> ./.env
        fi
    else
        echo "USE_HTTPS=false" >> ./.env
    fi
else
    echo ".env file already exists"
fi

# check if binaries directory exists
if [ ! -d ./binaries ]; then
    echo "Creating binaries directory"
    mkdir -p ./binaries;
else
    echo "Binaries directory already exists"
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
