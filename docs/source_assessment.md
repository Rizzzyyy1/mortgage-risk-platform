# Phase 1A — Source assessment and data inventory

## Scope and status

This document records the current evidence for the source assessment phase of the mortgage risk platform. The project is intentionally bounded to evidence available in the local workspace and to the verified official source documentation in the browser.

### Current project state
- The project root is initialized and verified for the foundation phase.
- A local sample file is present at `data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv`.
- The sample file remains unchanged and was validated for checksum and physical format before any transformation work.
- The project has not yet completed authenticated Data Dynamics access for the full historical package, and the official glossary/file-layout PDF remains a blocker for exact official field-name verification.

## Verified local sample facts

### File identity and checksum
- File: `data/raw/fannie_mae_loan_performance/sf-loan-performance-data-sample.csv`
- Size: 192,742 bytes
- SHA-256: `c3f773e86e037986a966a35cdd39577a82fa5f7b9efd073d838b1417fea9b5b2`
- File was read in place without modification or re-encoding.

### Physical format
- Encoding: `utf-8-sig`
- Line ending: CRLF
- Delimiter: `|` (pipe), not comma
- Header row: no header row detected; the first row begins with a leading empty field followed by a loan identifier and monthly reporting values
- Record count: 757 non-empty rows
- Blank records: 0 blank rows
- Field-count consistency: all rows contain 108 fields
- Malformed rows: none detected in the local sample by row-length checks; the file is physically consistent on read

### Sample profile
- Distinct loans: 8
- Reporting range: `012010` through `122019` (132 distinct months)
- Observations per loan: minimum 35, median 121, maximum 131
- Duplicate loan-month keys: none
- Conflicting duplicate loan-month keys: none
- One row represents one loan-month observation within the sample panel
- The sample contains both static origination attributes (repeated across rows) and monthly performance values (changing over time)

### Data-quality notes from the sample itself
- The file is physically consistent and readable as a fixed-width-by-delimiter row structure.
- The sample uses empty strings for missing values rather than a sentinel numeric value.
- There is no evidence of malformed rows or row-length drift in the sample.
- The file is a sample panel, not a full acquisition-quarter historical package, and it should not be treated as representative of the entire Fannie Mae population.

### Verified official-source facts

### Public official product page
The official product page was successfully opened in a browser at:
- https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data

The page states the following verified facts:
- The product is the Fannie Mae Single-Family Loan Performance Data.
- Data access is through Data Dynamics, with a direct access link at https://capitalmarkets.fanniemae.com/tools-applications/data-dynamics.
- Fannie Mae requires users to register and create a username and password to access the data.
- Users must accept the applicable terms and conditions before access.
- The product includes acquisition and performance data; the official page says the primary dataset includes acquisition and performance data for each acquisition quarter and updated data as of the previous quarter.
- The page describes the primary dataset and HARP dataset, with a mapping key for HARP loan alignment.
- The page lists a sample file, FAQs, a tutorial, the glossary and file layout document, and R code resources.

### Data Dynamics access page
The Data Dynamics page was successfully opened at:
- https://capitalmarkets.fanniemae.com/tools-applications/data-dynamics

The page confirms:
- Data Dynamics is the official data access platform for Fannie Mae data products.
- It is a free platform intended for market participants.
- Access is gated by user registration and terms acceptance.
- There are downloadable data-related resources and dashboards, but the page does not replace the product-level source documentation.

### Browser access distinction
The earlier terminal requests that returned 403 responses were not a valid proof that the official product is unavailable. They only show that automated direct HTTP requests to guessed URLs are blocked by Cloudflare and bot-protection challenges from this environment.

This project therefore distinguishes:
- public-documentation verification: complete for the official Fannie Mae product page and Data Dynamics page,
- authenticated download access: pending user registration and approval,
- local data inspection: pending actual download and verification.

## Verified public-documentation facts relevant to the dataset

From the official product page, the following are directly supported by the source and should be treated as verified public-source facts:
- The data is organized by acquisition quarter and includes monthly performance history.
- The primary dataset contains static origination data and monthly performance history from acquisition through current status until liquidation or ongoing status as of the prior quarter.
- The HARP dataset is organized similarly and includes a mapping key to align original and HARP loan identifiers.
- The available documentation includes:
  - FAQs: https://capitalmarkets.fanniemae.com/resources/file/credit-risk/pdf/sf-loan-performance-dataset-faqs.pdf
  - Glossary and file layout: https://capitalmarkets.fanniemae.com/resources/file/credit-risk/pdf/crt-file-layout-and-glossary.pdf
  - Sample file: https://capitalmarkets.fanniemae.com/resources/file/credit-risk/xls/sf-loan-performance-data-sample.csv
  - Tutorial: https://capitalmarkets.fanniemae.com/resources/file/credit-risk/pdf/loan-performance-data-tutorial.pdf
  - Access location: https://datadynamics.fanniemae.com/data-dynamics/#/reportMenu;category=HP

## What remains pending

The following items remain pending authenticated access and local data inspection:
- acceptance of registration and the required terms in Data Dynamics,
- account approval status,
- actual vendor file download from Data Dynamics,
- local confirmation of the final archive names and file layout,
- final field names, code tables, and mapping definitions from the downloaded package.

## Cohort design correction

The previous recommendation to use only one reporting month of currently active loans is not appropriate for the historical modeling dataset.

This project must distinguish two different populations:

### 1. Historical cohort used to develop and evaluate models
This is the dataset used for model development and validation. It should include historical loan-level observations for a defined acquisition quarter or a comparable window with available monthly performance history.

Required design features:
- include loans that defaulted, prepaid, were modified, or exited through other termination paths,
- retain historical performance observations rather than filtering on survival to the current date,
- include the full monthly follow-up available for the selected acquisition quarter,
- keep default and prepayment outcomes visible to inform event logic and competing-risk modeling.

### 2. Portfolio of eligible loans at a specified reporting date
This is a separate population used for current scorecard or portfolio reporting. It may include only loans eligible as of a specified reporting date, and it should be defined separately from historical training data.

This distinction is important because:
- a historical cohort with full follow-up supports model development and calibration,
- a current portfolio snapshot supports scoring and current-risk monitoring,
- filtering a historical training dataset to only surviving loans would bias the design against default and prepayment events.

### Recommended initial cohort strategy
Use one acquisition quarter with its available monthly performance history as the initial development cohort. This supports a representative historical panel while staying modest in scope. A single cohort is suitable for early schema validation and development, but it may require expansion for credible chronological evaluation, adequate default counts, and severity estimation.

The exact acquisition quarter should remain provisional until the official product page and Data Dynamics download flow confirm the available releases and the quarter that is actually accessible to the user.

## Local source inventory

### Observed workspace state
- `data/raw/`: empty
- `data/interim/`: present but empty
- `data/processed/`: present but empty
- `data/demo/`: present but empty

### Conclusion
There is no observed mortgage source data in the repository. The project must keep vendor data out of Git and keep the raw vendor archives unchanged until they are downloaded through the approved workflow.

## Guardrails

The following remain prohibited until authenticated access and local source data are verified:
- model fitting on guessed columns,
- use of assumed field names as official schema facts,
- broad portfolio assumptions without provenance,
- silent substitution of synthetic data for actual source data,
- transformation or loss calculations based on unverified files.

## Recommended next action

The next action is to complete the required Data Dynamics registration and terms acceptance in the browser through the official access route. No data download should begin until the account access path is confirmed and the specific product page instructions are read in full.

## Status summary

Status: Phase 1A is partially complete and should remain open until authenticated access is completed and the actual vendor files are inspected locally.

Verified public-source evidence:
- official Fannie Mae product page reached and read,
- Data Dynamics access page reached and read,
- registration and terms requirement verified from the official product page,
- primary dataset and HARP dataset structure and supporting documents verified at the documentation level,
- local raw data remains absent and no vendor files have been downloaded yet.

Remaining work:
- complete registration and terms acceptance in Data Dynamics,
- inspect the actual downloaded package and identify the exact file layout,
- validate field definitions and any combined-file layout in the real downloaded data files.
