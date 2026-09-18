import feedparser
import requests
import schedule
import time
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

# كلمات بحرينية صرفة - تكفي وحدها بدون شرط "البحرين" لأنها غير قابلة للالتباس
KEYWORDS_BAHRAIN_SPECIFIC = [
    "مجلس النواب البحريني",
    "البرلمان البحريني",
    "المجلس النيابي البحريني",
    "مجلس النواب البحرين",
    "محمد إبراهيم السيسي",  # أمين عام مجلس النواب
    "أحمد بن سلمان الملا",  # رئيس مجلس النواب
    "علي بن صالح الصالح",  # رئيس مجلس الشورى
    "كريمة العباسي",  # أمينة عام مجلس الشورى
    "الدائرة الثامنة",
    "دائرة سترة",
]

# كلمات عامة نيابية - لازم يترافق معها ذكر "البحرين" بنفس الخبر
KEYWORDS_GENERAL = [
    "نائب", "نواب", "مجلس النواب", "المجلس النيابي",
    "برلماني", "برلمانيون", "برلمانية",
    "تصريح نيابي", "استجواب", "سؤال برلماني",
    "لجنة نيابية", "جلسة النواب",
    "مجلس الشورى", "تشريعي",
    "اقتراح بقانون", "اقتراح برغبة",
    "النائب", "النواب", "عضو مجلس",
]

# كلمات خاصة بالنائب جليلة علوي - أسماء ومسميات محددة فقط، بدون كلمات عامة
# ملاحظة: تم حذف "لجنة التحكيم" و"جائزة الملك حمد للتسامح" لأنها عامة جداً
# وتنطبق على مسابقات وجوائز أخرى لا علاقة لها بالنائبة
KEYWORDS_JALILA = [
    "جليلة علوي",
    "جليلة السيد حسن",
    "علوي السيد حسن",
    "جليلة علوي السيد حسن",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

RSS_FEEDS = {
    "الأيام": [
        "https://www.ayam.com/rss/latest.xml",
        "https://www.ayam.com/rss/politics.xml",
    ],
    "الخليج": [
        "https://www.alkhaleej.online/feed",
        "https://www.alkhaleej.online/rss",
    ],
    "البلاد": [
        "https://www.albiladpress.com/feed",
        "https://www.albiladpress.com/rss",
    ],
    "الوطن": [
        "https://www.alwatannews.net/rss/latest",
        "https://www.alwatannews.net/RSS/bahrain",
    ],
}

SENT_FILE = "sent_news.json"

def load_sent_news():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_sent_news(sent_set):
    recent = list(sent_set)[-500:]
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(recent, f, ensure_ascii=False)

def check_news_type(title, summary=""):
    """يرجع نوع الخبر: jalila أو parliamentary أو None"""
    text = title + " " + summary
    text_lower = text.lower()

    # أولاً: تحقق من اسم النائبة مباشرة (كلمات محددة فقط، ما تحتاج شرط إضافي)
    for kw in KEYWORDS_JALILA:
        if kw.lower() in text_lower:
            return "jalila"

    # ثانياً: كلمات بحرينية صرفة - تكفي وحدها
    for kw in KEYWORDS_BAHRAIN_SPECIFIC:
        if kw.lower() in text_lower:
            return "parliamentary"

    # ثالثاً: كلمات عامة - لازم يكون الخبر مذكور فيه "البحرين" صراحة
    has_bahrain_context = (
        "البحرين" in text or "البحريني" in text or "البحرينية" in text
    )
    if has_bahrain_context:
        for kw in KEYWORDS_GENERAL:
            if kw.lower() in text_lower:
                return "parliamentary"

    return None

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
        print(f"خطأ تيليغرام: {e}")
        return False

def fetch_feed(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            return feed
    except:
        pass
    try:
        feed = feedparser.parse(url)
        return feed
    except:
        return None

def format_message(newspaper, title, link, news_type, pub_date=""):
    time_str = ""
    if pub_date:
        try:
            dt = datetime(*pub_date[:6])
            time_str = dt.strftime("%I:%M %p - %d/%m/%Y")
        except:
            pass

    if news_type == "jalila":
        icon = "⭐️"
        label = "خبر النائب جليلة علوي"
    else:
        icon = "🏛️"
        label = "خبر نيابي"

    msg = f"""{icon} <b>{label}</b>

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
                feed = fetch_feed(feed_url)
                if not feed or not feed.entries:
                    print(f"  ⚠️ {newspaper}: لا توجد مقالات")
                    continue

                print(f"  ✓ {newspaper}: {len(feed.entries)} مقالة")

                for entry in feed.entries:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    pub_date = entry.get("published_parsed", None)

                    if not title or not link:
                        continue

                    if link in sent_news:
                        continue

                    news_type = check_news_type(title, summary)
                    if news_type:
                        msg = format_message(newspaper, title, link, news_type, pub_date)
                        success = send_telegram_message(msg)
                        if success:
                            sent_news.add(link)
                            new_count += 1
                            print(f"  📨 [{news_type}] أُرسل: {title[:50]}...")
                            time.sleep(1)

            except Exception as e:
                print(f"  ✗ خطأ {newspaper}: {e}")

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

🔍 <b>يبحث عن:</b>
• الأخبار النيابية البحرينية فقط (تشترط ذكر "البحرين" مع الكلمة المفتاحية)
• ⭐️ أي خبر يذكر اسم النائب جليلة علوي السيد حسن صراحة"""
    send_telegram_message(msg)

if __name__ == "__main__":
    print("=" * 50)
    print("بوت الأخبار النيابية البحرينية")
    print("=" * 50)

    send_startup_message()
    check_news()

    schedule.every(1).hours.do(check_news)

    print("\nالبوت يعمل...\n")
    while True:
        schedule.run_pending()
        time.sleep(60)
