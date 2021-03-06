#!/bin/bash
# Script to easily start local server.
source local.env

args="$*"

./make_dirs.sh
# docker pull --all-tags lioscro/alaska
docker-compose -f docker-compose.maintenance.yml down
cp src/web/assets/js/local_env.js src/web/assets/js/env.js
docker-compose run --rm mongo mongod --repair
docker-compose -f docker-compose.yml up $args
