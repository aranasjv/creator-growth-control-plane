# Control Plane Stack

This repository now includes a staged platform shell around the legacy CLI automation:

- `apps/web`: Next.js monitoring and KPI dashboard
- `apps/api`: ASP.NET Core orchestrator API
- `workers/python-worker`: Redis-backed desktop Python worker that executes the legacy flows
- `infra/docker-compose.yml`: shared `tech-infra` services for local projects
- `docker-compose.project.yml`: Creator Growth Control Plane project containers that attach to shared infra

## Default local ports

- Web: `http://localhost:3000`
- API: `http://localhost:5050`
- Postgres: `localhost:5432`
- Redis: `localhost:6379`
- RedisInsight: `http://localhost:8001`
- MongoDB: `localhost:27017`

## Shared Infra

The Docker stack is now named `tech-infra` and is intended to be a reusable local infra layer instead of a single-project-only stack.

- Postgres container: `tech-infra-postgres`
- Redis Stack container: `tech-infra-redis`
- MongoDB container: `tech-infra-mongo`
- Shared network: `tech-infra-network`
- Postgres volume root: `tech-infra-postgres-root`

## Project Containers

The project stack is now separated from shared infra:

- Web container: `creator-growth-control-plane-web`
- API container: `creator-growth-control-plane-api`
- Project network: `creator-growth-control-plane-app-network`

The API container joins both networks so it can talk to Postgres, Redis Stack, and MongoDB on `tech-infra-network`.
The web container only joins the project network and talks to the API container directly.
The desktop Python worker intentionally stays outside Docker so it can keep using your real Firefox profile, Ollama installation, ImageMagick path, and other host-level automation tools.

## Local setup order

1. Install desktop prerequisites with `powershell -ExecutionPolicy Bypass -File scripts/install_desktop_prereqs.ps1`
2. Install repo dependencies with `powershell -ExecutionPolicy Bypass -File scripts/setup_local.ps1`
3. Start infrastructure with `powershell -ExecutionPolicy Bypass -File scripts/start_stack.ps1`
4. Start project containers with `npm.cmd run start:project`
5. Start the hybrid workspace with `npm.cmd run start:hybrid`
6. Or stay fully local with `npm.cmd run start:desktop`
7. Start the desktop worker alone with `npm.cmd run dev:worker`

## Desktop helpers

- `scripts/configure_desktop.ps1`: fills in obvious local defaults like ImageMagick and Firefox profile paths when they already exist, and writes `.env.platform.local` plus `apps/web/.env.local`
- `scripts/smoke_test_stack.ps1`: queues a safe `smoke_test` job through the API and waits for the worker to complete it
- `scripts/start_project_stack.ps1`: builds and runs the web/API containers against `tech-infra`
- `scripts/start_hybrid_workspace.ps1`: runs web/API in Docker and opens the desktop Python worker in its own window

## Python readiness notes

- `scripts/preflight_local.py --targets twitter` validates the X/Twitter automation prerequisites
- `scripts/preflight_local.py --targets youtube` validates the YouTube prerequisites
- `scripts/preflight_local.py --targets outreach` validates the outreach prerequisites
- Browser-driven flows still need a real logged-in Firefox profile
- The YouTube flow still needs a valid `GEMINI_API_KEY` or `nanobanana2_api_key`
- Outreach still needs SMTP credentials and a niche configured in `config.json`

## Legacy data import

When the API starts, it imports the existing `.mp` cache data into the Postgres read model so the dashboard can display accounts, posts, videos, and affiliate products that already exist.

