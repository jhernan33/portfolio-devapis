# Atajos de desarrollo del backend.
#
# `make test` tiene que funcionar desde un clon limpio y sin PostgreSQL. Sin
# eso la suite solo se ejecuta en CI, refactorizar es refactorizar a ciegas y
# los tests dejan de usarse justo cuando más falta hacen.
#
# El entorno se recrea solo cuando cambian los requirements: el fichero
# `.venv/.instalado` es la marca de tiempo que lo decide.

VENV := .venv
PY   := $(VENV)/bin/python
RUFF := $(VENV)/bin/ruff

.PHONY: test lint formato entorno limpiar ayuda

ayuda:
	@echo "make test     — ejecuta la suite (crea el entorno si hace falta)"
	@echo "make lint     — ruff check + ruff format --check, lo mismo que la CI"
	@echo "make formato  — aplica el formato de ruff"
	@echo "make limpiar  — borra el entorno y los cachés"

test: entorno
	$(PY) -m pytest

lint: entorno
	$(RUFF) check .
	$(RUFF) format --check .

formato: entorno
	$(RUFF) format .

entorno: $(VENV)/.instalado

$(VENV)/.instalado: requirements.txt requirements-dev.txt
	python3 -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements-dev.txt
	@touch $@
	@echo "Entorno listo: $$($(PY) --version)"

limpiar:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
