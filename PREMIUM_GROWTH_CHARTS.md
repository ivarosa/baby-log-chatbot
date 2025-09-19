# Premium Growth Charts Feature

## Overview
This feature adds premium growth chart generation capability to the baby tracking chatbot.

## Implementation Details

### New Files Created
- `utils/premium_growth_charts.py` - Core chart generation module
- `static/.gitkeep` - Placeholder for static files directory

### Modified Files
- `handlers/child_handler.py` - Added premium chart command handling
- `main.py` - Added static file serving capability

### How it Works

1. **Command Trigger**: Users can type "lihat grafik tumbuh kembang" to request a growth chart
2. **Premium Check**: System checks if user has premium access using `can_access_feature(user, "advanced_charts")`
3. **Data Fetching**: For premium users, fetches all growth records using `get_timbang_history(user, limit=None)` and child info using `get_child(user)`
4. **Data Conversion**: Converts database tuple format to dict format required by chart generator
5. **Chart Generation**: Uses `PremiumChartGenerator.generate_weight_chart()` to create PNG chart
6. **File Serving**: Saves chart to `static/growth_chart_{user}.png` and serves via FastAPI static mount
7. **Response**: Sends download link and attempts to send as WhatsApp media

### Premium vs Free User Experience
- **Premium Users**: Get visual charts with download links and WhatsApp media
- **Free Users**: Get informative message about premium upgrade benefits

### Environment Variables
- `BASE_URL`: Base URL for serving static files (defaults to http://localhost:8000)

### Dependencies
- matplotlib: For chart generation
- FastAPI: For static file serving
- Twilio: For WhatsApp media sending

### Error Handling
- Gracefully handles missing chart modules
- Validates data availability before chart generation
- Provides informative error messages for users