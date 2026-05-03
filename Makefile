.PHONY: all all-dctech all-dcstem clean clean-all force refresh-calendars refresh-calendars-dctech refresh-calendars-dcstem generate-month-data generate-month-data-dctech generate-month-data-dcstem freeze freeze-dctech freeze-dcstem js-build validate validate-report

# Default target - builds all sites
all: js-build refresh-calendars generate-month-data freeze

# Single-site targets
all-dctech: js-build refresh-calendars-dctech generate-month-data-dctech freeze-dctech
all-dcstem: js-build refresh-calendars-dcstem generate-month-data-dcstem freeze-dcstem

# Build JavaScript bundles
js-build:
	npm run build

# Multi-site calendar refresh (all sites)
refresh-calendars:
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache from S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_cache _cache || echo "Warning: Failed to sync _cache from S3"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_data _data || echo "Warning: Failed to sync _data from S3"; \
	fi
	python refresh_calendars.py --all-sites
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache to S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync _cache s3://$$DATA_CACHE_BUCKET/_cache || echo "Warning: Failed to sync _cache to S3"; \
		aws s3 sync _data s3://$$DATA_CACHE_BUCKET/_data || echo "Warning: Failed to sync _data to S3"; \
	fi

# Single-site calendar refresh
refresh-calendars-dctech:
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache from S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_cache _cache || echo "Warning: Failed to sync _cache from S3"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_data _data || echo "Warning: Failed to sync _data from S3"; \
	fi
	python refresh_calendars.py --site dctech
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache to S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync _cache s3://$$DATA_CACHE_BUCKET/_cache || echo "Warning: Failed to sync _cache to S3"; \
		aws s3 sync _data s3://$$DATA_CACHE_BUCKET/_data || echo "Warning: Failed to sync _data to S3"; \
	fi

refresh-calendars-dcstem:
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache from S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_cache _cache || echo "Warning: Failed to sync _cache from S3"; \
		aws s3 sync s3://$$DATA_CACHE_BUCKET/_data _data || echo "Warning: Failed to sync _data from S3"; \
	fi
	python refresh_calendars.py --site dcstem
	@if [ -n "$$DATA_CACHE_BUCKET" ]; then \
		echo "Syncing cache to S3 bucket: $$DATA_CACHE_BUCKET"; \
		aws s3 sync _cache s3://$$DATA_CACHE_BUCKET/_cache || echo "Warning: Failed to sync _cache to S3"; \
		aws s3 sync _data s3://$$DATA_CACHE_BUCKET/_data || echo "Warning: Failed to sync _data to S3"; \
	fi

# Multi-site month data generation (all sites)
generate-month-data: refresh-calendars
	python generate_month_data.py --all-sites

# Single-site month data generation
generate-month-data-dctech: refresh-calendars-dctech
	python generate_month_data.py --site dctech

generate-month-data-dcstem: refresh-calendars-dcstem
	python generate_month_data.py --site dcstem

# Multi-site freeze (all sites)
freeze: generate-month-data
	python freeze.py --site all

# Single-site freeze
freeze-dctech: generate-month-data-dctech
	python freeze.py --site dctech

freeze-dcstem: generate-month-data-dcstem
	python freeze.py --site dcstem

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
	PYTHONPATH=. ./.venv/bin/python -m pytest . --ignore=oauth-endpoint --cov=app --cov=location_utils --cov=generate_month_data

test-oauth:
	cd oauth-endpoint && ../.venv/bin/python -m pytest test_oauth_app.py

test-all: test test-oauth

force: clean-all all
