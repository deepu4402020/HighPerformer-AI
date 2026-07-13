import pandas as pd
import re
import os

def clean_domain(domain):
    if pd.isna(domain) or not str(domain).strip():
        return ""
    d = str(domain).lower().strip()
    # Remove http://, https://, www.
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    # Remove trailing slashes and anything after it (like paths)
    d = d.split('/')[0]
    return d

def main():
    print("Loading raw accounts...")
    input_path = os.path.join("data", "raw_accounts.csv")
    output_path = os.path.join("data", "cleaned_accounts.csv")
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return
        
    df = pd.read_csv(input_path, sep='\t')
    
    col_mapping = {
        'input-company-name': 'company_name',
        'input-company-domain': 'domain'
    }
    df.rename(columns=col_mapping, inplace=True)
    
    if 'company_name' not in df.columns:
        df['company_name'] = ""
    if 'domain' not in df.columns:
        df['domain'] = ""
    if 'linkedin_url' not in df.columns:
        df['linkedin_url'] = ""

    # Drop any extra empty columns created by trailing tabs
    df = df[['company_name', 'domain', 'linkedin_url']]
    # Normalize domain
    df['domain'] = df['domain'].apply(clean_domain)
    
    # If name is just the domain or URL, it's garbage. Set to empty.
    def clean_name(row):
        name = str(row['company_name']).strip()
        if pd.isna(row['company_name']) or not name:
            return ""
        # if name looks like a domain or is exactly the domain
        if row['domain'] and (row['domain'] in name.lower() or name.lower() in row['domain']):
            # It's probably garbage if they match
            if len(name.split()) == 1 and ('.' in name):
                return ""
        return row['company_name']
        
    df['company_name'] = df.apply(clean_name, axis=1)
    
    # Ensure empty strings instead of NaN for string operations
    df.fillna('', inplace=True)
    
    # Identify missing fields
    def get_missing_fields(row):
        missing = []
        if not str(row['company_name']).strip():
            missing.append('company_name')
        if not str(row['domain']).strip():
            missing.append('domain')
        if not str(row['linkedin_url']).strip():
            missing.append('linkedin_url')
        return ",".join(missing)
        
    df['missing_fields'] = df.apply(get_missing_fields, axis=1)
    
    # Drop duplicates based on domain (if domain exists)
    # Rows without a domain might be duplicate names, but let's keep it simple: drop exact duplicates
    # We will sort to keep the one with fewer missing fields.
    df['missing_count'] = df['missing_fields'].apply(lambda x: len(x.split(',')) if x else 0)
    df.sort_values('missing_count', inplace=True)
    
    # Only drop duplicates if domain is present
    df = df.drop_duplicates(subset=['domain'], keep='first')
    
    # Drop the temporary column
    df.drop(columns=['missing_count'], inplace=True)
    
    df.to_csv(output_path, index=False)
    print(f"Cleaned data saved to {output_path}")

if __name__ == "__main__":
    main()
