#!/bin/bash
# Script to easily start remote server.
export SERVER_HOST="13.52.189.218"
args="$*"

docker-compose up $args
