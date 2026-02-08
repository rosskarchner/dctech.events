.PHONY: all clean clean-all force refresh-calendars generate-month-data freeze js-build validate validate-report

# Default target
all: js-build refresh-calendars generate-month-data freeze

# Build JavaScript bundles
js-build:
	npm run build

# Always run refresh-calendars by making it .PHONY and a prerequisite for generate-month-data
refresh-calendars:
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache from S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_cache _cache || echo "Warning: Failed to sync _cache from S3"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_data _data || echo "Warning: Failed to sync _data from S3"; \
	fi
	python refresh_calendars.py
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache to S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync _cache s3://$$DATA_CACHE_BUCKET/_cache || echo "Warning: Failed to sync _cache to S3"; \
		aws s3 sync _data s3://$$DATA_CACHE_BUCKET/_data || echo "Warning: Failed to sync _data to S3"; \
	fi

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
	rm -rf static/js/dist/

clean-all: clean
	rm -rf _cache/

test:
	PYTHONPATH=. ./.venv/bin/python -m pytest . --ignore=oauth-endpoint --cov=app --cov=location_utils --cov=generate_month_data --cov=address_utils

test-oauth:
	cd oauth-endpoint && ../.venv/bin/python -m pytest test_oauth_app.py

test-all: test test-oauth

force: clean-all all