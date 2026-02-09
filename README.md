# Canny Revenue Sync

## Setup

### 1. Install Dependencies with Conda

```bash
conda env create -f environment.yml
conda activate cannyio-revenue
```

Or update existing environment:
```bash
conda env update -f environment.yml --prune
```

### 2. Google Sheets API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Google Sheets API**
4. Create **Service Account** credentials
5. Download credentials JSON as `credentials.json` (save in same directory as script)
6. Open your Google Sheet
7. Click **Share** button
8. Share with the service account email (found in `credentials.json` under `client_email`)
9. Give **Viewer** permissions

### 3. Environment Variables

Your existing `.env` file needs these variables:

```
API_KEY=<canny-api-key>
SLACKBOT_OAUTH_TOKEN=<slack-oauth-token>
SLACK_CHANNEL=<slack-channel-name>
SHEET_URL=https://docs.google.com/spreadsheets/d/<sheet-id>/edit?gid=0#gid=0
```

## Usage

### Dry Run (Preview Changes First - RECOMMENDED!)

```bash
python add-revenue.py --dry-run
```

This will show you:
- Which companies will be updated (exact name matches only)
- Current monthly spend vs new monthly spend
- The dollar change for each company
- Potential fuzzy matches (display only, not updated)
- Companies with "Churned" status (skipped)
- Companies without "Active" status (skipped)
- Companies with $0 ARR (skipped, not updated)
- Companies not found in Canny
- **NO actual changes will be made**

### Apply Changes (Live Update)

```bash
python add-revenue.py
```

**Important:** Always run with `--dry-run` first to verify changes!

## Output Example (Dry Run)

```
🔍 DRY RUN MODE ENABLED - No changes will be made

Starting Canny revenue sync...

✓ Loaded 150 companies from Google Sheets
✓ Loaded 142 companies from Canny

================================================================================
DRY RUN MODE - No changes will be made
================================================================================

Note: Only EXACT name matches are updated. Fuzzy matches are shown for review only.

📝 WOULD UPDATE 87 companies (exact matches):
--------------------------------------------------------------------------------
  Company A
    Current: $XXXX/month
    New:     $XXXX/month
    Change:  +XXX

  Acme Corp
    Current: $XXXX/month
    New:     $XXXX/month
    Change:  -XXX

  [... more companies ...]

✓ 53 companies already have correct values (no change needed)

⊘ SKIPPED 12 CHURNED companies:
  - Former Customer Inc
  - Lost Deal Corp

⊘ SKIPPED 3 INACTIVE companies (not 'Active' status):
  - Prospect Company (status: Pending)

⊘ SKIPPED 8 companies with $0 ARR:
  - ABC Startup (no revenue yet)
  - Test Company Ltd
  - Trial Account Corp

🔍 POTENTIAL FUZZY MATCHES (not updated, manual review needed):
------------------------------------------------------------
  Google Sheet: 'Medicine Inc'
  Possible Canny match: 'MeDicine'
  Would set to: $XXX/month

  Google Sheet: 'Acme Corp.'
  Possible Canny match: 'Acme Corp'
  Would set to: $XXX/month

============================================================
COMPANIES NOT FOUND IN CANNY (Manual review needed)
============================================================
  - Biotech Solutions LLC
  - GeneTech Labs
  - MedDx Corporation

📧 DRY RUN: Slack notification would be sent

================================================================================
DRY RUN COMPLETE - No changes were made
================================================================================

To apply these changes, run without --dry-run flag:
  python add-revenue.py
```

## Output Example (Live Mode)

```
============================================================
🚀 LIVE MODE - Will update Canny with new values
============================================================

Starting Canny revenue sync...

✓ Loaded 161 companies from Google Sheets
✓ Loaded 123 companies from Canny

============================================================
LIVE UPDATE MODE - Making changes to Canny
============================================================

  ✓ Updated Company A to $5,125/month
  ✓ Updated Company B to $5,000/month
  ✓ Updated Company C to $4,167/month
  ✓ Updated Company D to $1,608/month
  ✓ Updated Company E to $15,417/month
  ... (37 more companies) ...

============================================================
SUMMARY
============================================================
✓ Updated (exact matches): 42 companies
🔍 Fuzzy matches found (not updated): 25 companies
⊘ Skipped (churned): 26 companies
⊘ Skipped (inactive): 1 companies
⊘ Skipped (zero revenue): 1 companies
✗ Not found in Canny: 66 companies

🔍 POTENTIAL FUZZY MATCHES (not updated, manual review needed):
------------------------------------------------------------
  Google Sheet: 'ComPaNY A'
  Possible Canny match: 'Company A'
  Would set to: $XXX/month

  Google Sheet: 'ExampleTx'
  Possible Canny match: 'Example'
  Would set to: $XXX/month

  ... (more fuzzy matches) ...

============================================================
COMPANIES NOT FOUND IN CANNY (Manual review needed)
============================================================
  - Company A
  - Company B
  - Company C
  ... (more companies) ...

✓ Sent notification to Slack
✓ Done!
```

**Note:** After updating, you may need to hard-refresh Canny (Ctrl+Shift+R or Cmd+Shift+R) to see the new values.

## Returns

The script will output a list of company names from your Google Sheet that **don't have a match** in Canny, so you can manually fix the names in either system.

**Matching behavior:**
- **Exact matches only** are updated automatically
- **Fuzzy matches** are displayed for review but NOT updated
- This gives you full control - review fuzzy matches and fix names manually before re-running

**Status filtering:**
- Companies with **"Active"** or **"Active (Churning)"** status → processed
- Companies with **"Churned"** status → skipped (listed separately)
- Companies without "Active" in status → skipped (listed separately)

Companies with **$0 ARR** will be skipped (not updated) but listed separately so you're aware of them.

The Slack notification will contain the list of companies not found in Canny.