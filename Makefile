.PHONY: install seed demo api streamlit test lint clean docker-up docker-down

install:
	pip install -e ".[dev]"

seed:
	python -m data.seed

demo: seed
	python -m src.graph

api:
	uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

streamlit:
	streamlit run streamlit_app.py

test:
	pytest -v

lint:
	ruff check src tests data
	ruff format --check src tests data

format:
	ruff format src tests data

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__ src/__pycache__ src/agents/__pycache__ tests/__pycache__
	find . -name "*.pyc" -delete

docker-up:
	docker compose up -d

docker-down:
	docker compose down
