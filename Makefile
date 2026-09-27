PYTHON ?= python
.PHONY: setup dev ingest test eval eval-jev eval-hybrid eval-system-one security-test compare lint typecheck build verify
setup:
	$(PYTHON) -m pip install -e ".[dev,eval,jev]"
	cd frontend && npm ci
dev:
	$(PYTHON) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
ingest:
	$(PYTHON) -m scripts.ingest
test:
	$(PYTHON) -m pytest
eval:
	$(PYTHON) -m evals.runners.run --suite deepeval
eval-jev:
	$(PYTHON) -m evals.runners.run --suite jev
eval-hybrid:
	$(PYTHON) -m evals.runners.run --suite deepeval --eval-mode hybrid
eval-system-one:
	$(PYTHON) -m evals.runners.run --suite deepeval --eval-mode system_one
security-test:
	$(PYTHON) -m pytest backend/tests -m security
compare:
	$(PYTHON) -m evals.runners.compare
lint:
	$(PYTHON) -m ruff check backend evals scripts
	cd frontend && npm run lint
typecheck:
	$(PYTHON) -m mypy backend
	cd frontend && npm run typecheck
build:
	$(PYTHON) -m build
	cd frontend && npm run build
verify:
	$(PYTHON) -m scripts.verify
