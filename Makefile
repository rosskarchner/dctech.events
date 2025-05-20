.PHONY: all clean clean-all force refresh-calendars generate-month-data freeze

all: generate-month-data freeze

_data/.refreshed:
	mkdir -p _data
	python refresh_calendars.py
	touch _data/.refreshed

generate-month-data: _data/.refreshed
	python generate_month_data.py

freeze: generate-month-data
	python freeze.py

clean:
	rm -rf build/
	rm -f _data/.refreshed
	rm -f _data/*.yaml

clean-all: clean
	rm -rf _cache/

force: clean-all all