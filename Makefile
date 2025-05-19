# Makefile for DC Tech Events

.PHONY: all fetch generate freeze clean

all: fetch generate freeze

fetch:
        python aggregator.py

generate:
        python aggregator.py --force

freeze:
        python freeze.py

clean:
        rm -rf build
        rm -rf _cache/*.meta