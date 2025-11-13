.PHONY: all clean clean-all force refresh-calendars generate-month-data freeze js-build validate validate-report homepage

# City configuration (defaults to DC for backward compatibility)
CITY ?= dc

# Default target (builds DC for backward compatibility with dctech.events)
all: js-build refresh-calendars generate-month-data freeze

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