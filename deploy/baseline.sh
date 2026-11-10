#!/usr/bin/env bash
# Task 2.1: record VPS memory/CPU baseline BEFORE starting the inference stack.
# Usage: ./baseline.sh > ../poc/reports/baseline.md
set -uo pipefail
echo "# VPS baseline ($(date -u +%Y-%m-%dT%H:%MZ))"
echo
echo "Host: \`$(hostname)\` · $(nproc) vCPU · kernel $(uname -r) · cgroup: $(stat -fc %T /sys/fs/cgroup)"
echo
echo '## Memory (`free -m`)'; echo '```'; free -m; echo '```'
echo '## Load'; echo '```'; uptime; echo '```'
echo '## Top memory consumers'; echo '```'; ps -eo rss,comm --sort=-rss | head -15 | awk 'NR==1{print "RSS_MiB COMMAND";next}{printf "%7.0f %s\n",$1/1024,$2}'; echo '```'
echo '## Running containers'; echo '```'; docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' 2>/dev/null || echo "docker not available"; echo '```'
echo '## Services of interest'; echo '```'
for s in nginx php-fpm mysql mysqld mariadb pm2 node; do pgrep -x "$s" >/dev/null && echo "running: $s"; done
pm2 ls 2>/dev/null | head -20 || true
echo '```'
echo '## Disk'; echo '```'; df -h / /opt 2>/dev/null; echo '```'
echo
echo '## Conclusion (fill in)'
echo
echo '- Other apps on this VPS: …'
echo '- Measured non-inference usage: … MiB; reserve to use for the headroom check (`run_bench.py --reserve-mib`): … MiB'
echo '- WHISPER_MEM_LIMIT / LLAMA_MEM_LIMIT chosen: … / …'
