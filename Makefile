.PHONY: install run test docker-build docker-run clean init help

# Default target
help:
	@echo "HackingUpdate — Available Commands:"
	@echo ""
	@echo "  make install        Install package in development mode"
	@echo "  make run            Run the full pipeline"
	@echo "  make init           Show project configuration"
	@echo "  make steps          Show pipeline steps"
	@echo "  make feeds          List configured feeds"
	@echo "  make notify-wa      Send WhatsApp notification"
	@echo "  make notify-teams   Send Teams notification"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run pipeline in Docker"
	@echo "  make docker-compose Run with Docker Compose"
	@echo "  make clean          Remove cache and build artifacts"
	@echo "  make test           Run tests"
	@echo ""

install:
	pip install -e ".[dev]"

run:
	hackingupdate run

init:
	hackingupdate init

steps:
	hackingupdate steps

feeds:
	hackingupdate feeds list

notify-wa:
	hackingupdate notify --whatsapp

notify-teams:
	hackingupdate notify --teams

docker-build:
	docker build -t hackingupdate .

docker-run:
	docker run --env-file .env -v ./reports:/app/reports -v ./logs:/app/logs hackingupdate

docker-compose:
	docker compose up

clean:
	rm -rf cache/*.json reports/*.html reports/*.md logs/*.log
	rm -rf dist/ build/ *.egg-info __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

test:
	pytest tests/ -v --tb=short
