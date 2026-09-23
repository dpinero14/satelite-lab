PY ?= python
VENV ?= .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
BIN := $(VENV)/Scripts
endif

.PHONY: setup test data serie notebooks

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements.txt
	$(BIN)/python -m ipykernel install --user --name satelite-lab --display-name "satelite-lab"

test:
	$(BIN)/python -m pytest -q tests

data:
	$(BIN)/python scripts/download_data.py

serie:
	$(BIN)/python scripts/run_series.py 152 2017-01-01 2026-12-31 --por-mes 2
	$(BIN)/python scripts/run_series.py 9 2025-09-01 2026-12-31 --por-mes 2
	$(BIN)/python scripts/run_series.py 33 2025-09-01 2026-12-31 --por-mes 2
	$(BIN)/python scripts/run_series.py 3 2025-09-01 2026-12-31 --por-mes 2

notebooks:
	$(BIN)/python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=satelite-lab --ExecutePreprocessor.timeout=3600 notebooks/01_el_satelite_cuenta_camiones.ipynb
