#!/bin/bash
docker system prune -f

# Compile esp binary file
echo "Compiling ESP binary file"
arduino-cli compile -e --fqbn esp8266:esp8266:nodemcuv2 esp12f
cp -f ./esp12f/build/esp8266.esp8266.nodemcuv2/esp12f.ino.bin ./app/binaries/esp12f.ino.bin
version=$(grep '#define VERSION' esp12f/esp12f.ino | cut -d' ' -f3 | tail -c +2 | head -c -3)
mv ./app/binaries/esp12f.ino.bin ./app/binaries/$version.bin

# Building image
echo "Building Image"
docker build --rm -f Dockerfile --progress=plain -t smart-lift:latest .

# Run the containers
docker run --rm --publish 8000:8000 --name smart-lift smart-lift:latest