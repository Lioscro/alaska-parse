#!/bin/bash
args="$*"
export PORT=80

docker-compose -f docker-compose.yml down
cp src/nginx/start_local.sh src/nginx/start.sh
docker-compose -f docker-compose.maintenance.yml up $args
