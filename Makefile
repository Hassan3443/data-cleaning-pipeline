.PHONY: install data clean test

install:
	pip install -r requirements.txt

data:
	python src/generate_messy_data.py

clean:
	python src/clean_data.py --flag-outliers --plot figures/before_after.png

test:
	python -m pytest tests/ -q
