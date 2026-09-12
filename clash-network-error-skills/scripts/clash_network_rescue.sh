#!/bin/zsh
set -u

SERVICE="${1:-Wi-Fi}"
LOG_DIR="$HOME/Desktop"
STAMP="$(date '+%Y%m%d-%H%M%S')"
LOG_FILE="$LOG_DIR/clash-network-$STAMP.log"

log() {
  printf '\n### %s\n' "$1" | tee -a "$LOG_FILE"
}

run() {
  printf '\n$ %s\n' "$*" | tee -a "$LOG_FILE"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

run_with_timeout() {
  local seconds="$1"
  shift
  printf '\n$ %s\n' "$*" | tee -a "$LOG_FILE"
  local tmp="$LOG_DIR/clash-network-command-$STAMP.tmp"
  "$@" >"$tmp" 2>&1 &
  local pid="$!"
  local elapsed=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$elapsed" -ge "$seconds" ]; then
      kill "$pid" 2>/dev/null
      sleep 1
      kill -9 "$pid" 2>/dev/null
      cat "$tmp" | tee -a "$LOG_FILE"
      echo "[timed out after ${seconds}s]" | tee -a "$LOG_FILE"
      rm -f "$tmp"
      return 124
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  wait "$pid"
  local status="$?"
  cat "$tmp" | tee -a "$LOG_FILE"
  rm -f "$tmp"
  if [ "$status" -ne 0 ]; then
    echo "[exit $status]" | tee -a "$LOG_FILE"
  fi
  return "$status"
}

echo "Writing network diagnostics and rescue log to: $LOG_FILE"
echo "Service: $SERVICE" | tee -a "$LOG_FILE"

log "Before: system proxy"
run scutil --proxy

log "Before: DNS"
run scutil --dns
run networksetup -getdnsservers "$SERVICE"

log "Before: service info"
run networksetup -getinfo "$SERVICE"

log "Before: route table excerpts"
netstat -rn 2>&1 | tee -a "$LOG_FILE"

log "Before: fake-ip probes"
run_with_timeout 5 dscacheutil -q host -a name www.baidu.com
run_with_timeout 5 dscacheutil -q host -a name api.openai.com
run_with_timeout 5 dscacheutil -q host -a name www.qq.com

log "Rescue: disable system proxies"
run networksetup -setwebproxystate "$SERVICE" off
run networksetup -setsecurewebproxystate "$SERVICE" off
run networksetup -setsocksfirewallproxystate "$SERVICE" off
run networksetup -setautoproxystate "$SERVICE" off

log "Rescue: set stable DNS"
run networksetup -setdnsservers "$SERVICE" 223.5.5.5 119.29.29.29

log "Rescue: flush DNS cache"
run dscacheutil -flushcache
sudo killall -HUP mDNSResponder 2>&1 | tee -a "$LOG_FILE"

log "After: system proxy"
run scutil --proxy

log "After: DNS"
run scutil --dns
run networksetup -getdnsservers "$SERVICE"

log "After: connectivity probes"
run_with_timeout 5 ping -c 2 192.168.0.1
run_with_timeout 5 ping -c 2 223.5.5.5
run_with_timeout 10 curl -I --connect-timeout 8 https://www.baidu.com

echo
echo "Done. Log saved to: $LOG_FILE"
