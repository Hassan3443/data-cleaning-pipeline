.PHONY: install data clean audit test

install:
	pip install -r requirements.txt

data:
	python src/generate_messy_data.py

clean:
	python src/clean_data.py --flag-outliers --plot figures/before_after.png

audit:
	python src/audit.py

test:
	python -m pytest tests/ -q
	node --test tests/js/check.test.js
