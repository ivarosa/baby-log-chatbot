# baby-log-chatbot

### MPASI & Milk Intake Graph

- **GET /mpasi-milk-graph/{user_phone}**  
  Returns a PNG chart combining daily MPASI (solid food) and milk intake (ml & calories) for the last 7 days for the given user.

- **GET /report-mpasi-milk/{user_phone}**  
  Returns a PDF report including the same chart and a summary table.

**Dependencies:**
- matplotlib
- reportlab

Install with:  
```
pip install matplotlib reportlab
```
