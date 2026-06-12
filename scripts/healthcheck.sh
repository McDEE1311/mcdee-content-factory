#!/bin/bash
# Quick health check

echo "=== McDEE Health Check ==="
echo ""

# API
echo -n "API (http://127.0.0.1:8899/health): "
if curl -sf http://127.0.0.1:8899/health > /dev/null 2>&1; then
    echo "OK"
    curl -s http://127.0.0.1:8899/health | python3 -m json.tool
else
    echo "DOWN"
fi

echo ""
echo -n "Ollama: "
if curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "OK"
else
    echo "DOWN"
fi

echo ""
echo -n "DB: "
if [ -f "data/content_factory.db" ]; then
    echo "OK ($(du -sh data/content_factory.db | cut -f1))"
else
    echo "NOT FOUND"
fi

echo ""
echo "Outputs:"
ls -la outputs/upload_packages/ 2>/dev/null || echo "  (empty)"

echo ""
echo "PM2 services:"
pm2 list 2>/dev/null || echo "PM2 not running"
