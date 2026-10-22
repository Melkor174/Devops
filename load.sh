#!/usr/bin/env bash
# Простой генератор нагрузки без дополнительных утилит.
# Использование: ./load.sh [URL] [ПАРАЛЛЕЛЬНО] [СЕКУНД]
# Пример:        ./load.sh http://localhost/api/notes 10 60
URL="${1:-http://localhost/api/notes}"
JOBS="${2:-5}"
DURATION="${3:-30}"
END=$((SECONDS + DURATION))

worker() {
  while [ "$SECONDS" -lt "$END" ]; do
    curl -s -o /dev/null -w "%{http_code} %{time_total}\n" "$URL"
  done
}

echo "Нагрузка: $URL, потоков: $JOBS, секунд: $DURATION"
for _ in $(seq "$JOBS"); do worker & done | awk '{c[$1]++; s+=$2; n++} END {for (k in c) print "HTTP", k, c[k]; if (n) print "avg time:", s/n, "s, requests:", n}'
wait
