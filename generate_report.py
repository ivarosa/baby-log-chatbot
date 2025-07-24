"""
PDF Report Generation Module

This module generates PDF reports with MPASI & Milk intake charts and summary tables
using reportlab.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import io
from mpasi_milk_chart import get_mpasi_milk_data, generate_mpasi_milk_chart


def generate_mpasi_milk_report(user_phone):
    """
    Generate a PDF report with MPASI and milk intake chart and summary table.
    
    Args:
        user_phone (str): User phone number
        
    Returns:
        bytes: PDF report as bytes
    """
    # Create a BytesIO buffer for the PDF
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    story = []
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20,
        alignment=TA_LEFT,
        textColor=colors.black
    )
    
    # Get data
    data = get_mpasi_milk_data(user_phone)
    
    # Add title
    title = Paragraph(f"MPASI & Milk Intake Report", title_style)
    story.append(title)
    
    # Add user info and period
    user_info = Paragraph(f"<b>User:</b> {user_phone}<br/><b>Period:</b> {data['period']}<br/><b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal'])
    story.append(user_info)
    story.append(Spacer(1, 20))
    
    # Generate and add chart
    try:
        chart_bytes = generate_mpasi_milk_chart(user_phone)
        
        # Create chart image directly from bytes using BytesIO
        chart_io = io.BytesIO(chart_bytes)
        chart_image = Image(chart_io, width=6*inch, height=4*inch)
        story.append(chart_image)
        story.append(Spacer(1, 20))
        
    except Exception as e:
        error_text = Paragraph(f"<b>Error generating chart:</b> {str(e)}", styles['Normal'])
        story.append(error_text)
        story.append(Spacer(1, 20))
    
    # Add summary section
    summary_title = Paragraph("Summary Table", subtitle_style)
    story.append(summary_title)
    
    # Create summary table data
    table_data = [
        ['Date', 'MPASI (g)', 'MPASI Cal', 'Milk (ml)', 'Milk Cal', 'Total Cal']
    ]
    
    mpasi = data['mpasi']
    milk = data['milk']
    
    total_mpasi_g = 0
    total_mpasi_cal = 0
    total_milk_ml = 0
    total_milk_cal = 0
    
    for i in range(len(mpasi['dates'])):
        date = mpasi['dates'][i]
        mpasi_g = mpasi['quantities'][i]
        mpasi_cal = mpasi['calories'][i]
        milk_ml = milk['quantities'][i]
        milk_cal = milk['calories'][i]
        total_cal = mpasi_cal + milk_cal
        
        total_mpasi_g += mpasi_g
        total_mpasi_cal += mpasi_cal
        total_milk_ml += milk_ml
        total_milk_cal += milk_cal
        
        table_data.append([
            date,
            str(mpasi_g),
            str(mpasi_cal),
            str(milk_ml),
            str(milk_cal),
            str(total_cal)
        ])
    
    # Add totals row
    table_data.append([
        'TOTAL',
        str(total_mpasi_g),
        str(total_mpasi_cal),
        str(total_milk_ml),
        str(total_milk_cal),
        str(total_mpasi_cal + total_milk_cal)
    ])
    
    # Add averages row
    num_days = len(mpasi['dates'])
    table_data.append([
        'AVERAGE',
        str(round(total_mpasi_g / num_days, 1)),
        str(round(total_mpasi_cal / num_days, 1)),
        str(round(total_milk_ml / num_days, 1)),
        str(round(total_milk_cal / num_days, 1)),
        str(round((total_mpasi_cal + total_milk_cal) / num_days, 1))
    ])
    
    # Create table
    table = Table(table_data, colWidths=[1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
    
    # Style the table
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -3), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -3), 9),
        ('GRID', (0, 0), (-1, -3), 1, colors.black),
        
        # Total row
        ('BACKGROUND', (0, -2), (-1, -2), colors.lightblue),
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -2), (-1, -2), 9),
        
        # Average row
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Add notes section
    notes_title = Paragraph("Notes", subtitle_style)
    story.append(notes_title)
    
    notes_text = Paragraph("""
    <b>MPASI:</b> Makanan Pendamping ASI (Complementary feeding)<br/>
    <b>Chart:</b> Shows daily quantities as stacked bars and calories as line graphs<br/>
    <b>Data Source:</b> Example data - replace with real database queries<br/>
    <b>Recommendations:</b> Consult with pediatrician for appropriate intake levels
    """, styles['Normal'])
    story.append(notes_text)
    
    # Build PDF
    doc.build(story)
    
    # Get PDF bytes
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes