# DevOps / Deployment / Infra

**Owner:** Lokendra Rajawat &lt;rajawatlokendra2003@gmail.com&gt;

Everything required to build, ship, and run the platform — containers, reverse
proxy, CI/CD, and runtime configuration.

## Scope

- **Containers** — Dockerfiles and dev/prod `docker-compose` stacks
  (`backend/Dockerfile`, `backend/docker-compose.yml`,
  `docker-compose.prod.yml`, `backend/docker-compose-prod.yml`).
- **Reverse proxy** — Caddy configuration including socket support
  (`Caddyfile`).
- **CI/CD** — GitHub Actions for build and deploy
  (`.github/workflows/ci.yml`, `deploy.yml`) and deploy scripts (`deploy/`).
- **Runtime config** — environment/config handling, CORS, ports, WebSocket
  URL, and database URL wiring (`backend/app/core/config.py`, `.env.example`).
- **Project setup** — README, GitHub templates, and seed scripts
  (`seed_templates.py`, `seed_demo_workflows.py`).

## Highlights

- Stood up the dev and production container stacks and Caddy proxy.
- Wired CI/CD pipelines and deployment scripts.
- Hardened runtime configuration: CORS, ports, env keys, and DB URL handling.
