.PHONY: install test collect enrich stats demo clean

install:
	pip install -r requirements.txt

test:
	PYTHONPATH=src python3 -m pytest -q

collect:
	PYTHONPATH=src python3 -m leadharvest.cli collect --from-api --out demo/raw.json

enrich:
	PYTHONPATH=src python3 -m leadharvest.cli enrich demo/raw.json \
		-o demo/leads.xlsx --report demo/rejected.csv

stats:
	PYTHONPATH=src python3 -m leadharvest.cli stats demo/leads.xlsx

demo: collect enrich stats
	PYTHONPATH=src python3 -m leadharvest.cli enrich samples/leads_raw.csv \
		-o demo/leads_from_csv.csv

clean:
	rm -f leads.xlsx leads.csv leads.json rejected.csv raw.json
	find . -name __pycache__ -type d -exec rm -rf {} +
	rm -rf .pytest_cache
