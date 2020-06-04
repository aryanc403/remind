#!/bin/bash

# Get to a predictable directory, the directory of this script
cd "$(dirname "$0")"

[ -e environment ] && . ./environment

while true; do

    python -m remind
    (( $? != 42 )) && break

    echo '==================================================================='
    echo '=                       Restarting                                ='
    echo '==================================================================='
done
