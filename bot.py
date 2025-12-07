import telebot
from telebot import types
from datetime import datetime
import os
from flask import Flask
from threading import Thread
import time

# ==== СЕЙФ (НАСТРОЙКИ СЕРВЕРА) ====
# Бот теперь ищет эти данные в настройках Render, а не в коде
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ARCHIVE_CHAT_ID = os.environ.get("ARCHIVE_CHAT_ID")

# Проверка на ошибки при запуске
if not BOT_TOKEN or not ARCHIVE_CHAT_ID:
    print("CRITICAL ERROR: Токен или ID архива не найдены в переменных окружения!")

bot = telebot.TeleBot(BOT_TOKEN)

# Хранилище (Внимание: при перезагрузке сервера Render черновики очищаются)
user_stories = {}

# ==== ВЕБ-СЕРВЕР (ЧТОБЫ БОТ НЕ СПАЛ) ====
app = Flask('')

@app.route('/')
def home():
    return "Bot is running and waiting for stories..."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==== КЛАВИАТУРЫ ====

def get_start_keyboard():
    """Кнопка, которая будет висеть в ПУБЛИЧНОЙ группе"""
    keyboard = types.InlineKeyboardMarkup()
    # url нужен, чтобы перекинуть человека из группы в личку к боту
    bot_username = bot.get_me().username
    start_btn = types.InlineKeyboardButton(
        "📖 Рассказать историю (в личку)", 
        url=f"https://t.me/{bot_username}?start=story_mode"
    )
    keyboard.add(start_btn)
    return keyboard

def get_continue_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    add_btn = types.InlineKeyboardButton("➕ Добавить ещё (текст/фото/аудио)", callback_data="add_more")
    location_btn = types.InlineKeyboardButton("📍 Добавить место события", callback_data="add_location")
    finish_btn = types.InlineKeyboardButton("✅ Завершить и отправить", callback_data="finish_story")
    cancel_btn = types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_story")
    keyboard.add(add_btn, location_btn, finish_btn, cancel_btn)
    return keyboard

def get_confirmation_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    public_btn = types.InlineKeyboardButton("👤 С моим именем", callback_data="send_public")
    anonymous_btn = types.InlineKeyboardButton("🎭 Анонимно", callback_data="send_anonymous")
    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_editing")
    keyboard.add(public_btn)
    keyboard.add(anonymous_btn)
    keyboard.add(back_btn)
    return keyboard

# ==== СПЕЦИАЛЬНАЯ КОМАНДА ДЛЯ АДМИНА ====
# Напиши /post_menu в своей публичной группе, чтобы бот вывел кнопку
@bot.message_handler(commands=['post_menu'])
def post_public_menu(message):
    # Здесь можно добавить проверку на твой ID, чтобы никто другой не мог это сделать
    # Но пока оставим просто так для теста
    bot.send_message(
        message.chat.id,
        "🔥 **Уголок Городского Фольклора**\n\n"
        "Вы видели что-то странное? Слышали легенду, о которой страшно говорить?\n"
        "Этот архив собирает ваши истории.\n\n"
        "Нажмите кнопку ниже, чтобы рассказать свою историю анонимно или публично.",
        parse_mode="Markdown",
        reply_markup=get_start_keyboard()
    )

# ==== ЛОГИКА БОТА ====

# Обработка команды /start (с параметром story_mode или без)
@bot.message_handler(commands=['start'])
def start_private(message):
    if message.chat.type != 'private':
        return

    # Если перешли по кнопке из группы
    if len(message.text.split()) > 1 and message.text.split()[1] == 'story_mode':
        start_story_logic(message)
    else:
        bot.send_message(
            message.chat.id, 
            "Добро пожаловать в Архив.\nЧтобы рассказать историю, перейдите в группу или нажмите /start story_mode"
        )

# Функция запуска создания истории
def start_story_logic(message):
    user_id = message.from_user.id
    user_stories[user_id] = {
        "items": [],
        "user_name": message.from_user.first_name,
        "user_username": message.from_user.username or "hidden",
        "user_id": user_id,
        "started_at": datetime.now(),
        "location": None,
        "waiting_for": "content"
    }
    
    bot.send_message(
        user_id,
        "📖 **Архивариус слушает.**\n\n"
        "Присылайте всё по очереди: текст, фото, голосовые, видео.\n"
        "Я буду собирать это в одну папку, пока вы не нажмете «Завершить».\n\n"
        "👇 *Отправьте первый фрагмент прямо сейчас.*",
        parse_mode="Markdown",
        reply_markup=get_continue_keyboard()
    )

# Обработка кнопки "Добавить ещё"
@bot.callback_query_handler(func=lambda call: call.data == "add_more")
def callback_add_more(call):
    user_id = call.from_user.id
    if user_id in user_stories:
        user_stories[user_id]["waiting_for"] = "content"
        bot.answer_callback_query(call.id, "Жду следующий фрагмент...")
        bot.send_message(user_id, "✏️ Жду следующий фрагмент (текст или медиа)...")

# Обработка кнопки "Отмена"
@bot.callback_query_handler(func=lambda call: call.data == "cancel_story")
def callback_cancel(call):
    user_id = call.from_user.id
    if user_id in user_stories:
        del user_stories[user_id]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ История удалена. Черновик очищен.")

# Обработка кнопки "Назад"
@bot.callback_query_handler(func=lambda call: call.data == "back_to_editing")
def callback_back(call):
    bot.edit_message_text(
        "Вернулись к редактированию. Можете добавить еще что-то.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_continue_keyboard()
    )

# Обработка кнопки "Добавить место"
@bot.callback_query_handler(func=lambda call: call.data == "add_location")
def callback_location(call):
    user_id = call.from_user.id
    if user_id in user_stories:
        user_stories[user_id]["waiting_for"] = "location"
        
        # Кнопка для телефона, чтобы отправить гео
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(types.KeyboardButton("📍 Отправить текущее место", request_location=True))
        
        bot.send_message(user_id, "Пришлите геометку (через скрепку 📎 или кнопкой ниже).", reply_markup=kb)
    bot.answer_callback_query(call.id)

# Ловим геолокацию
@bot.message_handler(content_types=['location'])
def handle_location(message):
    user_id = message.from_user.id
    if user_id in user_stories and user_stories[user_id]["waiting_for"] == "location":
        user_stories[user_id]["location"] = message.location
        user_stories[user_id]["waiting_for"] = "content" # Возвращаем режим контента
        
        bot.send_message(
            user_id, 
            "✅ Место записано.", 
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.send_message(
            user_id,
            "Что делаем дальше?",
            reply_markup=get_continue_keyboard()
        )

# Обработка кнопки "Завершить"
@bot.callback_query_handler(func=lambda call: call.data == "finish_story")
def callback_finish(call):
    user_id = call.from_user.id
    if user_id not in user_stories or not user_stories[user_id]["items"]:
        bot.answer_callback_query(call.id, "История пуста!", show_alert=True)
        return

    count = len(user_stories[user_id]["items"])
    bot.edit_message_text(
        f"🏁 История собрана ({count} фрагментов).\nКак отправляем в Архив?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_confirmation_keyboard()
    )

# ФИНАЛЬНАЯ ОТПРАВКА
@bot.callback_query_handler(func=lambda call: call.data in ["send_public", "send_anonymous"])
def send_to_archive_final(call):
    user_id = call.from_user.id
    if user_id not in user_stories:
        bot.answer_callback_query(call.id, "Ошибка: история не найдена (возможно, бот перезагружался).")
        return

    story = user_stories[user_id]
    is_anon = (call.data == "send_anonymous")
    
    # Заголовок для админа
    header = f"🔥 <b>НОВАЯ ИСТОРИЯ</b>\n"
    if is_anon:
        header += "🎭 <b>АНОНИМНО</b> (Автор скрыл себя)\n"
    else:
        header += f"👤 <b>Автор:</b> {story['user_name']} (@{story['user_username']})\n"
    
    header += f"📅 {story['started_at'].strftime('%Y-%m-%d %H:%M')}\n"
    if story['location']:
        header += "📍 Геометка прикреплена\n"
    header += "-----------------------"

    try:
        # 1. Шлем заголовок
        bot.send_message(ARCHIVE_CHAT_ID, header, parse_mode="HTML")

        # 2. Шлем контент (copy_message защищает анонимность лучше, чем forward)
        for item in story['items']:
            bot.copy_message(ARCHIVE_CHAT_ID, item['chat_id'], item['message_id'])

        # 3. Шлем гео, если есть
        if story['location']:
            bot.send_location(ARCHIVE_CHAT_ID, story['location'].latitude, story['location'].longitude)

        # 4. Финальная черта
        bot.send_message(ARCHIVE_CHAT_ID, "-----------------------\n✅ Конец истории.")

        # Успех
        bot.edit_message_text(
            "✅ <b>Ваша история принята в Архив.</b>\nСпасибо за вклад.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )
        del user_stories[user_id]

    except Exception as e:
        bot.send_message(user_id, f"Ошибка при отправке: {e}")

# СБОРЩИК КОНТЕНТА (Текст, Фото, Видео и т.д.)
@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'video_note', 'document', 'audio'])
def handle_content(message):
    user_id = message.from_user.id
    
    # Если пользователь не в режиме истории - игнорируем
    if user_id not in user_stories or user_stories[user_id]["waiting_for"] != "content":
        return

    # Сохраняем ID сообщения, чтобы потом скопировать
    user_stories[user_id]["items"].append({
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'type': message.content_type
    })

    bot.reply_to(message, "Принято 📥", reply_markup=get_continue_keyboard())

# ЗАПУСК
if __name__ == "__main__":
    keep_alive() # Запуск веб-сервера
    bot.infinity_polling()
