SHELL := /bin/zsh

.PHONY: up down restart ps logs health build clean

up:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose down
	docker compose up -d --build

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100

health:
	@echo "API:" && curl -sS -i http://127.0.0.1:8080/health
	@echo "\nPostgres:" && docker compose exec -T postgres pg_isready -U domens -d domens
	@echo "\nRedis:" && docker compose exec -T redis redis-cli ping

build:
	docker compose build --no-cache

clean:
	docker compose down -v --remove-orphans
