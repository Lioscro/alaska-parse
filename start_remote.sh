#!/bin/bash
# Script to easily start remote server.
source remote.env

args="$*"

./make_dirs.sh
docker pull --all-tags lioscro/alaska
cp src/web/assets/js/remote_env.js src/web/assets/js/env.js
cp src/nginx/start_remote.sh src/nginx/start.sh
src/nginx/start_local.shdocker-compose up $args
