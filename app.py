from flask import Flask, send_file, request, render_template_string
import sqlite3
import os
from mpasi_milk_chart import generate_mpasi_milk_chart
from generate_report import generate_pdf_report
from datetime import datetime, timedelta

app = Flask(__name__)

# Assuming you have a database with the required data
def get_baby_data(phone_number, days=7):
    """Fetch baby feeding data from database for the given phone number"""
    # Replace with your actual database connection and query
    conn = sqlite3.connect('your_database.db')
    cursor = conn.cursor()
    
    # Get data for last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Adjust this query based on your actual database schema
    cursor.execute("""
        SELECT date, mpasi_ml, mpasi_kcal, milk_ml, milk_kcal
        FROM baby_feeds
        WHERE phone_number = ? AND date >= ?
        ORDER BY date
    """, (phone_number, start_date.strftime('%Y-%m-%d')))
    
    result = []
    for row in cursor.fetchall():
        result.append({
            'date': row[0],
            'mpasi_ml': row[1],
            'mpasi_kcal': row[2],
            'milk_ml': row[3],
            'milk_kcal': row[4]
        })
    
    conn.close()
    return result

@app.route('/')
def home():
    return """
    <h1>Baby Log Chart Generator</h1>
    <p>Access charts using URL format: /mpasi-milk-graph/[phone_number]</p>
    <p>For example: <a href="/mpasi-milk-graph/+6285261264323">+6285261264323</a></p>
    """

@app.route('/mpasi-milk-graph/<phone_number>')
def mpasi_milk_graph(phone_number):
    # Decode phone number if needed
    if phone_number.startswith('%2B'):
        phone_number = '+' + phone_number[3:]
    
    # Get data for this phone number
    data = get_baby_data(phone_number)
    
    # If no data found
    if not data:
        return f"No data found for phone number: {phone_number}", 404
    
    # Generate chart
    chart_bytes = generate_mpasi_milk_chart(data, phone_number)
    
    # Option to download PDF report
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Baby Food/Milk Chart</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Baby Food/Milk Intake for {{ phone }}</h1>
            <img src="data:image/png;base64,{{ image_data }}" width="100%" alt="Baby Food/Milk Chart">
            <p>
                <a href="/download-report/{{ phone }}" class="button">Download PDF Report</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    import base64
    chart_bytes.seek(0)
    encoded_img = base64.b64encode(chart_bytes.getvalue()).decode('utf-8')
    
    return render_template_string(html, phone=phone_number, image_data=encoded_img)

@app.route('/download-report/<phone_number>')
def download_report(phone_number):
    # Get data
    data = get_baby_data(phone_number)
    
    # Generate chart
    chart_bytes = generate_mpasi_milk_chart(data, phone_number)
    
    # Generate PDF report
    pdf_bytes = generate_pdf_report(data, chart_bytes, phone_number)
    
    # Send as downloadable file
    return send_file(
        pdf_bytes,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'baby_report_{phone_number}.pdf'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
