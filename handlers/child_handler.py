# handlers/child_handler.py - OPTIMIZED VERSION
# Key changes marked with # OPTIMIZED

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
    """Handle child-related operations with robust error handling and session management"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger
        self.cache_manager = cache_manager  #new
    
    def is_premium(self, user: str) -> bool:
        """Check if user has premium access"""
        return can_access_feature(user, "advanced_charts")
    
    def handle_add_child(self, user: str, message: str) -> Response:
        """Handle 'tambah anak' command with robust error handling"""
        resp = MessagingResponse()
        
        try:
            session = self.session_manager.get_session(user)
            
            # Global reset commands
            if message.lower() in ["batal", "cancel", "start", "mulai"]:
                self.session_manager.clear_session(user)
                resp.message("✅ Sesi dibatalkan.")  # OPTIMIZED: Removed redundant text
                return Response(str(resp), media_type="application/xml")
            
            # State machine
            if message.lower() == "tambah anak":
                session["state"] = "ADDCHILD_NAME"
                session["data"] = {}
                reply = "Siapa nama anak Anda?"  # OPTIMIZED: Removed example text
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "ADDCHILD_NAME":
                session["data"]["name"] = message
                session["state"] = "ADDCHILD_GENDER"
                reply = "Jenis kelamin? (laki-laki/perempuan)"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "ADDCHILD_GENDER":
                gender = message.lower()
                if gender in ["laki-laki", "pria", "laki"]:
                    session["data"]["gender"] = "laki-laki"
                    session["state"] = "ADDCHILD_DOB"
                    reply = "Tanggal lahir (YYYY-MM-DD atau 'today')?"  # OPTIMIZED: Shorter
                elif gender in ["perempuan", "wanita"]:
                    session["data"]["gender"] = "perempuan"
                    session["state"] = "ADDCHILD_DOB"
                    reply = "Tanggal lahir (YYYY-MM-DD atau 'today')?"  # OPTIMIZED: Shorter
                else:
                    reply = "❌ Ketik 'laki-laki' atau 'perempuan'"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "ADDCHILD_DOB":
                is_valid, error_msg = InputValidator.validate_date(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["dob"] = message
                    session["state"] = "ADDCHILD_HEIGHT"
                    reply = "Tinggi badan (cm)?"  # OPTIMIZED: Removed example
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "ADDCHILD_HEIGHT":
                is_valid, error_msg = InputValidator.validate_height_cm(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["height_cm"] = float(message)
                    session["state"] = "ADDCHILD_WEIGHT"
                    reply = "Berat badan (kg)?"  # OPTIMIZED: Removed example
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "ADDCHILD_WEIGHT":
                try:
                    weight = float(message.replace(',', '.'))
                    weight_kg = weight / 1000 if weight > 100 else weight
                    
                    is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                    else:
                        session["data"]["weight_kg"] = weight_kg
                        # OPTIMIZED: Combine summary and confirmation into ONE message
                        summary = self._format_child_summary(session["data"])
                        session["state"] = "ADDCHILD_CONFIRM"
                        reply = summary
                except ValueError:
                    reply = "❌ Angka tidak valid"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "ADDCHILD_CONFIRM":
                if message.lower() == "ya":
                    try:
                        save_child(user, session["data"])
                        # OPTIMIZED: Single consolidated message
                        reply = (
                            f"✅ Data {session['data']['name']} tersimpan!\n\n"
                            f"Ketik 'tampilkan anak' untuk lihat data"
                        )
                        session["state"] = None
                        session["data"] = {}
                    except Exception as e:
                        self.session_manager.clear_session(user)
                        logging.error(f"Error saving child: {e}")
                        reply = "❌ Gagal menyimpan. Coba lagi dengan 'tambah anak'"  # OPTIMIZED: Shorter
                elif message.lower() == "ulang":
                    session["state"] = "ADDCHILD_NAME"
                    reply = "Siapa nama anak?"  # OPTIMIZED: Removed redundant text
                elif message.lower() == "batal":
                    session["state"] = None
                    session["data"] = {}
                    reply = "❌ Dibatalkan"  # OPTIMIZED: Much shorter
                else:
                    reply = "Ketik: ya/ulang/batal"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                self.session_manager.clear_session(user)
                reply = "❓ Perintah tidak dikenali. Ketik 'help'"  # OPTIMIZED: Much shorter
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            try:
                self.session_manager.clear_session(user)
            except:
                pass
            
            self.logger.error(f"Critical error in handle_add_child for user {user}: {e}", exc_info=True)
            
            # OPTIMIZED: Shorter error message
            resp.message("❌ Terjadi kesalahan. Ketik 'tambah anak' untuk coba lagi")
            return Response(str(resp), media_type="application/xml")
    
    def handle_show_child(self, user: str) -> Response:
        """Handle 'tampilkan anak' command"""
        resp = MessagingResponse()
        
        try:
            row = self.cache_manager.get_child_data(user, get_child)
            if row:
                # OPTIMIZED: Shorter formatting
                reply = (
                    f"📝 Data Anak:\n"
                    f"• Nama: {row[0]}\n"
                    f"• Jenis kelamin: {row[1]}\n"
                    f"• Lahir: {row[2]}\n"
                    f"• Tinggi: {row[3]} cm\n"
                    f"• Berat: {row[4]} kg"
                )
            else:
                # OPTIMIZED: Shorter
                reply = "Belum ada data. Ketik 'tambah anak'"
        except Exception as e:
            self.logger.error(f"Error getting child data: {e}", exc_info=True)
            reply = "❌ Gagal mengambil data"  # OPTIMIZED: Much shorter
        
        resp.message(reply)
        return Response(str(resp), media_type="application/xml")
    
    def handle_growth_tracking(self, user: str, message: str) -> Response:
        """Handle growth tracking operations"""
        resp = MessagingResponse()
        
        try:
            session = self.session_manager.get_session(user)
            
            if message.lower() in ["batal", "cancel", "start", "mulai"]:
                self.session_manager.clear_session(user)
                resp.message("✅ Sesi dibatalkan")  # OPTIMIZED: Shorter
                return Response(str(resp), media_type="application/xml")
            
            if message.lower() == "tambah anak":
                session["state"] = "ADDCHILD_NAME"
                session["data"] = {}
                reply = "Siapa nama anak?"
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                resp.message(reply)
                return Response(str(resp), media_type="application/xml")
            
            # View commands
            if message.lower().startswith("lihat grafik tumbuh kembang"):
                try:
                    if not self.is_premium(user):
                        # OPTIMIZED: Consolidated premium message
                        reply = (
                            "📈 Grafik Tumbuh Kembang (Premium)\n\n"
                            "Fitur ini tersedia untuk premium user.\n"
                            "💎 Upgrade untuk akses grafik visual!"
                        )
                    else:
                        records = get_timbang_history(user, limit=None)
                        child_info = get_child(user)
                        
                        if not records:
                            reply = "📊 Belum ada data. Ketik 'catat timbang'"  # OPTIMIZED: Shorter
                            resp.message(reply)
                            return Response(str(resp), media_type="application/xml")
                        elif not child_info:
                            reply = "👶 Data anak belum ada. Ketik 'tambah anak'"  # OPTIMIZED: Shorter
                            resp.message(reply)
                            return Response(str(resp), media_type="application/xml")
                        else:
                            from utils.premium_growth_charts import PremiumChartGenerator
                            growth_data, child_data = PremiumChartGenerator.convert_tuple_to_dict(records, child_info)
                            safe_user = user.replace(':', '_').replace('+', '')
                            chart_filename = f"growth_chart_{safe_user}.png"
                            chart_path = os.path.join("static", chart_filename)
                            
                            if PremiumChartGenerator.generate_weight_chart(growth_data, child_data, chart_path):
                                base_url = os.getenv("BASE_URL", "http://localhost:8000")
                                chart_url = f"{base_url}/static/{chart_filename}"
                                
                                # OPTIMIZED: Shorter success message
                                reply = (
                                    f"📈 Grafik {child_data.get('name', 'Anak')}\n\n"
                                    f"✅ Grafik siap!\n"
                                    f"📊 Data: {len(growth_data)} catatan\n\n"
                                    f"🔗 {chart_url}"
                                )
                                
                                try:
                                    resp.message().media(chart_url)
                                    resp.message(reply)
                                    return Response(str(resp), media_type="application/xml")
                                except Exception as e:
                                    logging.warning(f"Media send failed: {e}")
                                    resp.message(reply)
                                    return Response(str(resp), media_type="application/xml")
                            else:
                                reply = "❌ Gagal membuat grafik"  # OPTIMIZED: Shorter
                                resp.message(reply)
                                return Response(str(resp), media_type="application/xml")
                except Exception as e:
                    self.logger.error(f"Error generating chart: {e}", exc_info=True)
                    reply = "❌ Gagal membuat grafik"  # OPTIMIZED: Shorter
                    resp.message(reply)
                    return Response(str(resp), media_type="application/xml")
                            
            elif message.lower().startswith("lihat tumbuh kembang"):
                try:
                    records = get_timbang_history(user)
                    if records:
                        # OPTIMIZED: Shorter header
                        reply = "📊 Riwayat Timbang:\n\n"
                        for r in records[:5]:
                            reply += f"📅 {r[0]}: {r[1]}cm, {r[2]}kg, {r[3]}cm lingkar kepala\n"
                        
                        if len(records) > 5:
                            reply += f"\n...+{len(records) - 5} lagi"
                        
                        # OPTIMIZED: Shorter upsell
                        if self.is_premium(user):
                            reply += f"\n\n💎 Ketik 'lihat grafik tumbuh kembang'"
                        else:
                            reply += f"\n\n✨ Upgrade untuk grafik visual"
                    else:
                        reply = "Belum ada data. Ketik 'catat timbang'"  # OPTIMIZED: Shorter
                except Exception as e:
                    self.logger.error(f"Error getting history: {e}", exc_info=True)
                    reply = "❌ Gagal mengambil data"  # OPTIMIZED: Shorter
            
            elif message.lower() == "catat timbang":
                session["state"] = "TIMBANG_HEIGHT"
                session["data"] = {"date": datetime.now().strftime("%Y-%m-%d")}
                reply = "Tinggi (cm)?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "TIMBANG_HEIGHT":
                is_valid, error_msg = InputValidator.validate_height_cm(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["height_cm"] = float(message)
                    session["state"] = "TIMBANG_WEIGHT"
                    reply = "Berat (kg)?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "TIMBANG_WEIGHT":
                try:
                    weight = float(message.replace(',', '.'))
                    weight_kg = weight / 1000 if weight > 100 else weight
                    
                    is_valid, error_msg = InputValidator.validate_weight_kg(str(weight_kg))
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                    else:
                        session["data"]["weight_kg"] = weight_kg
                        session["state"] = "TIMBANG_HEAD"
                        reply = "Lingkar kepala (cm)?"  # OPTIMIZED: Much shorter
                except ValueError:
                    reply = "❌ Angka tidak valid"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "TIMBANG_HEAD":
                try:
                    session["data"]["head_circum_cm"] = float(message.replace(',', '.'))
                    save_timbang(user, session["data"])
                    
                    # OPTIMIZED: Single consolidated success message
                    reply = (
                        f"✅ Data timbang tersimpan!\n"
                        f"Ketik 'lihat tumbuh kembang' untuk riwayat"
                    )
                    session["state"] = None
                    session["data"] = {}
                except ValueError:
                    reply = "❌ Angka tidak valid"  # OPTIMIZED: Shorter
                except (ValidationError) as e:
                    self.session_manager.clear_session(user)
                    reply = f"❌ {str(e)}"  # OPTIMIZED: Removed redundant text
                except Exception as e:
                    self.session_manager.clear_session(user)
                    self.logger.error(f"Error saving timbang: {e}", exc_info=True)
                    reply = "❌ Gagal menyimpan"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            else:
                self.session_manager.clear_session(user)
                # OPTIMIZED: Much shorter unknown command response
                reply = "❓ Perintah tidak dikenali. Ketik 'help'"
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            try:
                self.session_manager.clear_session(user)
            except:
                pass
            
            self.logger.error(f"Critical error in handle_growth_tracking: {e}", exc_info=True)
            
            # OPTIMIZED: Shorter error message
            resp.message("❌ Terjadi kesalahan. Ketik 'help'")
            return Response(str(resp), media_type="application/xml")
    
    def _format_child_summary(self, data: dict) -> str:
        """Format child data summary for confirmation"""
        # OPTIMIZED: Shorter confirmation format
        return (
            f"✅ Konfirmasi:\n\n"
            f"• {data['name']}\n"
            f"• {data['gender']}\n"
            f"• Lahir: {data['dob']}\n"
            f"• {data['height_cm']}cm, {data['weight_kg']}kg\n\n"
            f"Benar? (ya/ulang/batal)"
        )
