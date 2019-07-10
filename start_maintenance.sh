#!/bin/bash
args="$*"
source shared.env
export PORT=80

docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.maintenance.yml up $args
