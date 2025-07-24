"""
MPASI & Milk Intake Chart Generation Module

This module generates PNG charts showing daily MPASI (solid food) and milk intake
with stacked bars for quantities and lines for calories using matplotlib.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import io
import base64
import numpy as np


def get_mpasi_milk_data(user_phone):
    """
    Example data function to be replaced with real DB queries.
    
    Args:
        user_phone (str): User phone number
        
    Returns:
        dict: Dictionary containing MPASI and milk data for the last 7 days
    """
    # Generate example data for the last 7 days
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    
    # Example MPASI data (in grams and calories)
    mpasi_data = {
        'dates': dates,
        'quantities': [120, 150, 100, 180, 160, 140, 170],  # grams
        'calories': [96, 120, 80, 144, 128, 112, 136]       # calories (0.8 cal/g average)
    }
    
    # Example milk data (in ml and calories)
    milk_data = {
        'dates': dates,
        'quantities': [800, 750, 900, 700, 850, 780, 820],  # ml
        'calories': [560, 525, 630, 490, 595, 546, 574]     # calories (0.7 cal/ml average)
    }
    
    return {
        'user_phone': user_phone,
        'mpasi': mpasi_data,
        'milk': milk_data,
        'period': f"{dates[0]} to {dates[-1]}"
    }


def generate_mpasi_milk_chart(user_phone):
    """
    Generate a matplotlib chart for MPASI and milk intake.
    
    Args:
        user_phone (str): User phone number
        
    Returns:
        bytes: PNG chart image as bytes
    """
    # Get data
    data = get_mpasi_milk_data(user_phone)
    mpasi = data['mpasi']
    milk = data['milk']
    
    # Convert date strings to datetime objects
    dates = [datetime.strptime(date, '%Y-%m-%d') for date in mpasi['dates']]
    
    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(12, 8))
    
    # Set up the primary axis for quantities (bars)
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Quantity (g for MPASI, ml for Milk)', fontsize=12, color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    
    # Create stacked bar chart for quantities
    width = 0.8
    mpasi_bars = ax1.bar(dates, mpasi['quantities'], width, label='MPASI (g)', 
                        color='#FF9999', alpha=0.8)
    milk_bars = ax1.bar(dates, milk['quantities'], width, 
                       bottom=mpasi['quantities'], label='Milk (ml)', 
                       color='#66B2FF', alpha=0.8)
    
    # Create secondary axis for calories (lines)
    ax2 = ax1.twinx()
    ax2.set_ylabel('Calories', fontsize=12, color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    
    # Plot calorie lines
    mpasi_line = ax2.plot(dates, mpasi['calories'], color='red', marker='o', 
                         linewidth=2, markersize=6, label='MPASI Calories')
    milk_line = ax2.plot(dates, milk['calories'], color='darkblue', marker='s', 
                        linewidth=2, markersize=6, label='Milk Calories')
    
    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Add title
    plt.title(f'MPASI & Milk Intake Chart\nUser: {user_phone}\nPeriod: {data["period"]}', 
              fontsize=14, fontweight='bold', pad=20)
    
    # Add legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', bbox_to_anchor=(0, 1))
    
    # Add grid
    ax1.grid(True, alpha=0.3)
    
    # Add value labels on bars
    for i, (mpasi_qty, milk_qty) in enumerate(zip(mpasi['quantities'], milk['quantities'])):
        # MPASI label
        ax1.text(dates[i], mpasi_qty/2, str(mpasi_qty), ha='center', va='center', 
                fontweight='bold', fontsize=9)
        # Milk label
        ax1.text(dates[i], mpasi_qty + milk_qty/2, str(milk_qty), ha='center', va='center', 
                fontweight='bold', fontsize=9)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save to bytes
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
    img_buffer.seek(0)
    
    # Get bytes
    chart_bytes = img_buffer.getvalue()
    
    # Clean up
    plt.close(fig)
    img_buffer.close()
    
    return chart_bytes