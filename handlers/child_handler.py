# handlers/child_handler.py
from datetime import datetime
from fastapi import BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from database.operations import save_child, get_child, save_timbang, get_timbang_history
from validators import InputValidator
from error_handler import ValidationError
from tier_management import can_access_feature
import logging
import os

class ChildHandler:
    """Handle child-related operations"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger  # Use simple logger instead of app_logger
    
    def is_premium(self, user: str) -> bool:
        """Check if user has premium access - wrapper for can_access_feature"""
        return can_access_feature(user, "advanced_charts")
    
    def handle_add_child(self, user: str, message: str) -> Response:
        """Handle 'tambah anak' command"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        # Always check for "tambah anak" command first, regardless of current state
        # This prevents float conversion errors when users type "tambah anak" from any state
        if message.lower() == "tambah anak":
            session["state"] = "ADDCHILD_NAME"
            session["data"] = {}
            reply = "Siapa nama anak Anda?"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "ADDCHILD_NAME":
            session["data"]["name"] = message
            session["state"] = "ADDCHILD_GENDER"
            reply = "Jenis kelamin anak? (laki-laki/perempuan)"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "ADDCHILD_GENDER":
            gender = message.lower()
            if gender in ["laki-laki", "pria", "laki"]:
                session["data"]["gender"] = "laki-laki"
                session["state"] = "ADDCHILD_DOB"
                reply = "Tanggal lahir? (format: YYYY-MM-DD, contoh: 2019-05-21)"
            elif gender in ["perempuan", "wanita"]:
                session["data"]["gender"] = "perempuan"
                session["state"] = "ADDCHILD_DOB"
                reply = "Tanggal lahir? (format: YYYY-MM-DD, contoh: 2019-05-21)"
            else:
                reply = "Masukkan 'laki-laki' atau 'perempuan' untuk jenis kelamin."
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "ADDCHILD_DOB":
            is_valid, error_msg = InputValidator.validate_date(message)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["dob"] = message
                session["state"] = "ADDCHILD_HEIGHT"
                reply = "Tinggi badan anak (cm)? (contoh: 75.5)"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "ADDCHILD_HEIGHT":
            # Validate input before attempting float conversion to prevent ValueError
            is_valid, error_msg = InputValidator.validate_height_cm(message)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["height_cm"] = float(message)
                session["state"] = "ADDCHILD_WEIGHT"
                reply = "Berat badan? (kg, contoh: 8.4 atau 8500 untuk gram)"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "ADDCHILD_WEIGHT":
            # Check if input is numeric before attempting float conversion
            try:
                weight = float(message.replace(',', '.'))  # Allow comma as decimal separator
                weight_kg = weight / 1000 if weight > 100 else weight
                
                is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["weight_kg"] = weight_kg
                    summary = self._format_child_summary(session["data"])
                    session["state"] = "ADDCHILD_CONFIRM"
                    reply = summary
            except ValueError:
                reply = "❌ Masukkan angka untuk berat badan, contoh: 8.4 atau 8500."
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "ADDCHILD_CONFIRM":
            if message.lower() == "ya":
                try:
                    save_child(user, session["data"])
                    reply = "✅ Data anak tersimpan! Untuk melihat data anak, ketik: tampilkan anak"
                except Exception as e:
                    logging.error(f"Error saving child: {e}")
                    reply = "❌ Terjadi kesalahan saat menyimpan data anak."
                finally:
                    # Always clear session state after confirmation, whether save succeeded or failed
                    # This prevents the user from being stuck in confirmation state after errors
                    session["state"] = None
                    session["data"] = {}
            elif message.lower() == "ulang":
                session["state"] = "ADDCHILD_NAME"
                reply = "Siapa nama anak Anda? (Ulangi input)"
            elif message.lower() == "batal":
                session["state"] = None
                session["data"] = {}
                reply = "Input data anak dibatalkan."
            else:
                reply = "Ketik 'ya' jika data sudah benar, 'ulang' untuk mengisi ulang, atau 'batal' untuk membatalkan."
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
        
        else:
            reply = "Perintah tidak dikenali dalam konteks tambah anak."
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_show_child(self, user: str) -> Response:
        """Handle 'tampilkan anak' command"""
        resp = MessagingResponse()
        
        try:
            row = get_child(user)
            if row:
                reply = (
                    f"📝 **Data Anak:**\n"
                    f"• Nama: {row[0]}\n"
                    f"• Jenis kelamin: {row[1].capitalize()}\n"
                    f"• Tanggal lahir: {row[2]}\n"
                    f"• Tinggi: {row[3]} cm\n"
                    f"• Berat: {row[4]} kg"
                )
            else:
                reply = "Data anak belum ada. Silakan ketik 'tambah anak' untuk menambah data anak."
        except Exception as e:
            logging.error(f"Error getting child data: {e}")
            reply = "❌ Terjadi kesalahan saat mengambil data anak."
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_growth_tracking(self, user: str, message: str) -> Response:
        """Handle growth tracking operations"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        # Always check for "tambah anak" command first, regardless of current state
        # This prevents float conversion errors when users type "tambah anak" from any growth tracking state
        if message.lower() == "tambah anak":
            session["state"] = "ADDCHILD_NAME"
            session["data"] = {}
            reply = "Siapa nama anak Anda?"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
        
        # Check for view commands first, regardless of session state
        if message.lower().startswith("lihat grafik tumbuh kembang"):
            # Premium growth chart feature
            try:
                if not self.is_premium(user):
                    reply = ("📈 **Grafik Tumbuh Kembang** adalah fitur premium.\n\n"
                            "✨ Dengan upgrade ke premium, Anda dapat:\n"
                            "• Melihat grafik pertumbuhan visual\n"
                            "• Download chart dalam format PNG\n"
                            "• Analisis tren pertumbuhan\n\n"
                            "💎 Upgrade ke premium untuk akses unlimited!")
                else:
                    # Fetch all growth records for premium users (no limit)
                    records = get_timbang_history(user, limit=None)
                    child_info = get_child(user)
                    
                    if not records:
                        reply = ("📊 Belum ada data pertumbuhan untuk membuat grafik.\n"
                               "Ketik 'catat timbang' untuk menambah data terlebih dahulu.")
                    elif not child_info:
                        reply = ("👶 Data anak belum tersedia.\n"
                               "Ketik 'tambah anak' untuk menambah data anak terlebih dahulu.")
                    else:
                        # Import and use PremiumChartGenerator
                        from utils.premium_growth_charts import PremiumChartGenerator
                        
                        # Convert tuple data to dict format required by chart generator
                        growth_data, child_data = PremiumChartGenerator.convert_tuple_to_dict(records, child_info)
                        
                        # Generate chart filename
                        chart_filename = f"growth_chart_{user}.png"
                        chart_path = os.path.join("static", chart_filename)
                        
                        # Generate the chart
                        if PremiumChartGenerator.generate_weight_chart(growth_data, child_data, chart_path):
                            # Get BASE_URL from environment or use default
                            base_url = os.getenv("BASE_URL", "http://localhost:8000")
                            chart_url = f"{base_url}/static/{chart_filename}"
                            
                            reply = (f"📈 **Grafik Pertumbuhan {child_data.get('name', 'Anak')}**\n\n"
                                   f"✅ Grafik berhasil dibuat!\n"
                                   f"📊 Data: {len(growth_data)} catatan pertumbuhan\n\n"
                                   f"🔗 **Download:** {chart_url}\n\n"
                                   f"💡 Klik link di atas untuk melihat dan download grafik pertumbuhan.")
                            
                            # Try to send chart as WhatsApp media if possible
                            try:
                                resp.message().media(chart_url)
                                return Response(str(resp), media_type="application/xml")
                            except Exception as e:
                                logging.warning(f"Could not send chart as media: {e}")
                                # Fall back to text message with download link
                        else:
                            reply = ("❌ Terjadi kesalahan saat membuat grafik.\n"
                                   "Silakan coba lagi atau hubungi support.")
            except Exception as e:
                logging.error(f"Error generating premium growth chart: {e}")
                reply = "❌ Terjadi kesalahan saat membuat grafik pertumbuhan."
            
        elif message.lower().startswith("lihat tumbuh kembang"):
            try:
                records = get_timbang_history(user)
                if records:
                    reply = "📊 **Riwayat Timbang Terbaru:**\n\n"
                    for r in records[:5]:  # Show last 5 records
                        reply += f"📅 {r[0]}: Tinggi {r[1]} cm, Berat {r[2]} kg, Lingkar kepala {r[3]} cm\n"
                    
                    if len(records) > 5:
                        reply += f"\n... dan {len(records) - 5} catatan lainnya"
                    
                    # Add premium chart suggestion
                    if self.is_premium(user):
                        reply += f"\n\n💎 Ketik 'lihat grafik tumbuh kembang' untuk melihat grafik visual!"
                    else:
                        reply += f"\n\n✨ Upgrade ke premium untuk grafik pertumbuhan visual!"
                else:
                    reply = "Belum ada catatan timbang. Ketik 'catat timbang' untuk menambah data."
            except Exception as e:
                logging.error(f"Error getting growth history: {e}")
                reply = "❌ Terjadi kesalahan saat mengambil riwayat tumbang."
        
        elif message.lower() == "catat timbang":
            session["state"] = "TIMBANG_HEIGHT"
            session["data"] = {"date": datetime.now().strftime("%Y-%m-%d")}
            reply = "Tinggi badan (cm)?"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "TIMBANG_HEIGHT":
            # Validate input before attempting float conversion to prevent ValueError
            is_valid, error_msg = InputValidator.validate_height_cm(message)
            if not is_valid:
                reply = f"❌ {error_msg}"
            else:
                session["data"]["height_cm"] = float(message)
                session["state"] = "TIMBANG_WEIGHT"
                reply = "Berat badan? (kg)"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "TIMBANG_WEIGHT":
            # Check if input is numeric before attempting float conversion
            try:
                weight = float(message.replace(',', '.'))  # Allow comma as decimal separator
                weight_kg = weight / 1000 if weight > 100 else weight
                
                is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["weight_kg"] = weight_kg
                    session["state"] = "TIMBANG_HEAD"
                    reply = "Lingkar kepala (cm)?"
            except ValueError:
                reply = "❌ Masukkan angka yang valid untuk berat badan"
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        elif session["state"] == "TIMBANG_HEAD":
            # Check if input is numeric before attempting float conversion
            try:
                session["data"]["head_circum_cm"] = float(message.replace(',', '.'))  # Allow comma as decimal separator
                save_timbang(user, session["data"])
                reply = "✅ Data timbang tersimpan! Ketik 'lihat tumbuh kembang' untuk melihat riwayat."
            except ValueError:
                reply = "❌ Masukkan angka yang valid untuk lingkar kepala (cm)"
            except (ValidationError) as e:
                reply = f"❌ {str(e)}"
            except Exception as e:
                logging.error(f"Error saving timbang: {e}")
                reply = "❌ Terjadi kesalahan saat menyimpan data timbang."
            finally:
                # Always clear session state after attempting to save growth data
                # This prevents the user from being stuck in data entry state after errors
                session["state"] = None
                session["data"] = {}
            self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
        else:
            reply = "Perintah tidak dikenali dalam konteks tumbuh kembang."
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def _format_child_summary(self, data: dict) -> str:
        """Format child data summary for confirmation"""
        return (
            f"📝 **Konfirmasi Data Anak:**\n\n"
            f"• Nama: {data['name']}\n"
            f"• Jenis kelamin: {data['gender']}\n"
            f"• Tanggal lahir: {data['dob']}\n"
            f"• Tinggi: {data['height_cm']} cm\n"
            f"• Berat: {data['weight_kg']} kg\n\n"
            f"Apakah data sudah benar? (ya/ulang/batal)"
        )
