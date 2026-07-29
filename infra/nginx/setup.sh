#!/usr/bin/env bash
set -euo pipefail

DOMAIN_CORE="core.YOUR_DOMAIN.com"
DOMAIN_ANALYSIS="analysis.YOUR_DOMAIN.com"
EMAIL="you@example.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

sed -e "s/CORE_DOMAIN_PLACEHOLDER/${DOMAIN_CORE}/g" \
    -e "s/ANALYSIS_DOMAIN_PLACEHOLDER/${DOMAIN_ANALYSIS}/g" \
    "${SCRIPT_DIR}/pitch-coach.conf" | sudo tee /etc/nginx/sites-available/pitch-coach.conf > /dev/null

sudo ln -sf /etc/nginx/sites-available/pitch-coach.conf /etc/nginx/sites-enabled/pitch-coach.conf
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl reload nginx

sudo certbot --nginx \
  -d "${DOMAIN_CORE}" \
  -d "${DOMAIN_ANALYSIS}" \
  -m "${EMAIL}" \
  --agree-tos \
  --redirect \
  --non-interactive

sudo certbot renew --dry-run
