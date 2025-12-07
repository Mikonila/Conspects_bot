#!/bin/bash

echo "=== Checking Docker container status ==="
docker-compose ps

echo -e "\n=== Last 50 lines of logs ==="
docker-compose logs --tail=50 bot

echo -e "\n=== Checking if bot is running ==="
docker-compose exec bot ps aux || echo "Container might not be running"

echo -e "\n=== Checking .env file (without values) ==="
if [ -f .env ]; then
    echo ".env file exists"
    grep -E "^[A-Z_]+=" .env | sed 's/=.*/=***/' || echo "No variables found"
else
    echo ".env file NOT found!"
fi



