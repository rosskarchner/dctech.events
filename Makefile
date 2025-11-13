.PHONY: all all-cities clean clean-all force refresh-calendars generate-month-data freeze js-build validate validate-report homepage

# City configuration (defaults to DC for backward compatibility)
CITY ?= dc

# Dynamically get list of cities from config.yaml
CITIES = $(shell python -c "import yaml; print(' '.join([c['slug'] for c in yaml.safe_load(open('config.yaml'))['cities']]))")

# Default target (builds all cities)
all: all-cities

# Build all cities
all-cities: js-build
	@for city in $(CITIES); do \
		echo "Building $$city..."; \
		$(MAKE) CITY=$$city refresh-calendars generate-month-data freeze; \
	done
	@$(MAKE) homepage

# Build JavaScript bundles
js-build:
	npm run build

# Always run refresh-calendars by making it .PHONY and a prerequisite for generate-month-data
refresh-calendars:
	python refresh_calendars.py --city $(CITY)

generate-month-data: refresh-calendars
	python generate_month_data.py --city $(CITY)

freeze: generate-month-data
	python freeze.py --city $(CITY)

# Build localtech.events homepage
homepage: js-build
	python freeze.py --homepage

# Validation targets
validate:
	python .github/scripts/validate_all_existing.py

validate-report:
	python .github/scripts/validate_all_existing.py --report

clean:
	rm -rf build/
	rm -rf cities/*/_data/
	rm -rf _cache/
	rm -rf static/js/dist/

clean-all: clean
	rm -rf _cache/

force: clean-all all