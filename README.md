# baby-log-chatbot

WhatsApp chatbot for baby logging with MPASI & Milk intake tracking and reporting.

## New Features: MPASI & Milk Intake Graph + PDF Report

### Endpoints

#### `/mpasi-milk-graph/{user_phone}`
Generates and serves a PNG chart showing daily MPASI (solid food) and milk intake for the given user.

**Features:**
- Stacked bars showing MPASI (grams) and milk intake (ml)
- Line graphs showing calories for both MPASI and milk
- 7-day period display
- Professional chart formatting with labels and legends

**Usage:**
```
GET /mpasi-milk-graph/+1234567890
```

**Response:** PNG image file

#### `/report-mpasi-milk/{user_phone}`
Generates and serves a PDF report with the chart and a comprehensive summary table.

**Features:**
- Embedded MPASI & milk intake chart
- Detailed summary table with daily breakdown
- Total and average calculations
- Professional PDF formatting with headers and notes

**Usage:**
```
GET /report-mpasi-milk/+1234567890
```

**Response:** PDF report file

### Integration Options

1. **Direct API calls:** Use the endpoints directly in your application
2. **WhatsApp integration:** Link these endpoints in WhatsApp messages for easy access
3. **Web embedding:** Embed charts in web dashboards or reports

### Data Source

Currently uses example data function `get_mpasi_milk_data()`. To use with real data:

1. Replace the function in `mpasi_milk_chart.py` with your database query logic
2. Ensure data format matches the expected structure:
   - MPASI: dates, quantities (grams), calories
   - Milk: dates, quantities (ml), calories

### Example Data Structure
```python
{
    'user_phone': '+1234567890',
    'mpasi': {
        'dates': ['2024-01-01', '2024-01-02', ...],
        'quantities': [120, 150, ...],  # grams
        'calories': [96, 120, ...]      # calories
    },
    'milk': {
        'dates': ['2024-01-01', '2024-01-02', ...], 
        'quantities': [800, 750, ...],  # ml
        'calories': [560, 525, ...]     # calories
    }
}
```

### Dependencies

Added to requirements.txt:
- `matplotlib` - Chart generation
- `reportlab` - PDF report generation