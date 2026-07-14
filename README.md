# Highperformr Assessment

This project is a simple, 3-stage data processing pipeline designed to clean, enrich, and augment a list of company accounts using Python and Pandas.

## What it Does

Given a spreadsheet of accounts with some missing data (company name, domain, LinkedIn URL), the pipeline will:
1. Normalize and clean the existing data.
2. Enrich missing fields using the free Clearbit API.
3. Augment the data by identifying the CEO or founder for each company using an LLM (OpenAI).

## How to Run

### Prerequisites
- Python 3.8+
- Optional: `OPENAI_API_KEY` exported in your environment for CEO lookups.

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Execution
Run the scripts in the following order:

```bash
# Stage 1: Load and normalize the raw data
# Reads data/raw_accounts.csv -> Outputs data/cleaned_accounts.csv
python src/clean.py

# Stage 2: Enrich missing fields (domain, name, LinkedIn URL)
# Reads data/cleaned_accounts.csv -> Outputs data/enriched_accounts.csv
python src/enrich.py

# Stage 3: Identify CEO/founder
# Reads data/enriched_accounts.csv -> Outputs output/final_accounts.csv
python src/find_ceo.py
```

## Approach for Missing Fields

- **Missing domain, have name:** Queries Clearbit's free autocomplete API (`https://autocomplete.clearbit.com/v1/companies/suggest`) with the company name and takes the top matched domain.
- **Missing name, have domain:** Queries Clearbit with the domain root. If no match is found, it falls back to a best-effort construction by capitalizing the domain root.
- **Missing LinkedIn URL:** Best-effort constructs the URL using the format `https://www.linkedin.com/company/{domain_root}`. These are flagged in the `linkedin_guessed` column.
- **Missing everything but LinkedIn URL:** Extracts the company slug from the URL path, formats it, and uses it as a fallback company name.
- **CEO/Founder Lookup:** For each unique company, calls OpenAI's `gpt-4o-mini` model with a tight prompt to identify the current CEO/founder.

## Known Limitations

- **Free API Rate Limits:** The Clearbit API used for enrichment is a free endpoint. The script adds a small `time.sleep(0.2)` delay to be polite, but aggressive usage might still hit rate limits. Responses are cached locally to mitigate redundant calls.
- **LLM CEO Answers Unverified:** The CEO/founder lookups are purely best-effort LLM generations. They are not fact-checked against a live database and can be outdated or hallucinated. The `source` column will indicate `"llm"` when populated this way. If no API key is provided, it defaults to `"Unknown"`.
- **Guessed LinkedIn URLs:** URLs constructed manually from domain names are best-effort guesses. They may point to 404 pages or incorrect company pages if the company's actual LinkedIn slug differs from their domain root. These are transparently flagged.
