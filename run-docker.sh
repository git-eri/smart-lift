#!/bin/bash
docker system prune -f

# Building image
echo "Building Image"
docker build --rm -f Dockerfile --progress=plain -t smart-lift:latest .

# Run the containers
docker run --rm --publish 8000:8000 --name smart-lift smart-lift:latest