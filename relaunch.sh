#!/bin/bash
# Rebuilds and restarts all docker-compose services
set -e

echo "Relaunching Docker Compose stack..."
docker compose up -d --build --force-recreate
echo "Done!"
