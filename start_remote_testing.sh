#!/bin/bash
source remote.env
export PORT=81

args="$*"

./make_dirs.sh
docker pull --all-tags lioscro/alaska
cp src/web/assets/js/remote_env.js src/web/assets/js/env.js
docker-compose up $args
