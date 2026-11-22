#!/bin/sh
# Kindle dashboard petlja. Pokrece je "Dashboard Start" iz biblioteke.
DIR=/mnt/us/dashboard
URL="https://vlado-grabovac.github.io/kindle-dashboard/dashboard.png"
INTERVAL=900                      # 15 minuta
TZSTR="CET-1CEST,M3.5.0,M10.5.0/3"
LOG=$DIR/dashboard.log
PIDFILE=/tmp/dashboard.pid

log() { echo "$(TZ=$TZSTR date '+%d.%m %H:%M:%S') $*" >> $LOG; }

# samo jedna instanca
[ -f $PIDFILE ] && kill "$(cat $PIDFILE)" 2>/dev/null
echo $$ > $PIDFILE
[ -f $LOG ] && [ "$(wc -c < $LOG)" -gt 200000 ] && mv $LOG $LOG.old

cleanup() {
  log "izlaz, vracam Kindle interfejs"
  [ -n "$WATCH" ] && kill $WATCH 2>/dev/null
  lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null
  rm -f $PIDFILE
  eips -c; eips -c
  start lab126_gui 2>/dev/null || start framework 2>/dev/null
  exit 0
}
trap cleanup INT TERM

log "start"
lipc-set-prop com.lab126.powerd preventScreenSaver 1
sleep 4
stop lab126_gui 2>/dev/null || stop framework 2>/dev/null
sleep 2

# power dugme = izlaz iz dashboarda
( lipc-wait-event com.lab126.powerd goingToScreenSaver,outOfScreenSaver >/dev/null 2>&1; kill -TERM $$ ) &
WATCH=$!

n=0
while true; do
  lipc-set-prop com.lab126.wifid enable 1 2>/dev/null
  i=0
  while [ $i -lt 30 ]; do
    [ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = "CONNECTED" ] && break
    sleep 2; i=$((i+1))
  done
  T=$(date +%s)
  if curl -fsS -m 40 -o $DIR/tmp.png "$URL?t=$T" 2>>$LOG || curl -fsSk -m 40 -o $DIR/tmp.png "$URL?t=$T" 2>>$LOG; then
    mv $DIR/tmp.png $DIR/dash.png
    OK=1
  else
    OK=0
    log "download nije uspio (wifi: $(lipc-get-prop com.lab126.wifid cmState 2>/dev/null))"
  fi
  if [ -f $DIR/dash.png ]; then
    # puni refresh svaki sat protiv "ghostinga"
    if [ $((n % 4)) -eq 0 ]; then eips -c; eips -c; fi
    eips -g $DIR/dash.png
    [ $OK -eq 0 ] && eips 1 1 "OFFLINE $(TZ=$TZSTR date +%H:%M)"
  else
    eips -c; eips 2 10 "Nema slike, provjeri WiFi"
  fi
  n=$((n+1))
  sleep $INTERVAL &
  wait $!
done
