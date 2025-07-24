import matplotlib
matplotlib.use('Agg')  # For headless server environments
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta

def generate_mpasi_milk_chart(data, user_phone):
    """
    data: List of dicts [{date, mpasi_ml, mpasi_kcal, milk_ml, milk_kcal}]
    Returns: BytesIO object of PNG image
    """
    dates = [d['date'] for d in data]
    mpasi_ml = [d['mpasi_ml'] for d in data]
    mpasi_kcal = [d['mpasi_kcal'] for d in data]
    milk_ml = [d['milk_ml'] for d in data]
    milk_kcal = [d['milk_kcal'] for d in data]

    fig, ax1 = plt.subplots(figsize=(8, 4))
    width = 0.35

    # Plotting bars
    ax1.bar([datetime.strptime(d, '%Y-%m-%d') for d in dates], mpasi_ml, width=width, label='MPASI (ml)', color='#74b9ff')
    ax1.bar([datetime.strptime(d, '%Y-%m-%d') + timedelta(hours=12) for d in dates], milk_ml, width=width, label='Milk (ml)', color='#fdcb6e')

    ax1.set_ylabel('Volume (ml)')
    ax1.set_xlabel('Date')
    ax1.set_xticks([datetime.strptime(d, '%Y-%m-%d') for d in dates])
    ax1.set_xticklabels(dates, rotation=30)
    ax1.legend(loc='upper left')

    # Plotting calories on second axis
    ax2 = ax1.twinx()
    ax2.plot([datetime.strptime(d, '%Y-%m-%d') for d in dates], mpasi_kcal, 'b--', marker='o', label='MPASI (kcal)')
    ax2.plot([datetime.strptime(d, '%Y-%m-%d') for d in dates], milk_kcal, 'r--', marker='o', label='Milk (kcal)')
    ax2.set_ylabel('Calories (kcal)')
    ax2.legend(loc='upper right')

    plt.title(f'MPASI & Milk Intake for {user_phone}')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf