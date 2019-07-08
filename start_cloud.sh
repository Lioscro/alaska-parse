#!/bin/bash
# Script to easily start remote server.
source remote.env

args="$*"

docker pull --all-tags lioscro/alaska
docker-compose up $args
