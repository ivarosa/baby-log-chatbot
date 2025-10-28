# handlers/feeding_handler.py - OPTIMIZED VERSION
# Only showing the most critical optimizations

class FeedingHandler:
    """Handle all feeding-related operations - OPTIMIZED"""
    
    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger
        
        class MockAppLogger:
            def log_user_action(self, **kwargs):
                logger.info(f"User action: {kwargs}")
            def log_error(self, error, **kwargs):
                logger.error(f"Error: {error}, {kwargs}")
                return f"ERROR_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.app_logger = MockAppLogger()
    
    def handle_mpasi_logging(self, user: str, message: str) -> Response:
        """Handle MPASI logging flow - OPTIMIZED"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() == "catat mpasi":
                session["state"] = "MPASI_DATE"
                session["data"] = {}
                reply = "Tanggal (YYYY-MM-DD atau 'today')?"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_DATE":
                if message.lower().strip() == "today":
                    session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                    session["state"] = "MPASI_TIME"
                    reply = "Jam (HH:MM)?"  # OPTIMIZED: Much shorter
                else:
                    is_valid, error_msg = InputValidator.validate_date(message)
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                    else:
                        session["data"]["date"] = message
                        session["state"] = "MPASI_TIME"
                        reply = "Jam (HH:MM)?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_TIME":
                time_input = message.replace('.', ':')
                is_valid, error_msg = InputValidator.validate_time(time_input)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["time"] = time_input
                    session["state"] = "MPASI_VOL"
                    reply = "Volume (ml)?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_VOL":
                is_valid, error_msg = InputValidator.validate_volume_ml(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["volume_ml"] = float(message)
                    session["state"] = "MPASI_DETAIL"
                    reply = "Makanan apa?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_DETAIL":
                session["data"]["food_detail"] = InputValidator.sanitize_text_input(message, 200)
                session["state"] = "MPASI_GRAMS"
                reply = "Menu & porsi untuk kalori (atau 'skip')?"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MPASI_GRAMS":
                if message.lower() != "skip":
                    session["data"]["food_grams"] = message
                    session["data"]["est_calories"] = None
                else:
                    session["data"]["food_grams"] = ""
                    session["data"]["est_calories"] = None
                
                try:
                    save_mpasi(user, session["data"])
                    
                    self.logger.info(f"User action: user_id={user}, action='mpasi_logged', success=True")
                    
                    # OPTIMIZED: Single consolidated success message
                    reply = (
                        f"✅ MPASI tersimpan!\n"
                        f"• {session['data']['time']}: {session['data']['volume_ml']}ml\n"
                        f"• {session['data']['food_detail'][:40]}...\n\n"
                        f"Ketik 'lihat ringkasan mpasi'"
                    )
                    
                    session["state"] = None
                    session["data"] = {}
                    
                except (ValueError, ValidationError) as e:
                    reply = f"❌ {str(e)}"
                    self.logger.info(f"User action: user_id={user}, action='mpasi_logged', success=False")
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'save_mpasi'})
                    reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
                
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "❓ Perintah tidak dikenali"  # OPTIMIZED: Much shorter
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user, context={'function': 'handle_mpasi_logging'})
            resp.message(f"❌ Error: {error_id}")  # OPTIMIZED: Shorter
            return Response(str(resp), media_type="application/xml")
    
    def handle_milk_logging(self, user: str, message: str) -> Response:
        """Handle milk intake logging flow - OPTIMIZED"""
        session = self.session_manager.get_session(user)
        resp = MessagingResponse()
        
        try:
            if message.lower() == "catat susu":
                session["state"] = "MILK_DATE"
                session["data"] = {}
                reply = "Tanggal (YYYY-MM-DD atau 'today')?"  # OPTIMIZED: Shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_DATE":
                if message.lower().strip() == "today":
                    session["data"]["date"] = datetime.now().strftime("%Y-%m-%d")
                else:
                    is_valid, error_msg = InputValidator.validate_date(message)
                    if not is_valid:
                        reply = f"❌ {error_msg}"
                        resp.message(reply)
                        return Response(str(resp), media_type="application/xml")
                    session["data"]["date"] = message
                
                session["state"] = "MILK_TIME"
                reply = "Jam (HH:MM)?"  # OPTIMIZED: Much shorter
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_TIME":
                time_input = message.replace('.', ':')
                is_valid, error_msg = InputValidator.validate_time(time_input)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["time"] = time_input
                    session["state"] = "MILK_VOL"
                    reply = "Volume (ml)?"  # OPTIMIZED: Much shorter
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_VOL":
                is_valid, error_msg = InputValidator.validate_volume_ml(message)
                if not is_valid:
                    reply = f"❌ {error_msg}"
                else:
                    session["data"]["volume_ml"] = float(message)
                    session["state"] = "MILK_TYPE"
                    reply = "Jenis: asi/sufor?"  # OPTIMIZED: Much shorter
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                
            elif session["state"] == "MILK_TYPE":
                milk_type = message.lower()
                if milk_type == "asi":
                    session["data"]["milk_type"] = "asi"
                    session["state"] = "ASI_METHOD"
                    reply = "Metode: dbf/pumping?"  # OPTIMIZED: Much shorter
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                elif milk_type == "sufor":
                    session["data"]["milk_type"] = "sufor"
                    try:
                        user_kcal = get_user_calorie_setting(user)
                        session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                        session["state"] = "MILK_NOTE"
                        # OPTIMIZED: Shorter confirmation
                        reply = f"✅ Kalori: {session['data']['sufor_calorie']:.1f} kkal\n\nCatatan? ('skip' jika tidak)"
                        self.session_manager.update_session(user, state=session["state"], data=session["data"])
                    except Exception as e:
                        error_id = self.app_logger.log_error(e, user_id=user)
                        reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
                else:
                    reply = "❌ Ketik: asi/sufor"  # OPTIMIZED: Much shorter
                
            elif session["state"] == "ASI_METHOD":
                method = message.lower()
                if method in ["dbf", "pumping"]:
                    session["data"]["asi_method"] = method
                    session["state"] = "MILK_NOTE"
                    reply = "Catatan? ('skip' jika tidak)"  # OPTIMIZED: Shorter
                    self.session_manager.update_session(user, state=session["state"], data=session["data"])
                else:
                    reply = "❌ Ketik: dbf/pumping"  # OPTIMIZED: Much shorter
                
            elif session["state"] == "MILK_NOTE":
                # Check if summary request
                if message.lower().startswith("lihat ringkasan"):
                    return self.handle_summary_requests(user, message)
                
                note_text = "" if message.lower() == "skip" else InputValidator.sanitize_text_input(message, 200)
                session["data"]["note"] = note_text
                
                # Ensure sufor_calorie is set
                if session["data"].get("milk_type") == "sufor" and "sufor_calorie" not in session["data"]:
                    user_kcal = get_user_calorie_setting(user)
                    session["data"]["sufor_calorie"] = session["data"]["volume_ml"] * user_kcal["sufor"]
                
                try:
                    save_milk_intake(user, session["data"])
                    
                    self.logger.info(f"User action: user_id={user}, action='milk_logged', success=True")
                    
                    # OPTIMIZED: Single consolidated success message
                    milk_type = session["data"].get("milk_type", "unknown")
                    extra = ""
                    if milk_type == "sufor":
                        extra = f" ({session['data'].get('sufor_calorie', 0):.1f} kkal)"
                    elif milk_type == "asi":
                        extra = f" ({session['data'].get('asi_method','')})"
                    
                    reply = (
                        f"✅ Susu tersimpan!\n"
                        f"• {session['data']['time']}: {session['data']['volume_ml']}ml {milk_type.upper()}{extra}\n\n"
                        f"Ketik 'lihat ringkasan susu'"
                    )
                    session["state"] = None
                    session["data"] = {}
                    
                except (ValueError, ValidationError) as e:
                    reply = f"❌ {str(e)}"
                    self.logger.info(f"User action: user_id={user}, action='milk_logged', success=False")
                except Exception as e:
                    error_id = self.app_logger.log_error(e, user_id=user)
                    reply = f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
                
                self.session_manager.update_session(user, state=session["state"], data=session["data"])
            
            else:
                reply = "❓ Perintah tidak dikenali"  # OPTIMIZED: Much shorter
            
            resp.message(reply)
            return Response(str(resp), media_type="application/xml")
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            resp.message(f"❌ Error: {error_id}")  # OPTIMIZED: Shorter
            return Response(str(resp), media_type="application/xml")
    
    def _generate_milk_summary(self, user: str, date: str) -> str:
        """Generate milk summary - OPTIMIZED"""
        try:
            rows = get_milk_intake_summary(user, date, date)
            if not rows:
                return f"Belum ada catatan susu/ASI.\n\nKetik 'catat susu'"  # OPTIMIZED: Shorter

            total_count = 0
            total_ml = 0
            total_cal = 0

            for r in rows:
                if isinstance(r, (list, tuple)):
                    total_count += r[2] if len(r) > 2 and r[2] else 0
                    total_ml += r[3] if len(r) > 3 and r[3] else 0
                    total_cal += r[4] if len(r) > 4 and r[4] else 0
                elif isinstance(r, dict):
                    total_count += r.get("count", 0)
                    total_ml += r.get("volume_ml", 0)
                    total_cal += r.get("calories", 0)

            # OPTIMIZED: Much shorter summary format
            reply = (
                f"🍼 Ringkasan Susu ({date})\n\n"
                f"• {total_count} sesi\n"
                f"• {total_ml} ml\n"
                f"• {total_cal:.0f} kkal\n\n"
            )

            # OPTIMIZED: Condensed detail section
            for r in rows:
                if isinstance(r, (list, tuple)):
                    milk_type = r[0] if len(r) > 0 else "-"
                    count = r[2] if len(r) > 2 else 0
                    volume = r[3] if len(r) > 3 else 0
                elif isinstance(r, dict):
                    milk_type = r.get("milk_type", "-")
                    count = r.get("count", 0)
                    volume = r.get("volume_ml", 0)

                reply += f"• {milk_type.upper()}: {count}x, {volume}ml\n"

            return reply
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            return f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
    
    def _generate_mpasi_summary(self, user: str, date: str) -> str:
        """Generate MPASI summary - OPTIMIZED"""
        try:
            rows = get_mpasi_summary(user, date, date)
            if not rows:
                return f"Belum ada catatan MPASI.\n\nKetik 'catat mpasi'"  # OPTIMIZED: Shorter
            
            total_ml = sum([row[2] or 0 for row in rows])
            total_cal = sum([row[5] or 0 for row in rows])
            
            # OPTIMIZED: Much shorter format
            reply = (
                f"🍽️ Ringkasan MPASI ({date})\n\n"
                f"• {len(rows)} sesi\n"
                f"• {total_ml} ml\n"
                f"• {total_cal} kkal\n\n"
            )
            
            # OPTIMIZED: Show only top 3 entries
            for i, row in enumerate(rows[:3], 1):
                time_val = row[1] if len(row) > 1 else '-'
                volume = row[2] if len(row) > 2 else 0
                food = row[3] if len(row) > 3 else ''
                
                reply += f"{i}. {time_val}: {volume}ml\n"
            
            if len(rows) > 3:
                reply += f"\n...+{len(rows) - 3} sesi lagi"
            
            return reply
            
        except Exception as e:
            error_id = self.app_logger.log_error(e, user_id=user)
            return f"❌ Error: {error_id}"  # OPTIMIZED: Shorter
