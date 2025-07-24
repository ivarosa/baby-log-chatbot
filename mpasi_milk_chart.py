import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
import io
import os
import psycopg
from psycopg.rows import dict_row

def get_db_connection():
    """Get database connection - supports both SQLite and PostgreSQL"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Railway PostgreSQL connection
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return psycopg.connect(database_url, row_factory=dict_row)
    else:
        # Local SQLite fallback
        import sqlite3
        return sqlite3.connect('babylog.db')

def get_mpasi_milk_data(user_phone, days=7):
    """
    Get aggregated MPASI and milk intake data for the last N days
    Returns data grouped by date with totals and calories
    """
    database_url = os.environ.get('DATABASE_URL')
    user_col = 'user_phone' if database_url else 'user'
    
    # Calculate date range
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days-1)
    
    data = {}
    
    if database_url:
        # PostgreSQL queries
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get MPASI data
        cursor.execute(f"""
            SELECT date, 
                   SUM(volume_ml) as total_volume_ml,
                   SUM(est_calories) as total_calories
            FROM mpasi_log 
            WHERE {user_col} = %s 
              AND date BETWEEN %s AND %s
            GROUP BY date
            ORDER BY date
        """, (user_phone, start_date, end_date))
        
        mpasi_rows = cursor.fetchall()
        
        # Get milk intake data with calorie calculation
        cursor.execute(f"""
            SELECT date,
                   SUM(volume_ml) as total_volume_ml,
                   SUM(CASE 
                       WHEN milk_type = 'sufor' THEN sufor_calorie
                       WHEN milk_type = 'asi' THEN volume_ml * 0.67
                       ELSE volume_ml * 0.67
                   END) as total_calories
            FROM milk_intake_log
            WHERE {user_col} = %s
              AND date BETWEEN %s AND %s
            GROUP BY date
            ORDER BY date
        """, (user_phone, start_date, end_date))
        
        milk_rows = cursor.fetchall()
        conn.close()
        
        # Process PostgreSQL results
        for row in mpasi_rows:
            date_str = row['date'].isoformat() if hasattr(row['date'], 'isoformat') else str(row['date'])
            data[date_str] = data.get(date_str, {})
            data[date_str]['mpasi_ml'] = row['total_volume_ml'] or 0
            data[date_str]['mpasi_calories'] = row['total_calories'] or 0
            
        for row in milk_rows:
            date_str = row['date'].isoformat() if hasattr(row['date'], 'isoformat') else str(row['date'])
            data[date_str] = data.get(date_str, {})
            data[date_str]['milk_ml'] = row['total_volume_ml'] or 0
            data[date_str]['milk_calories'] = row['total_calories'] or 0
    
    else:
        # SQLite queries
        import sqlite3
        conn = sqlite3.connect('babylog.db')
        cursor = conn.cursor()
        
        # Get MPASI data
        cursor.execute(f"""
            SELECT date, 
                   SUM(volume_ml) as total_volume_ml,
                   SUM(est_calories) as total_calories
            FROM mpasi_log 
            WHERE {user_col} = ?
              AND date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (user_phone, start_date.isoformat(), end_date.isoformat()))
        
        mpasi_rows = cursor.fetchall()
        
        # Get milk intake data 
        cursor.execute(f"""
            SELECT date,
                   SUM(volume_ml) as total_volume_ml,
                   SUM(CASE 
                       WHEN milk_type = 'sufor' THEN COALESCE(sufor_calorie, volume_ml * 0.7)
                       WHEN milk_type = 'asi' THEN volume_ml * 0.67
                       ELSE volume_ml * 0.67
                   END) as total_calories
            FROM milk_intake_log
            WHERE {user_col} = ?
              AND date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """, (user_phone, start_date.isoformat(), end_date.isoformat()))
        
        milk_rows = cursor.fetchall()
        conn.close()
        
        # Process SQLite results  
        for row in mpasi_rows:
            date_str = row[0]
            data[date_str] = data.get(date_str, {})
            data[date_str]['mpasi_ml'] = row[1] or 0
            data[date_str]['mpasi_calories'] = row[2] or 0
            
        for row in milk_rows:
            date_str = row[0]
            data[date_str] = data.get(date_str, {})
            data[date_str]['milk_ml'] = row[1] or 0
            data[date_str]['milk_calories'] = row[2] or 0
    
    # Fill in missing dates with zeros
    for i in range(days):
        date_str = (start_date + timedelta(days=i)).isoformat()
        if date_str not in data:
            data[date_str] = {
                'mpasi_ml': 0,
                'mpasi_calories': 0,
                'milk_ml': 0,
                'milk_calories': 0
            }
        else:
            # Ensure all keys exist
            data[date_str].setdefault('mpasi_ml', 0)
            data[date_str].setdefault('mpasi_calories', 0)
            data[date_str].setdefault('milk_ml', 0)
            data[date_str].setdefault('milk_calories', 0)
    
    return data

def generate_mpasi_milk_chart(user_phone, days=7):
    """
    Generate a PNG chart showing MPASI and milk intake with calories
    Returns bytes of the PNG image
    """
    # Set matplotlib backend to Agg for headless operation
    plt.switch_backend('Agg')
    
    # Get data
    data = get_mpasi_milk_data(user_phone, days)
    
    # Sort data by date
    sorted_dates = sorted(data.keys())
    dates = [datetime.strptime(date_str, '%Y-%m-%d').date() for date_str in sorted_dates]
    
    mpasi_ml = [data[date_str]['mpasi_ml'] for date_str in sorted_dates]
    milk_ml = [data[date_str]['milk_ml'] for date_str in sorted_dates]
    mpasi_calories = [data[date_str]['mpasi_calories'] for date_str in sorted_dates]
    milk_calories = [data[date_str]['milk_calories'] for date_str in sorted_dates]
    
    # Create figure and axis
    fig, ax1 = plt.subplots(figsize=(12, 8))
    
    # Set up the bar chart (volume in ml)
    x = np.arange(len(dates))
    width = 0.35
    
    # Create stacked bars for volumes
    bars1 = ax1.bar(x, mpasi_ml, width, label='MPASI (ml)', color='#FF9800', alpha=0.8)
    bars2 = ax1.bar(x, milk_ml, width, bottom=mpasi_ml, label='Milk (ml)', color='#2196F3', alpha=0.8)
    
    # Configure primary y-axis (volume)
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Volume (ml)', fontsize=12, color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.set_ylim(0, max(max(np.array(mpasi_ml) + np.array(milk_ml)), 100) * 1.1)
    
    # Create secondary y-axis for calories
    ax2 = ax1.twinx()
    
    # Add calorie lines
    line1 = ax2.plot(x, mpasi_calories, 'o-', color='#FF5722', linewidth=2, markersize=6, label='MPASI Calories')
    line2 = ax2.plot(x, milk_calories, 's-', color='#0D47A1', linewidth=2, markersize=6, label='Milk Calories')
    
    # Configure secondary y-axis (calories)
    ax2.set_ylabel('Calories (kcal)', fontsize=12, color='black')
    ax2.tick_params(axis='y', labelcolor='black')
    max_calories = max(max(mpasi_calories + milk_calories), 50)
    ax2.set_ylim(0, max_calories * 1.2)
    
    # Format x-axis
    ax1.set_xticks(x)
    ax1.set_xticklabels([date.strftime('%m/%d') for date in dates], rotation=45, ha='right')
    
    # Add value labels on bars
    for i, (mpasi, milk) in enumerate(zip(mpasi_ml, milk_ml)):
        if mpasi > 0:
            ax1.text(i, mpasi/2, f'{mpasi:.0f}', ha='center', va='center', fontweight='bold', fontsize=9)
        if milk > 0:
            ax1.text(i, mpasi + milk/2, f'{milk:.0f}', ha='center', va='center', fontweight='bold', fontsize=9)
    
    # Add calorie value labels
    for i, (mpasi_cal, milk_cal) in enumerate(zip(mpasi_calories, milk_calories)):
        if mpasi_cal > 0:
            ax2.text(i, mpasi_cal + max_calories*0.02, f'{mpasi_cal:.0f}', ha='center', va='bottom', 
                    fontsize=8, color='#FF5722')
        if milk_cal > 0:
            ax2.text(i, milk_cal + max_calories*0.02, f'{milk_cal:.0f}', ha='center', va='bottom', 
                    fontsize=8, color='#0D47A1')
    
    # Combine legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', framealpha=0.9)
    
    # Set title
    plt.title(f'Daily MPASI & Milk Intake - Last {days} Days\nUser: {user_phone}', 
              fontsize=14, fontweight='bold', pad=20)
    
    # Improve layout
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    
    # Save to bytes
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
    img_buffer.seek(0)
    
    # Clean up
    plt.close()
    
    return img_buffer.getvalue()

if __name__ == "__main__":
    # Test the chart generation
    test_user = "+1234567890"
    chart_bytes = generate_mpasi_milk_chart(test_user)
    
    with open("/tmp/test_chart.png", "wb") as f:
        f.write(chart_bytes)
    
    print(f"Test chart generated: {len(chart_bytes)} bytes")