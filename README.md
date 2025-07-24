# baby-log-chatbot

A WhatsApp chatbot for tracking baby feeding, growth, and activity data with FastAPI backend.

## Features

- WhatsApp integration via Twilio
- Baby growth tracking (weight, height, head circumference)
- MPASI (solid food) intake logging with calorie estimation
- Milk intake tracking (ASI/breast milk and formula)
- Pumping session recording
- Bowel movement logging with Bristol scale
- Automated feeding reminders
- Daily activity summaries
- Visual reporting with charts and PDF reports

## New Endpoints

### `/mpasi-milk-graph/{user_phone}`
Returns a PNG chart showing daily MPASI and milk intake for the last 7 days:
- Stacked bar chart showing volume intake (ml)
- Line chart overlay showing calorie values
- Data aggregated per day from mpasi_log and milk_intake_log tables

Example: `GET /mpasi-milk-graph/+1234567890`

### `/report-mpasi-milk/{user_phone}`
Returns a PDF report containing:
- Daily intake chart (same as above endpoint)
- Summary table with daily breakdowns
- Key insights and averages for the 7-day period

Example: `GET /report-mpasi-milk/+1234567890`

## Dependencies

Core dependencies:
- fastapi==0.104.1
- uvicorn[standard]==0.24.0
- twilio==8.10.0
- psycopg2-binary==2.9.7 (PostgreSQL support)
- psycopg[binary] (PostgreSQL support)
- openai (GPT integration for calorie estimation)

New dependencies for reporting:
- matplotlib (chart generation)
- reportlab (PDF report generation)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Start the FastAPI server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Access the endpoints:
- Chart: `http://localhost:8000/mpasi-milk-graph/{user_phone}`
- PDF Report: `http://localhost:8000/report-mpasi-milk/{user_phone}`
- API Documentation: `http://localhost:8000/docs`

The endpoints work with actual database data from the baby log system, aggregating information from the last 7 days for the specified user phone number.