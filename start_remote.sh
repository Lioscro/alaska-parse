#!/bin/bash
# Script to easily start remote server.
source remote.env

args="$*"

./make_dirs.sh
docker pull --all-tags lioscro/alaska
cp src/web/assets/js/remote_env.js src/web/assets/js/env.js
docker-compose up $args
