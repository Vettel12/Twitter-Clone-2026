# Makefile for Twitter Clone 2026

.PHONY: help install dev-install lint format type-check test security clean \
        docker-up docker-down docker-logs db-migrate db-seed \
        k8s-deploy k8s-delete k8s-logs locust

help:
	@echo "Twitter Clone 2026 — Helpful Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install          — Install dependencies"
	@echo "  make dev-install      — Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make dev              — Run FastAPI server with auto-reload"
	@echo "  make test             — Run tests with coverage"
	@echo "  make lint             — Check code with ruff"
	@echo "  make format           — Format code with ruff"
	@echo "  make type-check       — Check types with mypy"
	@echo "  make security         — Run security checks (bandit, safety)"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make docker-up        — Start all services (Docker Compose)"
	@echo "  make docker-down      — Stop all services"
	@echo "  make docker-logs      — Show logs from all containers"
	@echo "  make db-migrate       — Run database migrations"
	@echo "  make db-seed          — Seed database with test data"
	@echo ""
	@echo "Kubernetes:"
	@echo "  make k8s-deploy       — Deploy to Kubernetes"
	@echo "  make k8s-delete       — Delete from Kubernetes"
	@echo "  make k8s-logs         — Show logs from K8s pods"
	@echo ""
	@echo "Testing:"
	@echo "  make locust           — Run load testing with Locust"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            — Clean up cache and build files"

# === Installation ===

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

# === Development ===

dev:
	uvicorn services.gateway.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term

lint:
	ruff check .

format:
	ruff format .
	ruff check . --fix

type-check:
	mypy .

security:
	bandit -r services/ libs/ -ll
	safety check

# === Docker Compose ===

docker-up:
	docker-compose -f deploy/docker-compose.yml up --build -d
	@echo "⏳ Waiting for services to start..."
	@sleep 10
	@echo "✅ Services started. Checking status..."
	docker-compose -f deploy/docker-compose.yml ps

docker-down:
	docker-compose -f deploy/docker-compose.yml down

docker-logs:
	docker-compose -f deploy/docker-compose.yml logs -f

docker-clean:
	docker-compose -f deploy/docker-compose.yml down -v
	@echo "✅ All volumes removed"

db-migrate:
	docker-compose -f deploy/docker-compose.yml exec app alembic upgrade head
	@echo "✅ Database migrations applied"

db-seed:
	docker-compose -f deploy/docker-compose.yml exec app python scripts/seed_db.py
	@echo "✅ Database seeded with test data"

# === Quick Start ===

quick-start: docker-up db-migrate db-seed
	@echo ""
	@echo "🎉 Quick Start Complete!"
	@echo ""
	@echo "📝 API Documentation: http://localhost:8000/docs"
	@echo "🎛️  Kafdrop (Kafka UI): http://localhost:9000"
	@echo ""
	@echo "🧪 Test API:"
	@echo "  curl -H 'api-key: test' http://localhost:8000/api/users/me"

# === Kubernetes ===

k8s-deploy:
	kubectl apply -f deploy/k8s/00-namespace.yaml
	kubectl apply -f deploy/k8s/01-configmap.yaml
	kubectl apply -f deploy/k8s/02-secrets.yaml
	kubectl apply -f deploy/k8s/03-postgres.yaml
	kubectl apply -f deploy/k8s/04-redis.yaml
	kubectl apply -f deploy/k8s/05-kafka.yaml
	kubectl apply -f deploy/k8s/07-backend.yaml
	kubectl apply -f deploy/k8s/10-media-pvc.yaml
	kubectl apply -f deploy/k8s/11-ingress.yaml
	@echo "✅ Kubernetes resources deployed"

k8s-delete:
	kubectl delete namespace twitter-clone
	@echo "✅ Kubernetes namespace deleted"

k8s-logs:
	kubectl logs -l app=backend -n twitter-clone --tail=50 -f

k8s-port-forward:
	kubectl port-forward svc/backend-service -n twitter-clone 8000:8000

# === Testing ===

locust:
	locust -f locustfile.py --host=http://localhost:8000

# === Cleanup ===

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cache and build files cleaned"
