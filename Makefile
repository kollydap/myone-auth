.DEFAULT_GOAL := help

.PHONY: help build up down down-v logs ps shell test migrate makemigrations psql redis-cli

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

build: ## Build the api image
	docker compose build api

up: ## Start the full stack in the foreground (rebuilds first)
	docker compose up --build

down: ## Stop the stack, keep volumes
	docker compose down

down-v: ## Stop the stack and delete volumes (wipes the database)
	docker compose down -v

logs: ## Tail logs from all services
	docker compose logs -f

ps: ## List running services
	docker compose ps

shell: ## Open a shell in the running api container
	docker compose exec api sh

test: ## Run the test suite
	docker compose exec api pytest

migrate: ## Apply migrations
	docker compose exec api alembic upgrade head

makemigrations: ## Autogenerate a migration; usage: make makemigrations m="add users table"
	docker compose exec api alembic revision --autogenerate -m "$(m)"

psql: ## Open a psql shell against the postgres service
	docker compose exec postgres psql -U myone -d myone_auth

redis-cli: ## Open a redis-cli shell against the redis service
	docker compose exec redis redis-cli
