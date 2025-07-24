from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import io

def generate_pdf_report(data, chart_bytes, user_phone):
    """
    data: List of dicts [{date, mpasi_ml, mpasi_kcal, milk_ml, milk_kcal}]
    chart_bytes: BytesIO object (PNG)
    Returns: BytesIO object (PDF)
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"MPASI & Milk Intake Report for {user_phone}")

    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, "Summary Table (Last 7 Days):")

    # Table Data
    table_data = [["Date", "MPASI (ml)", "MPASI (kcal)", "Milk (ml)", "Milk (kcal)"]]
    for d in data:
        table_data.append([d['date'], d['mpasi_ml'], d['mpasi_kcal'], d['milk_ml'], d['milk_kcal']])

    # Draw Table
    x = 50
    y = height - 90
    row_height = 18
    for i, row in enumerate(table_data):
        for j, item in enumerate(row):
            c.drawString(x + j * 90, y - i * row_height, str(item))
    c.line(x, y - row_height, x + 90 * 5, y - row_height)  # underline header

    # Insert Chart
    chart_y = y - len(table_data) * row_height - 20
    c.drawString(50, chart_y, "See chart below:")
    chart_y -= 10
    c.drawImage(chart_bytes, 50, chart_y - 200, width=400, height=200)  # Adjust as needed

    c.showPage()
    c.save()
    buf.seek(0)
    return buf