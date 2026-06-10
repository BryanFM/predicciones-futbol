.PHONY: setup dev dev-postgres db-up db-down db-reset logs install clean-cache verify-deploy

ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

clean-cache:
	@find "$(ROOT)" -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.ruff_cache' \) -exec rm -rf {} + 2>/dev/null || true
	@find "$(ROOT)" -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "→ Caché de Python eliminada. Recarga el navegador con Cmd+Shift+R (Mac) o Ctrl+Shift+R."

setup:
	@chmod +x scripts/*.sh run.sh
	@./scripts/setup-dev.sh

install: setup

dev:
	@./run.sh

dev-postgres: db-up
	@echo "→ Esperando PostgreSQL..."
	@until docker compose exec -T db pg_isready -U predicciones -d predicciones >/dev/null 2>&1; do sleep 1; done
	@source .venv/bin/activate && pip install -q 'psycopg2-binary>=2.9.10' || true
	@DATABASE_URL=postgresql://predicciones:predicciones@localhost:5432/predicciones ./run.sh

db-up:
	@docker compose up -d
	@echo "→ PostgreSQL en localhost:5432"

db-down:
	@docker compose down

db-reset:
	@./scripts/reset-db.sh

logs:
	@docker compose logs -f db

verify-deploy:
	@chmod +x scripts/verify-deploy.sh
	@./scripts/verify-deploy.sh
