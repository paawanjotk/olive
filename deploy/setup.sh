#!/bin/bash
# One-time setup for a fresh DigitalOcean Ubuntu droplet.
# Run as root: bash setup.sh
#
# After this script: push to main and GitHub Actions will handle all future deploys.

set -e

REPO_URL="${1:-https://github.com/YOUR_GITHUB_USER/YOUR_REPO.git}"
DEPLOY_DIR="/opt/ollive"

echo "==> Installing Docker..."
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

echo "==> Installing Docker Compose plugin..."
apt-get install -y docker-compose-plugin 2>/dev/null || true
# Verify
docker compose version

echo "==> Opening firewall ports (80 + 443 for Caddy SSL)..."
ufw allow 22/tcp   # SSH — keep open
ufw allow 80/tcp   # HTTP (Caddy ACME challenge + redirect)
ufw allow 443/tcp  # HTTPS
ufw allow 443/udp  # HTTP/3 (QUIC)
ufw --force enable

echo "==> Cloning repo to $DEPLOY_DIR..."
mkdir -p "$DEPLOY_DIR"
git clone "$REPO_URL" "$DEPLOY_DIR"

echo ""
echo "==> Setup complete. Next steps:"
echo ""
echo "  1. Add the following GitHub Actions secrets to your repo"
echo "     (Settings → Secrets and variables → Actions):"
echo ""
echo "     DO_SSH_KEY     — the private SSH key for root@139.59.10.53"
echo "                      (add the matching public key to /root/.ssh/authorized_keys)"
echo ""
echo "     PROD_ENV_B64   — base64-encoded .env file, e.g.:"
echo "       base64 -w0 /opt/ollive/.env   # paste this value as the secret"
echo ""
echo "  2. Create /opt/ollive/.env from backend/.env.example and fill in:"
echo "       BACKEND_IMAGE=ghcr.io/<github-user>/ollive-backend"
echo "       POSTGRES_PASSWORD=<strong-password>"
echo "       ANTHROPIC_API_KEY=..."
echo "       SUPABASE_URL=..."
echo "       BACKEND_URL=https://139-59-10-53.sslip.io"
echo "       FRONTEND_URL=https://<your-frontend-domain>"
echo ""
echo "  3. Base64-encode the .env and store as PROD_ENV_B64 secret:"
echo "       cat /opt/ollive/.env | base64 -w0"
echo ""
echo "  4. Push to main — GitHub Actions will build, push, and deploy."
echo ""
echo "  Your API will be live at: https://139-59-10-53.sslip.io"
echo "  WebSocket endpoint:       wss://139-59-10-53.sslip.io/api/v1/ws/..."
