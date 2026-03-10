MANAGE = /opt/netbox/netbox/manage.py
PYTHON = /opt/netbox/venv/bin/python
STATIC_DIR = netbox_pathways/static/netbox_pathways

.PHONY: help migrations migrate runserver createsuperuser shell dbshell \
	collectstatic check lint test install showurls showmigrations \
	js-install js-build js-watch js-typecheck js-clean clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Django management ---

migrations: ## Create new migrations for netbox_pathways
	$(PYTHON) $(MANAGE) makemigrations netbox_pathways

migrate: ## Apply all migrations
	$(PYTHON) $(MANAGE) migrate

runserver: ## Start the development server on 0.0.0.0:8000
	$(PYTHON) $(MANAGE) runserver 0.0.0.0:8000

createsuperuser: ## Create a superuser account
	$(PYTHON) $(MANAGE) createsuperuser

shell: ## Open Django interactive shell
	$(PYTHON) $(MANAGE) shell_plus 2>/dev/null || $(PYTHON) $(MANAGE) shell

dbshell: ## Open database shell
	$(PYTHON) $(MANAGE) dbshell

collectstatic: ## Collect static files
	$(PYTHON) $(MANAGE) collectstatic --no-input

check: ## Run Django system checks
	$(PYTHON) $(MANAGE) check

showurls: ## List all registered URL patterns
	$(PYTHON) $(MANAGE) show_urls 2>/dev/null || \
		$(PYTHON) $(MANAGE) shell -c "from django.urls import get_resolver; [print(p.pattern) for p in get_resolver().url_patterns]"

showmigrations: ## Show migration status
	$(PYTHON) $(MANAGE) showmigrations netbox_pathways

# --- JavaScript / TypeScript ---

js-install: ## Install JS build dependencies
	cd $(STATIC_DIR) && npm install

js-build: js-install ## Build TypeScript → minified JS
	cd $(STATIC_DIR) && npm run build

js-watch: js-install ## Watch mode — rebuild on save
	cd $(STATIC_DIR) && npm run watch

js-typecheck: ## Type-check TypeScript without emitting
	cd $(STATIC_DIR) && npm run typecheck

js-clean: ## Remove JS build artifacts and node_modules
	rm -rf $(STATIC_DIR)/dist $(STATIC_DIR)/node_modules

# --- Code quality ---

lint: ## Run ruff linter + TypeScript type-check
	ruff check netbox_pathways/
	cd $(STATIC_DIR) && npm run typecheck

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix netbox_pathways/

format: ## Run ruff formatter
	ruff format netbox_pathways/

format-check: ## Check formatting without modifying files
	ruff format --check netbox_pathways/

# --- Testing ---

test: ## Run test suite
	$(PYTHON) -m pytest

test-v: ## Run test suite with verbose output
	$(PYTHON) -m pytest -v

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest --cov=netbox_pathways --cov-report=term-missing --cov-report=html

# --- Install / setup ---

install: js-build ## Install plugin in editable mode (builds JS first)
	pip install -e .

install-dev: js-build ## Install plugin with dev dependencies
	pip install -e ".[dev]"

clean: js-clean ## Remove all build artifacts

# --- Plugin-specific ---

qgis-project: ## Generate QGIS project file (usage: make qgis-project URL=http://... TOKEN=...)
	$(PYTHON) $(MANAGE) generate_qgis_project --url $(URL) --token $(TOKEN)
