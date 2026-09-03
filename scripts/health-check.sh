#!/bin/bash
HOST=${HOST:-localhost}
FAILURES=0

check() {
    eval "$2" > /dev/null 2>&1 && echo "  [OK]   $1" || { echo "  [FAIL] $1"; FAILURES=$((FAILURES+1)); }
}

echo "Checking PatchGuard services..."
check "API"      "curl -sf http://$HOST:8000/health"
check "Kafka"    "docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092"
check "Postgres" "docker-compose exec -T postgres pg_isready -U patchguard"
check "DynamoDB" "curl -sf http://$HOST:8001/"
check "Redis"    "docker-compose exec -T redis redis-cli ping"

[ $FAILURES -eq 0 ] && echo "All healthy." || { echo "$FAILURES unhealthy."; exit 1; }
