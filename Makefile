.PHONY: all fetch generate freeze clean

# Default target
all: fetch generate freeze

# Phase 1: Fetch iCal files
fetch:
	@echo "Phase 1: Fetching iCal files..."
	python aggregator.py

# Phase 2: Generate YAML files if needed
generate:
	@echo "Phase 2: Generating YAML files if needed..."
	@if [ -f _data/.updated ] || [ -f _data/current_day.txt ] && [ "$$(cat _data/current_day.txt)" != "$$(date +%Y-%m-%d)" ]; then \
		echo "Changes detected or day changed, regenerating YAML files..."; \
		python aggregator.py --force; \
		rm -f _data/.updated; \
	else \
		echo "No changes detected, skipping YAML generation."; \
	fi

# Freeze the Flask app if there are changes
freeze:
	@echo "Freezing Flask app..."
	@if [ -f _data/.updated ] || [ ! -d build ] || [ ! -f _data/current_day.txt ] || [ "$$(cat _data/current_day.txt)" != "$$(date +%Y-%m-%d)" ]; then \
		echo "Changes detected, build directory missing, or day changed, freezing app..."; \
		python freeze.py; \
	else \
		echo "No changes detected, skipping freeze."; \
	fi

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build
	rm -rf _cache
	rm -f _data/.updated
	rm -f _data/current_day.txt

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r app/requirements.txt
	pip install -r aggregator-requirements.txt