# Highperformr Accounts Processor

This project provides a data processing pipeline that takes a list of raw accounts (containing sparse data like company name, domain, and LinkedIn URL) and fills in the missing information using external data sources and LLM analysis.

## What it Does

Given a spreadsheet of accounts with some missing data, the pipeline performs three main functions:
1. **Normalization & Cleaning:** Cleans up inconsistent inputs (e.g., stripping `https://`, extracting pure domain names) and deduplicates the accounts.
2. **Data Enrichment:** Identifies and fills in missing company names and domains using the free Clearbit Autocomplete API, and intelligently constructs missing LinkedIn URLs.
3. **CEO & Founder Identification:** Uses OpenAI's Large Language Models (LLM) to look up the CEO or founder for each company.

## How to Run

### Prerequisites
- Python 3.8+
- An OpenAI API Key (Set the `OPENAI_API_KEY` environment variable). If this is not set, the CEO lookup will gracefully fallback to marking the CEO as "Unknown".

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Execution
Run the main processor script:

```bash
python src/main.py
```

The script will read the raw data from `data/raw_accounts.csv` and generate a fully enriched output file at `output/final_accounts.csv`.

## Approach for Missing Fields

- **Missing domain, have name:** Queries Clearbit's autocomplete API (`https://autocomplete.clearbit.com/v1/companies/suggest`) with the company name and takes the top matched domain.
- **Missing name, have domain:** Queries Clearbit with the domain root. If no match is found, it falls back to a best-effort construction by capitalizing the domain root.
- **Missing LinkedIn URL:** Best-effort constructs the URL using the format `https://www.linkedin.com/company/{domain_root}`. These are flagged transparently in the `linkedin_guessed` column.
- **Missing everything but LinkedIn URL:** Extracts the company slug from the URL path, formats it, and uses it as a fallback company name.
- **CEO/Founder Lookup:** For each unique company, calls OpenAI's `gpt-4o-mini` model with a strict prompt to identify the current CEO/founder.

## Known Limitations

- **Free API Rate Limits:** The Clearbit API used for enrichment is a free endpoint. The script adds a small delay (`time.sleep(0.2)`) between requests to be polite. Responses are cached locally in `data/clearbit_cache.json` to mitigate redundant API calls on subsequent runs.
- **LLM Generated Information:** The CEO/founder lookups are LLM-generated. While highly accurate, they are not fact-checked against a live database and can be outdated or hallucinated. The `source` column will indicate `"llm"` when populated this way.
- **Guessed LinkedIn URLs:** URLs constructed manually from domain names are best-effort guesses. They may point to 404 pages or incorrect company pages if the company's actual LinkedIn slug differs from their domain root.
