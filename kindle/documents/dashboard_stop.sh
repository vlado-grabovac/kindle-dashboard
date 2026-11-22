#!/bin/sh
# Name: Dashboard Stop
# Author: Vlado
[ -f /tmp/dashboard.pid ] && kill "$(cat /tmp/dashboard.pid)" 2>/dev/null
lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
echo "Dashboard zaustavljen."
