import os
import telebot
from telebot import types
from datetime import datetime
from flask import Flask
from threading import Thread

# ==== НАСТРОЙКИ - БЕРУТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ARCHIVE_CHAT_ID = int(os.environ.get('ARCHIVE_CHAT_ID'))
PUBLIC_GROUP_ID = int(os.environ.get('PUBLIC_GROUP_ID'))

# Создаём Flask приложение (чтобы Render не останавливал бота)
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Запускаем Flask в отдельном потоке"""
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

# Создаём бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения историй пользователей
user_stories = {}

# ==== ФУНКЦИИ ДЛЯ СОЗДАНИЯ КЛАВИАТУР ====
def get_start_keyboard():
    """Клавиатура для начала истории"""
    keyboard = types.InlineKeyboardMarkup()
    start_btn = types.InlineKeyboardButton(
        "📖 Рассказать свою историю", 
        callback_data="start_story"
    )
    keyboard.add(start_btn)
    return keyboard

def get_continue_keyboard():
    """Клавиатура для продолжения или завершения"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    add_btn = types.InlineKeyboardButton(
        "➕ Добавить ещё (текст/фото/видео/аудио)", 
        callback_data="add_more"
    )
    location_btn = types.InlineKeyboardButton(
        "📍 Добавить место события", 
        callback_data="add_location"
    )
    finish_btn = types.InlineKeyboardButton(
        "✅ Завершить и отправить", 
        callback_data="finish_story"
    )
    keyboard.add(add_btn, location_btn, finish_btn)
    return keyboard

def get_confirmation_keyboard():
    """Клавиатура для выбора способа отправки"""
    keyboard = types.InlineKeyboardMarkup()
    public_btn = types.InlineKeyboardButton(
        "👤 Отправить с моим именем", 
        callback_data="send_public"
    )
    anonymous_btn = types.InlineKeyboardButton(
        "🎭 Отправить анонимно", 
        callback_data="send_anonymous"
    )
    keyboard.add(public_btn)
    keyboard.add(anonymous_btn)
    return keyboard

# ==== КОМАНДА /start ====
@bot.message_handler(commands=['start'])
def start_private(message):
    if message.chat.type == 'private':
        welcome_text = """
🎭 Добро пожаловать в бот сборника городского фольклора!

Этот бот работает в группе. Найдите закреплённое сообщение в группе и нажмите кнопку "Рассказать свою историю".

Вы сможете отправить:
📝 Текст
🎤 Голосовые сообщения  
📷 Фотографии
🎥 Видео
📍 Геолокацию
📎 Документы

И всё это может быть частью одной истории!
        """
        bot.send_message(message.chat.id, welcome_text)

# ==== ОБРАБОТКА НАЖАТИЯ "НАЧАТЬ ИСТОРИЮ" ====
@bot.callback_query_handler(func=lambda call: call.data == "start_story")
def start_story(call):
    user_id = call.from_user.id
    
    user_stories[user_id] = {
        "items": [],
        "user_name": call.from_user.first_name,
        "user_username": call.from_user.username or "без username",
        "user_id": user_id,
        "started_at": datetime.now(),
        "location": None,
        "waiting_for": "content"
    }
    
    try:
        bot.send_message(
            user_id,
            "📖 Отлично! Начинаем собирать вашу историю.\n\n"
            "Отправьте мне сюда (в личные сообщения):\n"
            "• Текст\n"
            "• Голосовое сообщение\n"
            "• Фото\n"
            "• Видео\n"
            "• Аудио\n"
            "• Документ\n\n"
            "Можете отправить несколько элементов - они все станут частью одной истории!\n\n"
            "Когда закончите - нажмите '✅ Завершить и отправить'",
            reply_markup=get_continue_keyboard()
        )
        
        bot.answer_callback_query(
            call.id, 
            "✅ Проверьте личные сообщения с ботом!",
            show_alert=True
        )
        
    except Exception as e:
        bot.answer_callback_query(
            call.id,
            "⚠️ Сначала напишите боту в личные сообщения! Найдите @" + bot.get_me().username + " и нажмите START",
            show_alert=True
        )

# ==== ОБРАБОТКА "ДОБАВИТЬ ЕЩЁ" ====
@bot.callback_query_handler(func=lambda call: call.data == "add_more")
def add_more(call):
    user_id = call.from_user.id
    
    if user_id in user_stories:
        user_stories[user_id]["waiting_for"] = "content"
        bot.edit_message_text(
            "➕ Отправьте ещё контент (текст, фото, видео, аудио)...",
            call.message.chat.id,
            call.message.message_id
        )
    
    bot.answer_callback_query(call.id)

# ==== ОБРАБОТКА "ДОБАВИТЬ МЕСТО" ====
@bot.callback_query_handler(func=lambda call: call.data == "add_location")
def request_location(call):
    user_id = call.from_user.id
    
    if user_id in user_stories:
        user_stories[user_id]["waiting_for"] = "location"
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        location_btn = types.KeyboardButton("📍 Отправить моё местоположение", request_location=True)
        keyboard.add(location_btn)
        
        bot.send_message(
            user_id,
            "📍 Отправьте геолокацию места, где произошла история.\n\n"
            "Вы можете:\n"
            "• Нажать кнопку ниже для отправки текущего местоположения\n"
            "• Или выбрать любое место на карте вручную (нажмите 📎 → Место)",
            reply_markup=keyboard
        )
    
    bot.answer_callback_query(call.id)

# ==== ОБРАБОТКА "ЗАВЕРШИТЬ ИСТОРИЮ" ====
@bot.callback_query_handler(func=lambda call: call.data == "finish_story")
def finish_story(call):
    user_id = call.from_user.id
    
    if user_id not in user_stories:
        bot.answer_callback_query(call.id, "История не найдена!")
        return
    
    story = user_stories[user_id]
    
    if len(story["items"]) == 0:
        bot.answer_callback_query(
            call.id, 
            "⚠️ Вы ещё ничего не отправили! Добавьте хотя бы один элемент.",
            show_alert=True
        )
        return
    
    preview = "📋 Ваша история готова к отправке!\n\n"
    preview += f"📦 Элементов: {len(story['items'])}\n"
    
    for idx, item in enumerate(story['items'], 1):
        if item['type'] == 'text':
            preview += f"{idx}. 📝 Текст: {item['content'][:50]}...\n"
        elif item['type'] == 'photo':
            preview += f"{idx}. 📷 Фото\n"
        elif item['type'] == 'voice':
            preview += f"{idx}. 🎤 Голосовое ({item['duration']} сек.)\n"
        elif item['type'] == 'video':
            preview += f"{idx}. 🎥 Видео ({item['duration']} сек.)\n"
        elif item['type'] == 'video_note':
            preview += f"{idx}. 🎬 Видео-сообщение ({item['duration']} сек.)\n"
        elif item['type'] == 'document':
            preview += f"{idx}. 📎 Документ: {item['file_name']}\n"
        elif item['type'] == 'audio':
            preview += f"{idx}. 🎵 Аудио: {item['title']}\n"
    
    if story['location']:
        preview += "📍 С геолокацией\n"
    
    preview += "\nВыберите способ отправки:"
    
    bot.edit_message_text(
        preview,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_confirmation_keyboard()
    )
    
    bot.answer_callback_query(call.id)

# ==== ФУНКЦИЯ ДЛЯ ДОБАВЛЕНИЯ ЭЛЕМЕНТА В ИСТОРИЮ ====
def add_item_to_story(message, item_type, **extra_data):
    user_id = message.from_user.id
    
    if user_id not in user_stories:
        bot.reply_to(
            message, 
            "⚠️ Сначала начните историю! Перейдите в группу и нажмите кнопку '📖 Рассказать свою историю'"
        )
        return False
    
    if user_stories[user_id].get("waiting_for") != "content":
        return False
    
    item = {
        "type": item_type,
        "message_id": message.message_id,
        "chat_id": message.chat.id,
        **extra_data
    }
    
    user_stories[user_id]["items"].append(item)
    
    count = len(user_stories[user_id]["items"])
    bot.reply_to(
        message,
        f"✅ Добавлено! Элементов в истории: {count}\n\n"
        f"Выберите действие:",
        reply_markup=get_continue_keyboard()
    )
    
    return True

# ==== ОБРАБОТЧИКИ КОНТЕНТА ====
@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.chat.type != 'private':
        return
    add_item_to_story(message, "text", content=message.text)

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    if message.chat.type != 'private':
        return
    add_item_to_story(message, "voice", duration=message.voice.duration)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.chat.type != 'private':
        return
    caption = message.caption or ""
    add_item_to_story(message, "photo", caption=caption)

@bot.message_handler(content_types=['video'])
def handle_video(message):
    if message.chat.type != 'private':
        return
    caption = message.caption or ""
    add_item_to_story(message, "video", caption=caption, duration=message.video.duration)

@bot.message_handler(content_types=['video_note'])
def handle_video_note(message):
    if message.chat.type != 'private':
        return
    add_item_to_story(message, "video_note", duration=message.video_note.duration)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.chat.type != 'private':
        return
    caption = message.caption or ""
    add_item_to_story(message, "document", file_name=message.document.file_name, caption=caption)

@bot.message_handler(content_types=['audio'])
def handle_audio(message):
    if message.chat.type != 'private':
        return
    title = message.audio.title or "Без названия"
    add_item_to_story(message, "audio", duration=message.audio.duration, title=title)

@bot.message_handler(content_types=['location'])
def handle_location(message):
    if message.chat.type != 'private':
        return
    
    user_id = message.from_user.id
    
    if user_id in user_stories and user_stories[user_id].get("waiting_for") == "location":
        user_stories[user_id]["location"] = {
            "latitude": message.location.latitude,
            "longitude": message.location.longitude,
            "message_id": message.message_id,
            "chat_id": message.chat.id
        }
        
        bot.reply_to(
            message,
            "✅ Геолокация добавлена!\n\n"
            "Что дальше?",
            reply_markup=get_continue_keyboard()
        )
        user_stories[user_id]["waiting_for"] = "content"

# ==== ОТПРАВКА В АРХИВ ====
@bot.callback_query_handler(func=lambda call: call.data in ["send_public", "send_anonymous"])
def send_to_archive(call):
    user_id = call.from_user.id
    
    if user_id not in user_stories:
        bot.answer_callback_query(call.id, "История не найдена!")
        return
    
    story = user_stories[user_id]
    is_anonymous = (call.data == "send_anonymous")
    
    if is_anonymous:
        header = f"""
🎭 НОВАЯ ИСТОРИЯ (анонимно)
⚠️ Автор попросил не раскрывать личность
📅 Дата: {story['started_at'].strftime('%Y-%m-%d %H:%M')}
📦 Элементов: {len(story['items'])}
{"📍 С геолокацией" if story['location'] else ""}

━━━━━━━━━━━━━━━━━━━━
        """
    else:
        header = f"""
📖 НОВАЯ ИСТОРИЯ
👤 От: {story['user_name']} (@{story['user_username']})
🆔 ID: {story['user_id']}
📅 Дата: {story['started_at'].strftime('%Y-%m-%d %H:%M')}
📦 Элементов: {len(story['items'])}
{"📍 С геолокацией" if story['location'] else ""}

━━━━━━━━━━━━━━━━━━━━
        """
    
    bot.send_message(ARCHIVE_CHAT_ID, header)
    
    for idx, item in enumerate(story['items'], 1):
        if item['type'] == 'text':
            bot.send_message(ARCHIVE_CHAT_ID, f"📝 Часть {idx} (текст):\n\n{item['content']}")
        else:
            emoji = {'photo':'📷', 'voice':'🎤', 'video':'🎥', 'video_note':'🎬', 'document':'📎', 'audio':'🎵'}.get(item['type'], '📎')
            bot.send_message(ARCHIVE_CHAT_ID, f"{emoji} Часть {idx}:")
            bot.forward_message(ARCHIVE_CHAT_ID, item['chat_id'], item['message_id'])
    
    if story['location']:
        bot.send_message(ARCHIVE_CHAT_ID, "📍 Место события:")
        bot.forward_message(
            ARCHIVE_CHAT_ID, 
            story['location']['chat_id'], 
            story['location']['message_id']
        )
    
    confirmation = "✅ Ваша история успешно отправлена в архив!\n\n"
    if is_anonymous:
        confirmation += "🎭 История опубликована анонимно."
    else:
        confirmation += "👤 История опубликована с вашим именем."
    
    confirmation += "\n\nСпасибо за участие! Вы можете рассказать ещё одну историю в группе."
    
    bot.edit_message_text(
        confirmation,
        call.message.chat.id,
        call.message.message_id
    )
    
    del user_stories[user_id]
    bot.answer_callback_query(call.id, "✅ Отправлено!")

# ==== ЗАПУСК ====
if __name__ == '__main__':
    print("🤖 Бот запущен и ожидает сообщений...")
    print("🌐 Flask сервер запускается...")
    
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Запускаем бота
    bot.infinity_polling()
