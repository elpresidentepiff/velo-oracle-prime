# OpenClaw Integration Guide

This document outlines how to feed race card data from OpenClaw into VÉLØ Oracle Prime.

## Data Ingestion Pipeline

1.  **Drop Zone:** Place your race card files (CSV or JSON) into the following directory:
    `/home/ubuntu/velo-oracle-prime/data/incoming/openclaw`

2.  **File Format:**
    The system expects files with at least the following columns:
    *   `Time`: Race time (e.g., "13:50")
    *   `Horse`: Horse name
    *   `Odds`: Current odds (decimal or fractional)
    *   `Jockey`: Jockey name (Optional but recommended)
    *   `Trainer`: Trainer name (Optional but recommended)
    *   `OR`: Official Rating (Optional)
    *   `RPR`: Racing Post Rating (Optional)
    *   `TS`: Top Speed (Optional)

3.  **Ingestion Process:**
    Run the ingestion script to process new files:
    ```bash
    python3 /home/ubuntu/velo-oracle-prime/ingest_openclaw.py
    ```

    The script will:
    *   Validate the file format.
    *   Normalize the data.
    *   Update the internal VÉLØ database (ledger.json).
    *   Move processed files to `/home/ubuntu/velo-oracle-prime/data/processed`.

## Automation

To automate this process, you can set up a cron job to run the script every minute:
```bash
* * * * * /usr/bin/python3 /home/ubuntu/velo-oracle-prime/ingest_openclaw.py >> /home/ubuntu/velo-oracle-prime/ingest.log 2>&1
```

## Troubleshooting

Check the log file `ingest.log` for any errors during processing. Ensure file permissions allow the script to read from the incoming directory and write to the processed directory.
