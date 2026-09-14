
import feedparser
import requests
import schedule
import time
import json
import os
from datetime import datetime
 
# ==========================================
# إعدادات - عدّل هذه القيم فقط
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
 
# ==========================================
# الكلمات المفتاحية للأخبار النيابية
# ==========================================
KEYWORDS = [
    "نائب", "نواب", "مجلس النواب", "المجلس النيابي",
    "برلماني", "برلمانيون", "برلمانية",
    "تصريح نيابي", "استجواب", "سؤال برلماني",
    "لجنة نيابية", "جلسة النواب", "البرلمان البحريني",
    "مجلس الشورى", "شوري", "تشريعي",
    "اقتراح بقانون", "اقتراح برغبة",
    "النائب", "النواب", "عضو مجلس",
]
 
# ==========================================
# روابط RSS للصحف البحرينية
# ==========================================
RSS_FEEDS = {
    "الأيام": [
        "https://www.ayam.com/rss/latest.xml",
        "https://www.ayam.com/rss/politics.xml",
    ],
    "الخليج": [
        "https://www.alkhaleej.online/feed",
    ],
    "البلاد": [
        "https://www.albiladpress.com/feed",
        "https://www.albiladpress.com/rss/politics",
    ],
    "الوطن": [
        "https://www.alwatannews.net/rss/latest",
        "https://www.alwatannews.net/RSS/bahrain",
    ],
}
 
# ==========================================
# ملف لتتبع الأخبار المُرسلة (لتجنب التكرار)
# ==========================================
SENT_FILE = "sent_news.json"
 
def load_sent_news():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()
 
def save_sent_news(sent_set):
    # نحتفظ بآخر 500 خبر فقط
    recent = list(sent_set)[-500:]
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(recent, f, ensure_ascii=False)
 
def is_parliamentary_news(title, summary=""):
    text = (title + " " + summary).lower()
    for kw in KEYWORDS:
        if kw.lower() in text:
            return True
    return False
 
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"خطأ في إرسال تيليغرام: {e}")
        return False
 
def format_message(newspaper, title, link, pub_date=""):
    time_str = ""
    if pub_date:
        try:
            dt = datetime(*pub_date[:6])
            time_str = dt.strftime("%I:%M %p - %d/%m/%Y")
        except:
            time_str = str(pub_date)
 
    msg = f"""🏛️ <b>خبر نيابي</b>
 
📰 <b>المصدر:</b> {newspaper}
📌 <b>العنوان:</b> {title}"""
 
    if time_str:
        msg += f"\n🕐 <b>الوقت:</b> {time_str}"
 
    msg += f"\n\n🔗 <a href='{link}'>اقرأ الخبر كاملاً</a>"
    return msg
 
def check_news():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] جاري فحص الأخبار...")
    sent_news = load_sent_news()
    new_count = 0
 
    for newspaper, feeds in RSS_FEEDS.items():
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    pub_date = entry.get("published_parsed", None)
 
                    if not title or not link:
                        continue
 
                    # تجنب التكرار باستخدام رابط الخبر
                    if link in sent_news:
                        continue
 
                    if is_parliamentary_news(title, summary):
                        msg = format_message(newspaper, title, link, pub_date)
                        success = send_telegram_message(msg)
                        if success:
                            sent_news.add(link)
                            new_count += 1
                            print(f"  ✓ تم الإرسال: {title[:50]}...")
                            time.sleep(1)  # تجنب الإرسال السريع
 
            except Exception as e:
                print(f"  ✗ خطأ في {newspaper} ({feed_url}): {e}")
 
    save_sent_news(sent_news)
    print(f"  → تم إرسال {new_count} خبر جديد")
 
def send_startup_message():
    msg = """🤖 <b>بوت الأخبار النيابية البحرينية</b>
 
✅ البوت شغّال الآن ويراقب:
• 📰 الأيام
• 📰 الخليج  
• 📰 البلاد
• 📰 الوطن
 
⏰ يتم الفحص كل ساعة تلقائياً
🔍 يبحث عن: تصريحات النواب، جلسات المجلس، الاستجوابات، اقتراحات القوانين"""
    send_telegram_message(msg)
 
# ==========================================
# تشغيل البوت
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("بوت الأخبار النيابية البحرينية")
    print("=" * 50)
 
    # تحقق من الإعدادات
    if "ضع_توكن" in TELEGRAM_TOKEN or "ضع_chat" in CHAT_ID:
        print("⚠️  الرجاء تعديل TELEGRAM_TOKEN و CHAT_ID أولاً")
        exit(1)
 
    # رسالة بدء التشغيل
    send_startup_message()
 
    # فحص فوري عند البدء
    check_news()
 
    # جدولة الفحص كل ساعة
    schedule.every(1).hours.do(check_news)
 
    print("\nالبوت يعمل... اضغط Ctrl+C للإيقاف\n")
    while True:
        schedule.run_pending()
        time.sleep(60)
 
