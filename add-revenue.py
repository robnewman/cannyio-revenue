import requests
import math
import json
import pandas as pd

from dotenv import dotenv_values
from slack_sdk import WebClient

secrets = dotenv_values(".env")

def parse_revenue_report():
    """Parse Excel spreadsheet exported from Hubspot"""
    revenue_dict = dict()
    required_fields = secrets["REQUIRED_FIELDS"].split(",")
    try:
        data = pd.read_excel(secrets["REVENUE_FILE"])
        missing_fields = [field for field in required_fields if field not in data.columns]
        if missing_fields:
            print(f"Error: The following required fields are missing: {', '.join(missing_fields)}")
            return False
        for index, row in data.iterrows():
            rid = row['Company name']
            revenue_dict[rid] = dict()
            revenue_dict[rid]['totalCustomerArr'] = row['Total Customer ARR']
            if not math.isnan(row['Total Customer ARR']):
                revenue_dict[rid]['monthlySpend'] = str(round(row['Total Customer ARR']/12))
            else:
                revenue_dict[rid]['monthlySpend'] = float('NaN')
        return(revenue_dict)
    except Exception as e:
        print(f"An error occurred: {e}")

def loop_canny_companies():
    """Return all Canny companies with full listing"""
    increment = 100 # Canny API caps increment at 100
    canny_companies = dict()
    # Loop over naively assumed total companies
    for i in range(0, int(secrets["TOTAL_COMPANIES"]), increment):
        companies = get_canny_companies(secrets["API_KEY"], increment, i)
        for c in companies["companies"]:
            cid = c['name']
            canny_companies[cid] = c
    return canny_companies

def get_canny_companies(api_key, limit, skip):
    """Return Canny companies in increments"""
    payload = {
        "apiKey": {api_key},
        "limit": {limit},
        "skip": {skip}
    }
    url = "https://canny.io/api/v1/companies/list"
    try:
        response = requests.post(url, params=payload)
        response.raise_for_status()  # Check for errors
        companies = response.json()
        return companies
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

def check_canny_companies(companies_mrr, canny_companies):
    """Check Canny Company names w/ revenue report company names

    Compare dictionaries and if a match found, update
    the monthly spend. If company names are missing,
    return as a list and post to Slack.
    """
    missing_companies = []
    for c in canny_companies:
        if c not in companies_mrr:
            missing_companies.append(c)
        else:
            canny_companies[c]["monthlySpend"] = companies_mrr[c]["monthlySpend"]
            update_canny_company(secrets["API_KEY"], canny_companies[c])

    message ="Canny.io Company with naming mismatch to revenue report:\n"
    joined_companies = '\n'.join(missing_companies)

    if len(missing_companies) > 0:
        client = WebClient(token=secrets["SLACKBOT_OAUTH_TOKEN"])
        client.chat_postMessage(
            channel = secrets["SLACK_CHANNEL"],
            text = message + joined_companies,
            username = "Bot User"
        )
    else:
        print("No Canny Companies missing MRR")
    return 0

def update_canny_company(api_key, payload):
    """Update company in Canny"""
    payload["apiKey"] = api_key

    url = "https://canny.io/api/v1/companies/update"
    try:
        response = requests.post(
            url,
            data = json.dumps(payload),
            headers = {
                'Content-Type':"application/json"
            }
        )
        response.raise_for_status()  # Check for errors
        companies = response.json()
        return 0
    except requests.exceptions.RequestException as e:
        print(f"Error: {e} using company name '{payload['name']}' and MRR of {payload['monthlySpend']}")
        return None

if __name__ == "__main__":
    mrr_by_company = parse_revenue_report()
    canny_companies = loop_canny_companies()
    check_canny_companies(mrr_by_company, canny_companies)
