# constants.py
"""
Application constants and messages
Centralized location for all static messages and configuration
"""

WELCOME_MESSAGE = (
    "🍼 **Selamat datang di Babylog!** 👋\n\n"
    "Saya siap membantu Anda mengelola catatan dan perkembangan si kecil.\n\n"
    "🚀 **Untuk memulai, coba perintah ini:**\n"
    "• `tambah anak` - Daftarkan data si kecil\n"
    "• `catat timbang` - Log berat & tinggi badan\n"
    "• `catat mpasi` - Log makanan bayi\n"
    "• `catat susu` - Log ASI/susu formula\n"
    "• `catat tidur` - Track jam tidur\n"
    "• `ringkasan hari ini` - Lihat aktivitas harian\n\n"
    "❓ **Butuh bantuan?**\n"
    "• Ketik `bantuan` untuk panduan singkat\n"
    "• Ketik `panduan` untuk daftar lengkap perintah\n\n"
    "💡 **Tips:** Gunakan perintah bahasa Indonesia atau English"
)

HELP_MESSAGE = (
    "🤖 **Bantuan Babylog**\n\n"
    "Pilih kategori bantuan yang Anda butuhkan:\n\n"
    "👶 **Data Anak & Tumbuh Kembang:**\n"
    "• `tambah anak` / `tampilkan anak`\n"
    "• `catat timbang` / `lihat tumbuh kembang`\n\n"
    "🍽️ **Asupan Nutrisi:**\n"
    "• `catat mpasi` / `lihat ringkasan mpasi`\n"
    "• `catat susu` / `lihat ringkasan susu`\n"
    "• `catat pumping` / `lihat ringkasan pumping`\n\n"
    "💤 **Tidur & Kesehatan:**\n"
    "• `catat tidur` / `lihat tidur` / `riwayat tidur`\n"
    "• `catat bab` / `lihat riwayat bab`\n\n"
    "🔥 **Kalori & Nutrisi:**\n"
    "• `hitung kalori susu` - Kalkulator kalori\n"
    "• `set kalori asi` / `set kalori sufor`\n"
    "• `lihat kalori` / `ringkasan nutrisi`\n\n"
    "⏰ **Pengingat Susu:**\n"
    "• `set reminder susu` / `show reminders`\n"
    "• **Respons cepat saat pengingat:**\n"
    "  • `done [volume]` - Selesai & catat\n"
    "  • `snooze [menit]` - Tunda pengingat\n"
    "  • `skip reminder` - Lewati pengingat\n\n"
    "📊 **Laporan & Ringkasan:**\n"
    "• `ringkasan hari ini` - Summary lengkap\n"
    "• `ringkasan nutrisi` - Focus kalori\n"
    "• `ringkasan minggu` - Analisis 7 hari (premium)\n\n"
    "🔧 **Perintah Umum:**\n"
    "• `batal` / `cancel` - Batalkan sesi\n"
    "• `status` - Lihat status tier\n"
    "• `panduan` - Daftar lengkap perintah\n\n"
    "💎 Upgrade ke **Premium** untuk fitur unlimited!"
)

PANDUAN_MESSAGE = (
    "📖 **Panduan Lengkap Babylog**\n\n"
    "Berikut adalah semua perintah yang bisa Anda gunakan:\n\n"
    "## **I. Data Anak & Tumbuh Kembang**\n"
    "• `tambah anak` - Tambah data si kecil baru\n"
    "• `tampilkan anak` - Lihat data anak tersimpan\n"
    "• `catat timbang` - Catat berat, tinggi, lingkar kepala\n"
    "• `lihat tumbuh kembang` - Riwayat pertumbuhan\n\n"
    "## **II. Asupan Nutrisi & Makan**\n"
    "• `catat mpasi` - Catat detail MPASI & makanan\n"
    "• `lihat ringkasan mpasi` - Ringkasan makanan\n"
    "• `catat susu` - Catat ASI/susu formula\n"
    "• `lihat ringkasan susu [tanggal]` - Rekap harian\n"
    "• `catat pumping` - Catat ASI perah\n"
    "• `lihat ringkasan pumping` - Total & riwayat ASI\n\n"
    "## **III. Kalori & Perhitungan Gizi**\n"
    "• `hitung kalori susu` - Kalkulator kalori susu\n"
    "• `set kalori asi [nilai]` - Atur kalori per ml ASI\n"
    "• `set kalori sufor [nilai]` - Atur kalori susu formula\n"
    "• `lihat kalori` - Total kalori harian\n"
    "• `ringkasan nutrisi` - Analisis gizi lengkap\n\n"
    "## **IV. Tidur & Aktivitas**\n"
    "• `catat tidur` - Mulai mencatat sesi tidur\n"
    "• `selesai tidur [HH:MM]` - Akhiri sesi (cth: selesai tidur 07:30)\n"
    "• `batal tidur` - Batalkan sesi belum selesai\n"
    "• `lihat tidur` - Catatan tidur hari ini\n"
    "• `riwayat tidur` - Riwayat beberapa hari\n\n"
    "## **V. Kesehatan & BAB**\n"
    "• `catat bab` - Catat riwayat BAB (Bristol Scale)\n"
    "• `lihat riwayat bab` - Riwayat kesehatan pencernaan\n\n"
    "## **VI. Pengingat Otomatis**\n"
    "• `set reminder susu` - Setup pengingat pemberian susu\n"
    "• `show reminders` - Daftar pengingat aktif\n"
    "• **Respons saat pengingat muncul:**\n"
    "  • `done [volume]` - Catat volume (cth: done 120)\n"
    "  • `snooze [menit]` - Tunda (cth: snooze 15)\n"
    "  • `skip reminder` - Lewati sekali\n"
    "• `henti reminder [nama]` - Nonaktifkan\n"
    "• `delete reminder [nama]` - Hapus permanent\n\n"
    "## **VII. Laporan & Analisis**\n"
    "• `ringkasan hari ini` - Summary aktivitas lengkap\n"
    "• `ringkasan [YYYY-MM-DD]` - Summary tanggal tertentu\n"
    "• `ringkasan nutrisi` - Fokus kalori & gizi\n"
    "• `ringkasan pertumbuhan` - Fokus tumbuh kembang\n"
    "• `ringkasan minggu` - Analisis 7 hari (premium)\n"
    "• `ringkasan bulan` - Laporan bulanan (premium)\n\n"
    "## **VIII. Manajemen & Pengaturan**\n"
    "• `status` / `tier` - Lihat status langganan\n"
    "• `batal` / `cancel` - Batalkan operasi berjalan\n"
    "• `help` / `bantuan` - Bantuan singkat\n"
    "• `panduan` / `guide` - Panduan lengkap ini\n\n"
    "## **💡 Tips Penggunaan:**\n"
    "📱 **Format waktu:** Gunakan 24 jam (HH:MM)\n"
    "📅 **Tanggal hari ini:** Bisa ketik 'today'\n"
    "🔢 **Volume:** Angka saja tanpa 'ml' (contoh: 120)\n"
    "❌ **Batalkan:** Ketik 'batal' kapan saja\n"
    "⏰ **Pengingat:** Respons cepat tanpa awalan\n\n"
    "## **💎 Fitur Premium:**\n"
    "• 🔄 Riwayat unlimited (vs 7 hari)\n"
    "• 📊 Analisis mingguan & bulanan\n"
    "• 📈 Grafik pertumbuhan percentile\n"
    "• 🔔 Pengingat unlimited (vs 3)\n"
    "• 📄 Export PDF laporan\n"
    "• 👨‍⚕️ Rekomendasi dokter anak\n\n"
    "🆓 **User gratis** tetap dapat akses semua fitur dasar!\n\n"
    "❓ Masih bingung? Ketik `bantuan` untuk panduan singkat."
)

# Error messages
ERROR_MESSAGES = {
    'database': "Maaf, terjadi kesalahan database. Silakan coba lagi.",
    'validation': "Data yang Anda masukkan tidak valid. {}",
    'api': "Layanan sedang tidak tersedia. Silakan coba lagi nanti.",
    'session': "Sesi Anda telah berakhir. Silakan mulai lagi.",
    'generic': "Maaf, terjadi kesalahan. Silakan coba lagi.",
    'timeout': "Waktu habis. Silakan coba lagi.",
    'permission': "Anda tidak memiliki akses untuk fitur ini.",
    'limit': "Anda telah mencapai batas penggunaan. Upgrade ke premium untuk melanjutkan."
}

# Success messages
SUCCESS_MESSAGES = {
    'data_saved': "✅ Data berhasil disimpan!",
    'reminder_created': "✅ Pengingat berhasil dibuat!",
    'session_cancelled': "✅ Sesi dibatalkan.",
    'sleep_started': "✅ Mulai mencatat tidur.",
    'sleep_completed': "✅ Catatan tidur tersimpan!",
}

# Bristol Stool Scale descriptions
BRISTOL_SCALE = {
    1: "Sangat keras (seperti kacang-kacang, susah dikeluarkan)",
    2: "Berbentuk sosis, bergelombang/bergerigi", 
    3: "Sosis dengan retakan di permukaan",
    4: "Lembut, berbentuk sosis/pisang, permukaan halus",
    5: "Potongan-potongan lunak, tepi jelas",
    6: "Potongan lembek, tepi bergerigi",
    7: "Cair, tanpa bentuk padat"
}

BRISTOL_STATUS = {
    1: "😰 Sangat keras (konstipasi)", 
    2: "😟 Keras (konstipasi ringan)", 
    3: "😐 Normal-keras",
    4: "😊 Normal (ideal)", 
    5: "😐 Normal-lembut", 
    6: "😟 Lembek (diare ringan)", 
    7: "😰 Cair (diare)"
}

# Sleep quality assessments
SLEEP_QUALITY = {
    'very_short': "💤 **Tidur sangat singkat** - Mungkin hanya power nap",
    'short': "😴 **Tidur singkat** - Good untuk nap time", 
    'medium': "😊 **Tidur sedang** - Durasi nap yang baik",
    'good': "😴 **Tidur cukup lama** - Excellent untuk recovery",
    'night': "🌙 **Tidur malam yang baik** - Durasi ideal",
    'long': "😴 **Tidur panjang** - Sangat baik untuk pertumbuhan",
    'very_long': "🛌 **Tidur sangat panjang** - Pastikan bayi dalam kondisi sehat"
}

# Tier information
TIER_INFO = {
    'free': {
        'name': 'Free',
        'emoji': '🆓',
        'history_days': 7,
        'growth_entries': 10,
        'active_reminders': 3,
        'children_count': 1,
        'mpasi_entries': 10,
        'pumping_entries': 10,
        'sleep_record': 10,
        'features': [
            'Tracking dasar semua aktivitas',
            'Riwayat 7 hari terakhir',
            'Maksimal 3 pengingat aktif',
            'Ringkasan harian',
            'Kalkulator kalori basic'
        ]
    },
    'premium': {
        'name': 'Premium',
        'emoji': '💎',
        'history_days': None,
        'growth_entries': None,
        'active_reminders': None,
        'children_count': 5,
        'mpasi_entries': None,
        'pumping_entries': None,
        'sleep_record': None,
        'features': [
            'Semua fitur unlimited',
            'Riwayat tanpa batas',
            'Pengingat unlimited',
            'Analisis mingguan & bulanan',
            'Grafik pertumbuhan percentile',
            'Export PDF laporan',
            'Rekomendasi dokter anak',
            'Multi-child support (max 5)',
            'Priority customer support'
        ]
    }
}

# Quick action suggestions
QUICK_ACTIONS = {
    'no_mpasi': "• `catat mpasi` - Log makanan bayi",
    'no_milk': "• `catat susu` - Log ASI/sufor", 
    'no_sleep': "• `catat tidur` - Mulai tracking tidur",
    'no_pumping': "• `catat pumping` - Log ASI perah",
    'no_poop': "• `catat bab` - Log kesehatan pencernaan",
    'view_summary': "• `ringkasan hari ini` - Lihat summary lengkap",
    'view_details': "• `lihat ringkasan [jenis]` - Detail per kategori"
}

# Nutrition recommendations
NUTRITION_RECOMMENDATIONS = {
    'low_calories': "Pertimbangkan tambah asupan kalori",
    'high_calories': "Asupan kalori tinggi - monitor pertumbuhan", 
    'no_mpasi': "Belum ada MPASI hari ini",
    'high_mpasi_frequency': "Frekuensi MPASI tinggi - sesuaikan porsi",
    'no_milk': "Belum ada catatan minum susu hari ini",
    'mpasi_dominant': "Dominasi MPASI - pastikan cukup cairan",
    'low_mpasi_portion': "MPASI porsi kecil - pertimbangkan variasi makanan",
    'high_milk_frequency': "Frekuensi minum tinggi - normal untuk bayi kecil",
    'low_milk_frequency': "Frekuensi minum rendah - monitor hidrasi"
}

# Sleep recommendations  
SLEEP_RECOMMENDATIONS = {
    'insufficient': "Bayi mungkin perlu tidur lebih banyak",
    'excessive': "Total tidur sangat banyak (normal untuk newborn)",
    'many_sessions': "Banyak sesi tidur pendek - normal untuk bayi kecil", 
    'few_sessions': "Sedikit sesi tidur - bayi mulai tidur lebih lama",
    'good_pattern': "Pola tidur dalam rentang normal"
}

# Health recommendations
HEALTH_RECOMMENDATIONS = {
    'no_poop': "Belum BAB hari ini - monitor hidrasi",
    'frequent_poop': "Frekuensi BAB tinggi - konsultasi dokter jika perlu",
    'normal_poop': "Frekuensi BAB dalam rentang normal"
}

# Application configuration
APP_CONFIG = {
    'version': '2.0.0',
    'name': 'Baby Log WhatsApp Chatbot',
    'description': 'Comprehensive baby tracking with advanced logging',
    'session_timeout_minutes': 30,
    'default_timezone': 'Asia/Jakarta',
    'max_message_length': 1600,  # WhatsApp limit
    'max_reminder_interval_hours': 12,
    'max_sleep_duration_hours': 20,
    'max_volume_ml': 1000,
    'max_calorie_per_ml': 5.0,
    'default_asi_kcal': 0.67,
    'default_sufor_kcal': 0.7
}

# Feature flags
FEATURE_FLAGS = {
    'enable_gpt_calorie_estimation': True,
    'enable_growth_percentiles': False,
    'enable_pdf_export': True, 
    'enable_family_sharing': False,
    'enable_advanced_analytics': False,
    'enable_doctor_recommendations': False
}
