from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import time
import sys
import pyperclip
import schedule

# ------------------------------
# ⚙️ بيانات تسجيل الدخول (ثابتة)
# ------------------------------
USERNAME = "موبي14"
PASSWORD = "حمادة2006"

# ------------------------------
# ⚙️ الإعدادات التلقائية
# ------------------------------
ROOM_NAME = "✨🎈"  # اسم الغرفة الافتراضي
MESSAGE = "✨💧"    # الرسالة الافتراضية
REPEAT_COUNT = 5    # عدد المرات الافتراضي
INTERVAL_MINUTES = 10  # الفترة بين التنفيذ (بالدقائق)

# ------------------------------
# 🚀 وظيفة إرسال الرسائل
# ------------------------------
def send_messages():
    print(f"🕒 بدء إرسال الرسائل في: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # إعدادات المتصفح لـ RENDER
        options = webdriver.EdgeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # استخدام webdriver_manager للتأكد من وجود السواق
        driver = webdriver.Edge(EdgeChromiumDriverManager().install(), options=options)
        wait = WebDriverWait(driver, 30)

        # 1) فتح الموقع
        print("🌐 جاري فتح الموقع...")
        driver.get("https://sabaya.ae/")
        time.sleep(5)

        # 2) تسجيل الدخول
        print("🔐 جاري تسجيل الدخول...")
        username_field = wait.until(EC.visibility_of_element_located((By.ID, "login-username-field")))
        password_field = wait.until(EC.visibility_of_element_located((By.NAME, "login_pass")))
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "loginBtn")))

        username_field.send_keys(USERNAME)
        password_field.send_keys(PASSWORD)
        login_button.click()
        time.sleep(5)

        # 3) إغلاق إعلان الكوكيز إذا ظهر
        try:
            close_button = wait.until(EC.element_to_be_clickable((By.ID, "save-and-exit")))
            close_button.click()
            print("✅ تم إغلاق إعلان الكوكيز")
            time.sleep(2)
        except:
            print("ℹ️ لم يظهر إعلان الكوكيز")

        # 4) فتح الشات
        print("💬 جاري فتح الشات...")
        chat_button = wait.until(EC.element_to_be_clickable((By.ID, "js-chat-toggle-button")))
        chat_button.click()
        time.sleep(3)

        # 5) اختيار الغرفة
        print(f"🎯 جاري البحث عن الغرفة: {ROOM_NAME}")
        room_found = False
        
        try:
            room_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"//span[contains(@class,'name') and contains(., '{ROOM_NAME}')]"))
            )
            room_button.click()
            room_found = True
            print("✅ تم العثور على الغرفة")
        except:
            print(f"❌ لم يتم العثور على الغرفة: {ROOM_NAME}")
            driver.quit()
            return

        # 6) التأكد من فتح نافذة الكتابة
        print("⌨️ جاري تهيئة منطقة الكتابة...")
        msg_area = wait.until(EC.element_to_be_clickable((By.ID, "msgArea")))
        time.sleep(2)

        # 7) نسخ الرسالة
        pyperclip.copy(MESSAGE)

        # 8) إرسال الرسائل
        print(f"🔄 جاري إرسال {REPEAT_COUNT} رسالة...")
        
        success_count = 0
        for i in range(REPEAT_COUNT):
            try:
                # تفعيل منطقة الكتابة
                msg_area.click()
                time.sleep(0.5)
                
                # لصق الرسالة
                msg_area.send_keys(Keys.CONTROL, 'v')
                time.sleep(0.5)
                
                # إرسال الرسالة
                msg_area.send_keys(Keys.RETURN)
                
                success_count += 1
                print(f"✅ تم إرسال الرسالة رقم {i+1}")
                time.sleep(3)  # انتظار بين الرسائل
                
            except Exception as e:
                print(f"❌ خطأ في الرسالة {i+1}: {e}")
                # محاولة استعادة الاتصال
                try:
                    msg_area = wait.until(EC.element_to_be_clickable((By.ID, "msgArea")))
                except:
                    break

        print(f"🎉 تم إرسال {success_count} من أصل {REPEAT_COUNT} رسالة بنجاح!")
        driver.quit()

    except Exception as e:
        print(f"❌ حدث خطأ جسيم: {e}")
        try:
            driver.quit()
        except:
            pass

# ------------------------------
# ⏰ جدولة المهام
# ------------------------------
def schedule_messages():
    print("⏰ بدء جدولة إرسال الرسائل التلقائي...")
    print(f"📋 الإعدادات:")
    print(f"   - الغرفة: {ROOM_NAME}")
    print(f"   - الرسالة: {MESSAGE}")
    print(f"   - عدد الرسائل: {REPEAT_COUNT}")
    print(f"   - الفترة: كل {INTERVAL_MINUTES} دقائق")
    
    # جدولة المهمة كل X دقائق
    schedule.every(INTERVAL_MINUTES).minutes.do(send_messages)
    
    # التنفيذ الفوري أول مرة
    send_messages()
    
    # الاستمرار في الجدولة
    while True:
        schedule.run_pending()
        time.sleep(1)

# ------------------------------
# 🚀 التشغيل الرئيسي
# ------------------------------
if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت الرسائل التلقائي لـ RENDER")
    print("⏰ البرنامج سيعمل بشكل مستمر ويرسل الرسائل تلقائياً")
    
    # إذا كانت هناك معطيات من سطر الأوامر
    if len(sys.argv) >= 2:
        ROOM_NAME = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            REPEAT_COUNT = int(sys.argv[2])
        except:
            pass
    if len(sys.argv) >= 4:
        MESSAGE = sys.argv[3]
    if len(sys.argv) >= 5:
        try:
            INTERVAL_MINUTES = int(sys.argv[4])
        except:
            pass
    
    # بدء الجدولة
    schedule_messages()
