# cannyio-revenue

Utility to query the Canny Companies API endpoint and return all companies,
update the company MRR value, then send a Slack notification with
the list of companies and their associated MRR.

## Overview

Simple Python script to query the [Canny.io API Companies
endpoint](https://developers.canny.io/api-reference#companies) and
return all companies. The Sales team provide a Hubspot report for all companies
that lists the ARR, which needs to be parsed, cross-referenced with the 
company name, and the company MRR (or `monthlySpend` key:value) updated
in Canny. This helps the Product team to prioritize feature requests.

The following environment variables are stored in a `.env` file and not part of this repository:

- Canny API key
- Slack OAuth token
- Slack channel name
- Total users

The `.env` file contents (in same directory as Python script):

```sh
API_KEY=<canny-api-key>
SLACKBOT_OAUTH_TOKEN=<slack-oauth-token>
SLACK_CHANNEL=<slack-channel-name>
TOTAL_COMPANIES=<total-companies-integer>
REVENUE_FILE=<relative-path-to-arr-file>
```

## Assumptions

- The Canny Companies API endpoint allows a maximum of 100 records returned (you can optionally define a `skip` value to skip N records).
- The Python script currently naively assumes a maximum of `TOTAL_COMPANIES` and iterates in blocks of 100.
- There is a working Slackbot integration with the auth token stored in the `.env` file

## Virtual environment

This script uses a virtual environment called `cannyio-revenue`. Use Conda
to recreate the environment on your localhost:

```
conda env create -f environment.yml
```

Make sure to activate the environment before running the script:

```
conda activate cannyio-revenue
```

## Run the script

Execute the script with the following Python command:

```
$ python add-revenue.py
```

- Companies that don't have revenue attached will return a 400 Bad Request because the MRR is NaN
- Companies that are not in the revenue file will be returned as a list of missing companies
