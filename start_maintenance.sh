#!/bin/bash
args="$*"

docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.maintenance.yml up $args
