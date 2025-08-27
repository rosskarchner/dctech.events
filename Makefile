.PHONY: all clean clean-all force refresh-calendars generate-month-data freeze validate validate-report

# Default target
all: refresh-calendars generate-month-data freeze

# Always run refresh-calendars by making it .PHONY and a prerequisite for generate-month-data
refresh-calendars:
	python refresh_calendars.py

generate-month-data: refresh-calendars
	python generate_month_data.py

freeze: generate-month-data
	python freeze.py

# Validation targets
validate:
	python .github/scripts/validate_all_existing.py

validate-report:
	python .github/scripts/validate_all_existing.py --report

clean:
	rm -rf build/
	rm -rf _data/
	rm -rf _cache/

clean-all: clean
	rm -rf _cache/

force: clean-all all