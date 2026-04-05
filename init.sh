#!/bin/bash

# This script compiles the esp binary file and copies it to the binaries directory

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
# copy the esp binary to backend and rename it to version number
cp -f ./esp12f/build/esp8266.esp8266.nodemcuv2/esp12f.ino.bin ./binaries/esp12f.ino.bin
version=$(grep '#define VERSION' esp12f/esp12f.ino | sed -E 's/^#define VERSION "([^"]+)"$/\1/')
mv ./binaries/esp12f.ino.bin ./binaries/$version.bin
