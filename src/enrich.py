import pandas as pd
import requests
import time
import json
import os
import re

CACHE_FILE = "data/clearbit_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def query_clearbit(query_str, cache):
    if not query_str:
        return None
        
    query_str = str(query_str).strip()
    if not query_str:
        return None
        
    # Check cache first
    if query_str in cache:
        return cache[query_str]
        
    url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={query_str}"
    
    try:
        time.sleep(0.2)  # Be polite to the free API
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                result = data[0]
                cache[query_str] = result
                save_cache(cache)
                return result
    except Exception as e:
        print(f"Error querying Clearbit for {query_str}: {e}")
        
    # Cache negative result to avoid re-querying
    cache[query_str] = None
    save_cache(cache)
    return None

def extract_domain_root(domain):
    if not domain:
        return ""
    # strip extensions or paths, keeping the main part
    parts = str(domain).split('.')
    if len(parts) >= 2:
        return parts[-2]
    return domain

def extract_linkedin_slug(url):
    if not url:
        return ""
    # usually https://www.linkedin.com/company/slug
    match = re.search(r'linkedin\.com/company/([^/]+)', str(url))
    if match:
        return match.group(1)
    return ""

def main():
    print("Loading cleaned accounts...")
    input_path = os.path.join("data", "cleaned_accounts.csv")
    output_path = os.path.join("data", "enriched_accounts.csv")
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found. Run clean.py first.")
        return
        
    df = pd.read_csv(input_path)
    for col in ['company_name', 'domain', 'linkedin_url']:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    
    cache = load_cache()
    
    # We will add a 'linkedin_guessed' column to be transparent about guessed URLs
    if 'linkedin_guessed' not in df.columns:
        df['linkedin_guessed'] = False
        
    for index, row in df.iterrows():
        name = str(row['company_name']).strip()
        domain = str(row['domain']).strip()
        linkedin = str(row['linkedin_url']).strip()
        guessed_li = False
        
        # Missing everything but linkedin?
        if not name and not domain and linkedin:
            slug = extract_linkedin_slug(linkedin)
            if slug:
                name = slug.replace('-', ' ').title()
                df.at[index, 'company_name'] = name
                
        # Missing domain, have name
        if not domain and name:
            result = query_clearbit(name, cache)
            if result and 'domain' in result:
                domain = result['domain']
                df.at[index, 'domain'] = domain
                
        # Missing name, have domain
        if not name and domain:
            domain_root = extract_domain_root(domain)
            result = query_clearbit(domain_root, cache)
            if result and 'name' in result:
                name = result['name']
            else:
                # Fallback to domain root
                name = domain_root.title()
            df.at[index, 'company_name'] = name
            
        # Missing LinkedIn URL
        if not linkedin and domain:
            domain_root = extract_domain_root(domain)
            if domain_root:
                linkedin = f"https://www.linkedin.com/company/{domain_root}"
                guessed_li = True
                df.at[index, 'linkedin_url'] = linkedin
                df.at[index, 'linkedin_guessed'] = guessed_li
                
    df.to_csv(output_path, index=False)
    print(f"Enriched data saved to {output_path}")

if __name__ == "__main__":
    main()
