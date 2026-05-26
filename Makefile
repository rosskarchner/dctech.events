.PHONY: all clean force refresh-calendars generate-month-data freeze js-build validate validate-report

CALGEN = .venv/bin/calgen

all: js-build refresh-calendars generate-month-data freeze

js-build:
	npm run build

refresh-calendars:
	$(CALGEN) refresh

generate-month-data: refresh-calendars
	$(CALGEN) pipeline

freeze: generate-month-data
	$(CALGEN) build --output-dir build/dctech

validate:
	python .github/scripts/validate_all_existing.py

validate-report:
	python .github/scripts/validate_all_existing.py --report

clean:
	rm -rf build/
	rm -rf _data/
	rm -rf _cache/
	rm -rf static/js/dist/

test:
	PYTHONPATH=. ./.venv/bin/python -m pytest . --ignore=oauth-endpoint --cov=app --cov=location_utils --cov=generate_month_data

test-oauth:
	cd oauth-endpoint && ../.venv/bin/python -m pytest test_oauth_app.py

test-all: test test-oauth

force: clean all
