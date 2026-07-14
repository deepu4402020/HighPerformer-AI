import pandas as pd
import requests
import time
import json
import os
import re
from openai import OpenAI

CACHE_FILE_CLEARBIT = "data/clearbit_cache.json"
CACHE_FILE_CEO = "data/ceo_cache.json"

def load_cache(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache, cache_file):
    with open(cache_file, "w") as f:
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
                save_cache(cache, CACHE_FILE_CLEARBIT)
                return result
    except Exception as e:
        print(f"Error querying Clearbit for {query_str}: {e}")
        
    # Cache negative result to avoid re-querying
    cache[query_str] = None
    save_cache(cache, CACHE_FILE_CLEARBIT)
    return None

def query_ceo_llm(client, company_name, domain, cache):
    if not company_name and not domain:
        return "Unknown"
        
    cache_key = f"{company_name}|{domain}"
    if cache_key in cache:
        return cache[cache_key]
        
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
        answer = answer.strip('\'".,')
    except Exception as e:
        print(f"Error querying OpenAI for {cache_key}: {e}")
        answer = "Unknown"
        
    cache[cache_key] = answer
    save_cache(cache, CACHE_FILE_CEO)
    return answer

def clean_domain(domain):
    if pd.isna(domain) or not str(domain).strip():
        return ""
    d = str(domain).lower().strip()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.split('/')[0]
    return d

def extract_domain_root(domain):
    if not domain:
        return ""
    parts = str(domain).split('.')
    if len(parts) >= 2:
        return parts[-2]
    return domain

def extract_linkedin_slug(url):
    if not url:
        return ""
    match = re.search(r'linkedin\.com/company/([^/]+)', str(url))
    if match:
        return match.group(1)
    return ""

def main():
    input_path = os.path.join("data", "raw_accounts.csv")
    output_dir = "output"
    output_path = os.path.join(output_dir, "final_accounts.csv")
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print("Loading data...")
    # Handle the specific TSV format
    df = pd.read_csv(input_path, sep='\t')
    
    # Map input columns to our standard schema
    col_mapping = {
        'input-company-name': 'company_name',
        'input-company-domain': 'domain'
    }
    df.rename(columns=col_mapping, inplace=True)
    
    if 'company_name' not in df.columns: df['company_name'] = ""
    if 'domain' not in df.columns: df['domain'] = ""
    if 'linkedin_url' not in df.columns: df['linkedin_url'] = ""
    
    df = df[['company_name', 'domain', 'linkedin_url']]
    
    # Cleaning Phase
    print("Cleaning accounts data...")
    df['domain'] = df['domain'].apply(clean_domain)
    
    def clean_name(row):
        name = str(row['company_name']).strip()
        if pd.isna(row['company_name']) or not name:
            return ""
        if row['domain'] and (row['domain'] in name.lower() or name.lower() in row['domain']):
            if len(name.split()) == 1 and ('.' in name):
                return ""
        return row['company_name']
        
    df['company_name'] = df.apply(clean_name, axis=1)
    
    for col in df.columns:
        df[col] = df[col].fillna('').astype(str)
        
    df = df.drop_duplicates(subset=['domain'], keep='first')
    
    # Enrichment Phase
    print("Enriching accounts data...")
    clearbit_cache = load_cache(CACHE_FILE_CLEARBIT)
    
    if 'linkedin_guessed' not in df.columns:
        df['linkedin_guessed'] = False
        
    for index, row in df.iterrows():
        name = str(row['company_name']).strip()
        domain = str(row['domain']).strip()
        linkedin = str(row['linkedin_url']).strip()
        guessed_li = False
        
        if not name and not domain and linkedin:
            slug = extract_linkedin_slug(linkedin)
            if slug:
                name = slug.replace('-', ' ').title()
                df.at[index, 'company_name'] = name
                
        if not domain and name:
            result = query_clearbit(name, clearbit_cache)
            if result and 'domain' in result:
                domain = result['domain']
                df.at[index, 'domain'] = domain
                
        if not name and domain:
            domain_root = extract_domain_root(domain)
            result = query_clearbit(domain_root, clearbit_cache)
            if result and 'name' in result:
                name = result['name']
            else:
                name = domain_root.title()
            df.at[index, 'company_name'] = name
            
        if not linkedin and domain:
            domain_root = extract_domain_root(domain)
            if domain_root:
                linkedin = f"https://www.linkedin.com/company/{domain_root}"
                guessed_li = True
                df.at[index, 'linkedin_url'] = linkedin
                df.at[index, 'linkedin_guessed'] = guessed_li

    # CEO Discovery Phase
    print("Discovering CEOs and Founders...")
    ceo_cache = load_cache(CACHE_FILE_CEO)
    api_key = os.environ.get("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key) if api_key else None
    
    if not client:
        print("Warning: OPENAI_API_KEY environment variable not set. CEO lookup will default to 'Unknown'.")
        
    if 'ceo_founder' not in df.columns: df['ceo_founder'] = ""
    if 'source' not in df.columns: df['source'] = ""
        
    for index, row in df.iterrows():
        name = row.get('company_name', '').strip()
        domain = row.get('domain', '').strip()
        
        ceo = query_ceo_llm(client, name, domain, ceo_cache)
        
        df.at[index, 'ceo_founder'] = ceo
        df.at[index, 'source'] = "llm" if (ceo and ceo.lower() != "unknown" and client) else ""
        
    # Write final output
    df.to_csv(output_path, index=False)
    print(f"Process complete. Data saved to {output_path}")

if __name__ == "__main__":
    main()
