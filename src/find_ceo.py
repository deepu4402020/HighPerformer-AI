import pandas as pd
import os
import json
from openai import OpenAI

CACHE_FILE = "data/ceo_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def query_ceo_llm(client, company_name, domain, cache):
    if not company_name and not domain:
        return "Unknown"
        
    cache_key = f"{company_name}|{domain}"
    if cache_key in cache:
        return cache[cache_key]
        
    # If client is None, it means no API key was provided
    if client is None:
        return "Unknown"
        
    prompt = f"Who is the current CEO or founder of {company_name} (domain: {domain})? Reply with just the name, or 'Unknown' if you're not confident."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that identifies company CEOs and founders. Provide only the name."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=20
        )
        answer = response.choices[0].message.content.strip()
        # Clean up any quotes or extra punctuation just in case
        answer = answer.strip('\'".,')
    except Exception as e:
        print(f"Error querying OpenAI for {cache_key}: {e}")
        answer = "Unknown"
        
    cache[cache_key] = answer
    save_cache(cache)
    return answer

def main():
    print("Loading enriched accounts...")
    input_path = os.path.join("data", "enriched_accounts.csv")
    output_dir = "output"
    output_path = os.path.join(output_dir, "final_accounts.csv")
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found. Run enrich.py first.")
        return
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    df = pd.read_csv(input_path)
    # Convert nans to empty strings safely
    for col in df.columns:
        df[col] = df[col].fillna('').astype(str)
        
    cache = load_cache()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key) if api_key else None
    
    if not client:
        print("Warning: OPENAI_API_KEY environment variable not set. CEO lookup will default to 'Unknown'.")
        
    # We add columns
    if 'ceo_founder' not in df.columns:
        df['ceo_founder'] = ""
    if 'source' not in df.columns:
        df['source'] = ""
        
    # Iterate and find CEO
    for index, row in df.iterrows():
        name = row.get('company_name', '').strip()
        domain = row.get('domain', '').strip()
        
        ceo = query_ceo_llm(client, name, domain, cache)
        
        df.at[index, 'ceo_founder'] = ceo
        df.at[index, 'source'] = "llm" if (ceo and ceo.lower() != "unknown" and client) else ""
        
    df.to_csv(output_path, index=False)
    print(f"Final data saved to {output_path}")

if __name__ == "__main__":
    main()
