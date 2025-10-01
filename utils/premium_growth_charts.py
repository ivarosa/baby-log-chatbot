# utils/premium_growth_charts.py
"""
Premium Growth Chart Generator
Generates weight and growth charts for premium users
"""
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    import matplotlib
    # Use Agg backend for server environments
    matplotlib.use('Agg')
    CHART_MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Chart modules not available: {e}")
    CHART_MODULES_AVAILABLE = False

class PremiumChartGenerator:
    """Generate premium growth charts for baby tracking"""
    
    @staticmethod
    def generate_weight_chart(growth_data: List[Dict[str, Any]], child_info: Dict[str, Any], 
                            output_path: str) -> bool:
        """
        Generate weight chart for premium users
        
        Args:
            growth_data: List of dicts with keys: date, height_cm, weight_kg, head_circum_cm
            child_info: Dict with keys: name, gender, dob, height_cm, weight_kg
            output_path: Full path where to save the PNG chart
            
        Returns:
            bool: True if chart generated successfully, False otherwise
        """
        if not CHART_MODULES_AVAILABLE:
            logging.error("Chart generation modules not available")
            return False
            
        if not growth_data:
            logging.error("No growth data provided for chart generation")
            return False
            
        try:
            # Create figure and axis
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            fig.suptitle(f'Grafik Pertumbuhan - {child_info.get("name", "Anak")}', 
                        fontsize=16, fontweight='bold')
            
            # Prepare data
            dates = []
            weights = []
            heights = []
            
            for record in growth_data:
                try:
                    # Handle date parsing
                    date_str = record['date']
                    if isinstance(date_str, str):
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    else:
                        date_obj = date_str
                    dates.append(date_obj)
                    weights.append(float(record['weight_kg']))
                    heights.append(float(record['height_cm']))
                except (ValueError, KeyError) as e:
                    logging.warning(f"Skipping invalid record: {record}, error: {e}")
                    continue
            
            if not dates:
                logging.error("No valid data points found for chart")
                return False
            
            # Sort by date
            sorted_data = sorted(zip(dates, weights, heights))
            dates, weights, heights = zip(*sorted_data)
            
            # Plot weight chart
            ax1.plot(dates, weights, marker='o', linewidth=2, markersize=6, 
                    color='#2E86AB', label='Berat Badan')
            ax1.set_title('Perkembangan Berat Badan', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Berat (kg)', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Format x-axis for weight chart
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
            
            # Plot height chart
            ax2.plot(dates, heights, marker='s', linewidth=2, markersize=6, 
                    color='#A23B72', label='Tinggi Badan')
            ax2.set_title('Perkembangan Tinggi Badan', fontsize=14, fontweight='bold')
            ax2.set_ylabel('Tinggi (cm)', fontsize=12)
            ax2.set_xlabel('Tanggal', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # Format x-axis for height chart
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
            # Add child info text
            child_text = f"Nama: {child_info.get('name', 'N/A')} | "
            child_text += f"Jenis Kelamin: {child_info.get('gender', 'N/A').title()} | "
            child_text += f"Tanggal Lahir: {child_info.get('dob', 'N/A')}"
            
            fig.text(0.5, 0.02, child_text, ha='center', fontsize=10, 
                    style='italic', color='#666666')
            
            # Adjust layout
            plt.tight_layout()
            plt.subplots_adjust(top=0.92, bottom=0.1)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save chart
            plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
            logging.info(f"Chart saved successfully to {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating chart: {e}")
            return False
    
    @staticmethod
    def convert_tuple_to_dict(growth_records: List[tuple], child_record: tuple) -> tuple:
        """
        Convert database tuple results to dict format required by generate_weight_chart
        
        Args:
            growth_records: List of tuples (date, height_cm, weight_kg, head_circum_cm)
            child_record: Tuple (name, gender, dob, height_cm, weight_kg)
            
        Returns:
            Tuple of (growth_data_list, child_info_dict)
        """
        # Convert growth records
        growth_data = []
        for record in growth_records:
            if len(record) >= 4:
                growth_data.append({
                    'date': record[0],
                    'height_cm': record[1],
                    'weight_kg': record[2],
                    'head_circum_cm': record[3]
                })
        
        # Convert child record
        child_info = {}
        if child_record and len(child_record) >= 5:
            child_info = {
                'name': child_record[0],
                'gender': child_record[1],
                'dob': child_record[2],
                'height_cm': child_record[3],
                'weight_kg': child_record[4]
            }
        
        return growth_data, child_info