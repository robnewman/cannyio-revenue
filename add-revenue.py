import requests
import json
import gspread
import argparse
from gspread import Client
from google.oauth2.service_account import Credentials
from dotenv import dotenv_values
from slack_sdk import WebClient
from difflib import get_close_matches

secrets = dotenv_values(".env")

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def parse_revenue_from_google_sheets():
    """Read revenue data directly from Google Sheets"""
    revenue_dict = dict()
    
    try:
        # Authenticate with Google Sheets (updated method to avoid deprecation warning)
        creds = Credentials.from_service_account_file(
            'credentials.json',
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        
        # Extract sheet ID from URL in .env
        sheet_url = secrets["SHEET_URL"]
        sheet_id = sheet_url.split('/d/')[1].split('/')[0]
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Get all records
        records = sheet.get_all_records()
        
        for row in records:
            company_name = row.get('Account Name', '').strip()
            arr = row.get('ARR (Reporting)', 0)
            status = row.get('Status', '').strip()
            
            if not company_name:
                continue
            
            revenue_dict[company_name] = dict()
            revenue_dict[company_name]['totalCustomerArr'] = arr
            revenue_dict[company_name]['status'] = status
            
            # Skip churned customers
            if status == 'Churned':
                revenue_dict[company_name]['monthlySpend'] = 'CHURNED'
                continue
            
            # Only process Active customers (including "Active (Churning)")
            if 'Active' not in status:
                revenue_dict[company_name]['monthlySpend'] = 'INACTIVE'
                continue
            
            # Convert ARR to monthly spend
            try:
                arr_value = float(str(arr).replace('$', '').replace(',', ''))
                if arr_value == 0:
                    revenue_dict[company_name]['monthlySpend'] = 'ZERO'
                else:
                    revenue_dict[company_name]['monthlySpend'] = str(round(arr_value / 12))
            except (ValueError, TypeError):
                revenue_dict[company_name]['monthlySpend'] = 'NaN'
        
        print(f"✓ Loaded {len(revenue_dict)} companies from Google Sheets")
        return revenue_dict
        
    except Exception as e:
        print(f"Error reading Google Sheets: {e}")
        return None

def loop_canny_companies():
    """Return all Canny companies with full listing"""
    increment = 100  # Canny API caps increment at 100
    canny_companies = dict()
    skip = 0
    
    while True:
        companies = get_canny_companies(secrets["API_KEY"], increment, skip)
        
        if not companies or 'companies' not in companies:
            break
        
        batch = companies['companies']
        
        if not batch:
            break
        
        for c in batch:
            cid = c['name']
            canny_companies[cid] = c
        
        skip += increment
        
        # Stop if we got fewer results than the limit
        if len(batch) < increment:
            break
    
    print(f"✓ Loaded {len(canny_companies)} companies from Canny")
    return canny_companies

def get_canny_companies(api_key, limit, skip):
    """Return Canny companies in increments"""
    # FIX: Removed curly braces around values
    payload = {
        "apiKey": api_key,
        "limit": limit,
        "skip": skip
    }
    url = "https://canny.io/api/v1/companies/list"
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        companies = response.json()
        return companies
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Canny companies: {e}")
        return None

def normalize_name(name):
    """Normalize company name for matching"""
    return name.lower().strip().replace(',', '').replace('.', '').replace(' inc', '').replace(' llc', '').strip()

def find_best_match(company_name, candidates, threshold=0.8):
    """Find best matching company name using fuzzy matching"""
    normalized = normalize_name(company_name)
    normalized_candidates = {normalize_name(c): c for c in candidates}
    
    matches = get_close_matches(normalized, normalized_candidates.keys(), n=1, cutoff=threshold)
    
    if matches:
        return normalized_candidates[matches[0]]
    return None

def check_canny_companies(companies_mrr, canny_companies, dry_run=False):
    """Match Google Sheet companies with Canny companies and update revenue
    
    NEW: Reports companies from Google Sheets that don't match Canny
    (the reverse of the original function)
    
    Args:
        companies_mrr: Dictionary of companies from Google Sheets
        canny_companies: Dictionary of companies from Canny
        dry_run: If True, show what would change without making updates
    """
    updated_count = 0
    not_in_canny = []  # Companies from Google Sheets not found in Canny
    fuzzy_matches = []  # Potential fuzzy matches (display only, no update)
    changes = []  # Track changes for dry-run display
    skipped_zero = []  # Companies with $0 ARR
    skipped_churned = []  # Churned companies
    skipped_inactive = []  # Inactive companies (not Active status)
    
    # Show update header for live mode
    if not dry_run:
        print(f"\n{'='*60}")
        print("UPDATING COMPANIES...")
        print(f"{'='*60}")
    
    for company_name, company_data in companies_mrr.items():
        monthly_spend = company_data.get('monthlySpend', 'NaN')
        
        # Skip churned customers
        if monthly_spend == 'CHURNED':
            skipped_churned.append(company_name)
            continue
        
        # Skip inactive customers
        if monthly_spend == 'INACTIVE':
            skipped_inactive.append(company_name)
            continue
        
        # Skip if $0 ARR
        if monthly_spend == 'ZERO':
            skipped_zero.append(company_name)
            continue
        
        # Skip if no valid revenue
        if monthly_spend == 'NaN':
            continue
        
        # Try exact match ONLY
        canny_company = canny_companies.get(company_name)
        
        if canny_company:
            # EXACT MATCH - proceed with update
            current_spend = canny_company.get('monthlySpend', 0)
            # Handle None values from Canny
            if current_spend is None:
                current_spend = 0
            new_spend = int(monthly_spend)
            
            # Track the change
            changes.append({
                'name': canny_company['name'],
                'current': current_spend,
                'new': new_spend,
                'changed': current_spend != new_spend
            })
            
            # Update the company (unless dry-run)
            if not dry_run:
                canny_company["monthlySpend"] = monthly_spend
                update_canny_company(secrets["API_KEY"], canny_company)
            
            updated_count += 1
        else:
            # NO EXACT MATCH - check for fuzzy match (display only)
            fuzzy_match = find_best_match(company_name, canny_companies.keys())
            if fuzzy_match:
                fuzzy_matches.append({
                    'sheet_name': company_name,
                    'canny_name': fuzzy_match,
                    'monthly_spend': monthly_spend
                })
            else:
                # No match at all
                not_in_canny.append(company_name)
    
    # Print dry-run preview or summary
    if dry_run:
        print(f"\n{'='*80}")
        print(f"DRY RUN MODE - No changes will be made")
        print(f"{'='*80}")
        print(f"\nNote: Only EXACT name matches are updated. Fuzzy matches are shown for review only.")
        
        # Show changes that would be made
        actual_changes = [c for c in changes if c['changed']]
        no_changes = [c for c in changes if not c['changed']]
        
        if actual_changes:
            print(f"\n📝 WOULD UPDATE {len(actual_changes)} companies (exact matches):")
            print(f"{'-'*80}")
            for change in actual_changes:
                print(f"  {change['name']}")
                print(f"    Current: ${change['current']:,}/month")
                print(f"    New:     ${change['new']:,}/month")
                print(f"    Change:  {'+' if change['new'] > change['current'] else ''}{change['new'] - change['current']:,}")
                print()
        
        if no_changes:
            print(f"\n✓ {len(no_changes)} companies already have correct values (no change needed)")
        
        if skipped_churned:
            print(f"\n⊘ SKIPPED {len(skipped_churned)} CHURNED companies:")
            for company in sorted(skipped_churned):
                print(f"  - {company}")
        
        if skipped_inactive:
            print(f"\n⊘ SKIPPED {len(skipped_inactive)} INACTIVE companies (not 'Active' status):")
            for company in sorted(skipped_inactive):
                print(f"  - {company}")
        
        if skipped_zero:
            print(f"\n⊘ SKIPPED {len(skipped_zero)} companies with $0 ARR:")
            for company in sorted(skipped_zero):
                print(f"  - {company}")
        
    else:
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"✓ Updated (exact matches): {updated_count} companies")
        print(f"🔍 Fuzzy matches found (not updated): {len(fuzzy_matches)} companies")
        print(f"⊘ Skipped (churned): {len(skipped_churned)} companies")
        print(f"⊘ Skipped (inactive): {len(skipped_inactive)} companies")
        print(f"⊘ Skipped (zero revenue): {len(skipped_zero)} companies")
        print(f"✗ Not found in Canny: {len(not_in_canny)} companies")
        
        if skipped_churned:
            print(f"\n⊘ Skipped CHURNED companies:")
            for company in sorted(skipped_churned):
                print(f"  - {company}")
        
        if skipped_inactive:
            print(f"\n⊘ Skipped INACTIVE companies:")
            for company in sorted(skipped_inactive):
                print(f"  - {company}")
        
        if skipped_zero:
            print(f"\n⊘ Skipped companies with $0 ARR:")
            for company in sorted(skipped_zero):
                print(f"  - {company}")
    
    if fuzzy_matches:
        print(f"\n🔍 POTENTIAL FUZZY MATCHES (not updated, manual review needed):")
        print(f"{'-'*60}")
        for match in fuzzy_matches:
            print(f"  Google Sheet: '{match['sheet_name']}'")
            print(f"  Possible Canny match: '{match['canny_name']}'")
            print(f"  Would set to: ${int(match['monthly_spend']):,}/month")
            print()
    
    # Output companies from Google Sheets not found in Canny
    if not_in_canny:
        message = "⚠️ Companies in Google Sheets NOT found in Canny:\n\n"
        message += '\n'.join(sorted(not_in_canny))
        
        print(f"\n{'='*60}")
        print("COMPANIES NOT FOUND IN CANNY (Manual review needed)")
        print(f"{'='*60}")
        for company in sorted(not_in_canny):
            print(f"  - {company}")
        
        # Send to Slack (skip in dry-run mode)
        if not dry_run:
            try:
                client = WebClient(token=secrets["SLACKBOT_OAUTH_TOKEN"])
                client.chat_postMessage(
                    channel=secrets["SLACK_CHANNEL"],
                    text=message,
                    username="Canny Revenue Bot"
                )
                print(f"\n✓ Sent notification to Slack")
            except Exception as e:
                print(f"\n⚠️  Could not send Slack message: {e}")
        else:
            print(f"\n📧 DRY RUN: Slack notification would be sent")
    else:
        print("\n✓ All companies from Google Sheets matched in Canny!")
    
    return 0

def update_canny_company(api_key, payload):
    """Update company in Canny"""
    payload["apiKey"] = api_key
    
    url = "https://canny.io/api/v1/companies/update"
    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers={'Content-Type': "application/json"}
        )
        response.raise_for_status()
        print(f"  ✓ Updated {payload.get('name', 'Unknown')} to ${payload.get('monthlySpend', 0)}/month")
        return 0
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error updating '{payload.get('name', 'Unknown')}': {e}")
        if hasattr(e.response, 'text'):
            print(f"    Response: {e.response.text}")
        return None

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Sync Google Sheets revenue data to Canny',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python add-revenue-improved.py --dry-run    # Preview changes without updating
  python add-revenue-improved.py              # Run actual updates
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without making actual updates to Canny'
    )
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE ENABLED - No changes will be made\n")
    
    print("Starting Canny revenue sync...\n")
    
    mrr_by_company = parse_revenue_from_google_sheets()
    if not mrr_by_company:
        print("Failed to load Google Sheets data")
        exit(1)
    
    canny_companies = loop_canny_companies()
    if not canny_companies:
        print("Failed to load Canny companies")
        exit(1)
    
    check_canny_companies(mrr_by_company, canny_companies, dry_run=args.dry_run)
    
    if args.dry_run:
        print("\n" + "="*80)
        print("DRY RUN COMPLETE - No changes were made")
        print("="*80)
        print("\nTo apply these changes, run without --dry-run flag:")
        print("  python add-revenue-improved.py")
    else:
        print("\n✓ Done!")