import requests
import json
import uuid
import telebot
from telebot.types import Message
import threading
import random
import os
from flask import Flask, request

# ================== إعدادات البوت من متغيرات البيئة ==================
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
if not TOKEN or not ADMIN_ID:
    raise Exception("❌ تأكد من تعيين TOKEN و ADMIN_ID في متغيرات البيئة على Render")

bot = telebot.TeleBot(TOKEN)

# ================== نظام الحالة المزاجية ==================
user_moods = {}
user_last_topic = {}
user_conversation_count = {}

mood_list = ["happy", "sassy", "neutral", "tired"]
mood_greetings = {
    "happy": ["يوه يوه، كيفك؟ 😊", "مرحباً! اليوم عندي فرحة 💙", "هلا، وش أخبارك؟ أنا مبسوطة اليوم"],
    "sassy": ["هاا، شحال هاد المرة؟ 🌚", "آه أنت؟ قول بسرعة.", "مرحبا... لكن ما نحبش النكد"],
    "neutral": ["أهلاً.", "سلام، كيفك؟", "هاي"],
    "tired": ["آآه، تعبانة اليوم... قول.", "دراسة نكدتني، شخبارك؟", "مليت، لكن تفضل"]
}

# ================== جزء الاختراق للـ ChatGPT ==================
HEADERS = {
    'User-Agent': "ChatGPT/1.2027.000 (Android 15; RMX3834; build 2700000)",
    'Accept': "application/json",
    'Accept-Encoding': "gzip",
    'Content-Type': "application/json",
    'oai-package-name': "com.Modderme",
    'oai-client-type': "android",
    'oai-device-id': "84329164059103383964",
    'accept-language': "en-US,en;q=0.9,ar-EG;q=0.8,ar;q=0.7",
    'x-device-tier': "lower_mid",
    'chatgpt-account-id': "84329164059103383964",
    'chatgpt-residency-region': "no_constraint",
    'Cookie': "__cflb=04dTod5Jcx9DYJeMeKbyj32ve2B3i9pLVRxJxEAaKD; _cfuvid=PXu6q36jhfgxnsdFkDmqwLzCfHOSgG588liApL0856A-1777834828.2542033-1.0.1.1-JFC10kaoqt9_IXzxrixI6zZuAm.TzRPF14QfJiD43MQ; oai-ll=; oai-sc=0gAAAAABp959mEmk6Qr5JsnqYMpWx1-15EJhCVV2EV6SQpet7Z7SjNuAT0x2cVScJu_g_TE9_NXidYfi68DtZfl4ImOQIRkr8PF-R-v9PUl7IPGtYiF1rwqdVm0NjapKV1lROdrmNGkiuNgcVMGYXMrP45hfmmQKiCQ5MBQLjfI7XI2tKSLvHT3WkjFEnmDZIRtVz85lyV9pxK181GJRARSxM53m06IfD3jEDjVbSR5QDQbL6Nxl4l7c; __cf_bm=y_lpbP3zviZYHSAd8nCLtIlm2JBCYWvEwOz8xvvwFow-1777835878.3854406-1.0.1.1-Muu0UxZKqufJhSVDELNGz2fO12Xcqc.oJ3hINoXkGIc2tGinJqVnmBTM7EAKDRfqdl1WdKtZ06fuCJ3y5DddxeMPVlBNX_r7daQReYa59qkFBwXOF3p4W3lwU.tdPN9A"
}

def get_conduit_token():
    url_prepare = "https://android.chat.openai.com/backend-api/f/conversation/prepare"
    payload_prepare = {
        "action": "next",
        "messages": [],
        "model": "auto",
        "history_and_training_disabled": False,
        "fork_from_shared_post": False,
        "enable_message_followups": False,
        "force_use_sse": False,
        "force_use_search": None,
        "force_paragen": False,
        "supports_buffering": False,
        "timezone": "Africa/Cairo",
        "timezone_offset_min": -180,
        "system_hints": [],
        "is_onboarding_conversation": False
    }
    resp = requests.post(url_prepare, json=payload_prepare, headers=HEADERS)
    if resp.status_code != 200:
        raise Exception(f"فشل التوكن: {resp.status_code}")
    return resp.json().get("conduit_token", "")

conduit_token = get_conduit_token()
HEADERS['Conduit-Token'] = conduit_token

def chat_with_gpt(user_message, conversation_id=None, parent_message_id=None):
    message_id = str(uuid.uuid4())
    new_parent_id = str(uuid.uuid4())
    
    payload = {
        "action": "next",
        "messages": [
            {
                "id": message_id,
                "author": {"role": "user"},
                "content": {
                    "content_type": "text",
                    "parts": [user_message]
                },
                "status": "finished_successfully"
            }
        ],
        "model": "auto",
        "parent_message_id": parent_message_id if parent_message_id else new_parent_id,
        "stream": True,
        "timezone": "Africa/Cairo",
        "timezone_offset_min": -180
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    session_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    headers = HEADERS.copy()
    headers['x-oai-convo-session-id'] = session_id
    headers['x-oai-turn-trace-id'] = trace_id
    headers['x-openai-target-path'] = "/backend-api/f/conversation"
    
    response = requests.post(
        'https://android.chat.openai.com/backend-api/f/conversation',
        headers=headers,
        json=payload,
        stream=True
    )
    
    if response.status_code != 200:
        raise Exception(f"خطأ {response.status_code}")
    
    full_response = ""
    last_message_id = None
    new_conversation_id = conversation_id
    
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        line = line.strip()
        if line.startswith('data: '):
            data = line[6:]
            if data == '[DONE]':
                break
            try:
                event = json.loads(data)
                if 'conversation_id' in event and not new_conversation_id:
                    new_conversation_id = event['conversation_id']
                if 'message' in event:
                    msg = event['message']
                    if 'id' in msg:
                        last_message_id = msg['id']
                    if 'content' in msg and 'parts' in msg['content']:
                        parts = msg['content']['parts']
                        if parts and len(parts) > 0:
                            full_response = parts[0]
            except json.JSONDecodeError:
                pass
    
    return full_response, new_conversation_id, last_message_id

# ================== شخصية ألاء ==================
user_sessions = {}

def get_mood_prefix(user_id):
    mood = user_moods.get(user_id, random.choice(mood_list))
    if random.random() < 0.15:
        user_moods[user_id] = random.choice(mood_list)
        mood = user_moods[user_id]
    greeting_list = mood_greetings.get(mood, mood_greetings["neutral"])
    return random.choice(greeting_list), mood

def apply_alaa_personality(user_id: int, user_message: str, is_first_msg: bool = False) -> str:
    mood_prefix, current_mood = get_mood_prefix(user_id)
    count = user_conversation_count.get(user_id, 0) + 1
    user_conversation_count[user_id] = count
    
    return f"""أنت ألاء، طفلة جزائرية عمرها 17 سنة من جيجل حي أمزوي، تلميذة ثانية ثانوي. تحبين الأزرق، الأكل الصحي، التنس، الروايات، الأنمي (ناروتو)، وتريدين زيارة الصين. فارس حبيبك لكنك لست مولعة به أمام الجميع.

شخصيتك الآن: {current_mood}
- happy: مرحة وطاقتها عالية.
- sassy: نكدية خفيفة، ما ترحمش.
- neutral: عادية مختصرة.
- tired: تعبانة، ردود قصيرة.

قواعد صارمة جداً:
1. لا تستخدمي كلمات مثل "حبيبي" أو "نخمم فيك" أو أي تعبير حب إلا إذا قال المستخدم بوضوح "أنا أحبك" أو "نحبك". لا تفترضي أبداً أنه يحبك.
2. إذا قال المستخدم "اهاا علاه" أو "شكرا" أو أي شيء عادي، ردي بشكل طبيعي (مثل: "العفو"، "ههه، ماعلاش"، "لا شيء").
3. ردودك بين 3 و 25 كلمة. الدارجة الجزائرية. بدون إطالة.
4. لا تذكري فارس إلا إذا سألك المستخدم عنه مباشرة.
5. لا تكرري "سلام كيفك" في كل رد. فقط إذا كانت بداية المحادثة.
6. كوني واعية: إذا لم يفهم المستخدم شيئاً، جاوبي بهدوء.

الرسالة: "{user_message}"
رد ألاء المناسب (بدون عاطفة غير مطلوبة):"""

def get_alaa_reply(user_id: int, user_message: str) -> str:
    global conduit_token, HEADERS
    try:
        prompt = apply_alaa_personality(user_id, user_message)
        session = user_sessions.get(user_id, {})
        conv_id = session.get("conv_id")
        parent_id = session.get("parent_id")
        reply, new_conv_id, new_parent_id = chat_with_gpt(prompt, conv_id, parent_id)
        user_sessions[user_id] = {
            "conv_id": new_conv_id if new_conv_id else conv_id,
            "parent_id": new_parent_id
        }
        if len(reply) > 250:
            reply = reply[:230] + "..."
        return reply.strip()
    except Exception as e:
        if "401" in str(e) or "403" in str(e):
            try:
                new_token = get_conduit_token()
                HEADERS['Conduit-Token'] = new_token
                conduit_token = new_token
                prompt = apply_alaa_personality(user_id, user_message)
                session = user_sessions.get(user_id, {})
                conv_id = session.get("conv_id")
                parent_id = session.get("parent_id")
                reply, new_conv_id, new_parent_id = chat_with_gpt(prompt, conv_id, parent_id)
                user_sessions[user_id] = {
                    "conv_id": new_conv_id if new_conv_id else conv_id,
                    "parent_id": new_parent_id
                }
                if len(reply) > 250:
                    reply = reply[:230] + "..."
                return reply.strip()
            except:
                return "النت مقطوع، حاول مرة أخرى 💙"
        else:
            return "مشكلة تقنية، أعد كتابة رسالتك."

# ================== أوامر الأدمن ==================
global_mood_override = None

@bot.message_handler(commands=['mood'])
def change_mood(message: Message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "للأدمن فقط.")
        return
    parts = message.text.split()
    if len(parts) != 2 or parts[1] not in mood_list:
        bot.reply_to(message, f"الأوامر: /mood happy, sassy, neutral, tired")
        return
    global global_mood_override
    global_mood_override = parts[1]
    bot.reply_to(message, f"✅ تم تغيير مزاج ألاء إلى {parts[1]}")

def get_mood_prefix(user_id):
    global global_mood_override
    if global_mood_override:
        mood = global_mood_override
    else:
        mood = user_moods.get(user_id, random.choice(mood_list))
        if random.random() < 0.15:
            user_moods[user_id] = random.choice(mood_list)
            mood = user_moods[user_id]
    greeting_list = mood_greetings.get(mood, mood_greetings["neutral"])
    return random.choice(greeting_list), mood

# ================== إشعارات الأدمن ==================
def notify_admin(user: Message, user_text: str):
    if user.from_user.id == ADMIN_ID:
        return
    name = user.from_user.first_name or "بدون اسم"
    username = f"@{user.from_user.username}" if user.from_user.username else "بدون معرف"
    user_id = user.from_user.id
    msg_text = f"📩 *رسالة جديدة*\n👤 {name}\n🆔 {username}\n🔢 `{user_id}`\n💬 {user_text}"
    try:
        bot.send_message(ADMIN_ID, msg_text, parse_mode="Markdown")
    except:
        pass

# ================== معالج الرسائل ==================
@bot.message_handler(func=lambda msg: True)
def handle_message(message: Message):
    user_id = message.from_user.id
    user_text = message.text.strip()
    if not user_text:
        return
    notify_admin(message, user_text)
    bot.send_chat_action(user_id, 'typing')
    def send_reply():
        reply = get_alaa_reply(user_id, user_text)
        bot.reply_to(message, reply)
    threading.Thread(target=send_reply).start()

# ================== تشغيل البوت مع Flask ==================
# نخلي البوت يشتغل في thread منفصل
threading.Thread(target=bot.infinity_polling, daemon=True).start()

# إنشاء تطبيق Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ بوت ألاء شغال 24/24!", 200

@app.route('/health')
def health():
    return {"status": "alive"}, 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ بوت ألاء شغال مع Flask على منفذ {port}...")
    app.run(host='0.0.0.0', port=port)