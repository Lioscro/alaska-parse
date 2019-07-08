#!/bin/bash
# Script to easily start local server.
source local.env

args="$*"

docker pull --all-tags lioscro/alaska
docker-compose up $args
