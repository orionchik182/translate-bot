import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
import telebot
from telebot import types
from gtts import gTTS
import azure.cognitiveservices.speech as speechsdk
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")
MONGO_URI = os.getenv("MONGO_URI")

uri = MONGO_URI

mongo_client = MongoClient(uri, server_api=ServerApi('1'))
db = mongo_client.translate
collection = db.words


user_states = {}

try:
    mongo_client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)


# Инициализация клиентов
bot = telebot.TeleBot(TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

direction_map = {
    "ru_en": {"source": "russian", "target": "english"},
    "en_ru": {"source": "english", "target": "russian"},
    "ru_ka": {"source": "russian", "target": "georgian"},
    "ka_ru": {"source": "georgian", "target": "russian"},
    "ru_tr": {"source": "russian", "target": "turkey"},
    "tr_ru": {"source": "turkey", "target": "russian"}
}

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилище состояний пользователей
user_states = {}

# Клавиатура выбора направления перевода
def get_translate_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.row("Русский → Английский", "Английский → Русский")
    keyboard.row("Русский → Грузинский", "Грузинский → Русский")
    keyboard.row("Русский → Турецкий", "Турецкий → Русский")
    keyboard.row("🔙 Назад")
    return keyboard


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_states[message.chat.id] = {}
    bot.send_message(
        message.chat.id,
        "🏁 Выберите направление перевода:",
        reply_markup=get_translate_keyboard()
    )


# Обработчик выбора языка
@bot.message_handler(func=lambda message: message.text in ["Русский → Английский", "Английский → Русский",
                                                           "Русский → Грузинский", "Грузинский → Русский",
                                                           "Русский → Турецкий", "Турецкий → Русский", "🔙 Назад"])
def handle_lang_selection(message):
    chat_id = message.chat.id
    text = message.text

    if text == "🔙 Назад":
        bot.send_message(chat_id, "🔄 Выберите направление:", reply_markup=get_translate_keyboard())
        return

    lang_map = {
        "Русский → Английский": "ru_en",
        "Английский → Русский": "en_ru",
        "Русский → Грузинский": "ru_ka",
        "Грузинский → Русский": "ka_ru",
        "Русский → Турецкий": "ru_tr",
        "Турецкий → Русский": "tr_ru"
    }

    user_states[chat_id] = {"direction": lang_map[text]}
    bot.send_message(chat_id, "📩 Отправьте текст или голосовое сообщение:", reply_markup=types.ReplyKeyboardRemove())


# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    if message.text.startswith('/'):
        return

    if 'direction' not in user_states.get(chat_id, {}):
        bot.send_message(chat_id, "ℹ️ Сначала выберите язык через /start", reply_markup=get_translate_keyboard())
        return

    try:
        msg = bot.send_message(chat_id, "⏳ Обрабатываю запрос...")
        direction = user_states[chat_id]['direction']
        translated = translate_text(message.text, direction)
        audio_file = generate_tts(translated, direction)

        bot.edit_message_text(f"✅ Перевод:\n{translated}", chat_id, msg.message_id)
        with open(audio_file, 'rb') as audio:
            bot.send_voice(chat_id, audio)

        user_states[chat_id]['original_text'] = message.text
        user_states[chat_id]['translated_text'] = translated
        bot.send_message(chat_id, "Хотите добавить полученный результат в базу Монго? Напишите да или нет.")

    except Exception as e:
        logger.error(f"Text error: {e}")
        bot.send_message(chat_id, "❌ Ошибка перевода")




# Обработчик голосовых сообщений
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    chat_id = message.chat.id
    if 'direction' not in user_states.get(chat_id, {}):
        bot.send_message(chat_id, "ℹ️ Сначала выберите язык через /start", reply_markup=get_translate_keyboard())
        return

    try:
        msg = bot.send_message(chat_id, "⏳ Обрабатываю аудио...")
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open('voice.ogg', 'wb') as f:
            f.write(downloaded_file)

        text = transcribe_audio('voice.ogg')
        translated = translate_text(text, user_states[chat_id]['direction'])
        audio_file = generate_tts(translated, user_states[chat_id]['direction'])

        bot.edit_message_text(
            f"🔊 Распознано: {text}\n\n✅ Перевод:\n{translated}",
            chat_id,
            msg.message_id
        )
        with open(audio_file, 'rb') as audio:
            bot.send_voice(chat_id, audio)

        user_states[chat_id]['original_text'] = text
        user_states[chat_id]['translated_text'] = translated
        bot.send_message(chat_id, "Хотите добавить полученный результат в базу Монго? Напишите да или нет.")

    except Exception as e:
        logger.error(f"Voice error: {e}")
        bot.send_message(chat_id, "❌ Ошибка обработки аудио")




def translate_text(text: str, direction: str) -> str:
    lang_map = {
        "ru_en": ("русский", "английский"),
        "en_ru": ("английский", "русский"),
        "ru_ka": ("русский", "грузинский"),
        "ka_ru": ("грузинский", "русский"),
        "ru_tr": ("русский", "турецкий"),
        "tr_ru": ("турецкий", "русский"),
    }

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": f"Переведи текст с {lang_map[direction][0]} на {lang_map[direction][1]}"},
                      {"role": "user", "content": text}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise


def generate_tts(text: str, direction: str) -> str:
    if direction in ["ru_ka", "ka_ru"]:
        return generate_azure_tts(text)

    lang_codes = {
        "ru_en": "en", "en_ru": "ru",
        "ru_ka": "ka", "ka_ru": "ru",
        "ru_tr": "tr", "tr_ru": "ru"
    }

    try:
        tts = gTTS(text=text, lang=lang_codes[direction], slow=False)
        filename = f"tts_{direction}_{hash(text)}.mp3"
        tts.save(filename)
        return filename
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise


def generate_azure_tts(text: str) -> str:
    try:
        speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_REGION)
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            filename = f"azure_tts_{hash(text)}.wav"
            with open(filename, 'wb') as audio_file:
                audio_file.write(result.audio_data)
            return filename
        else:
            raise Exception(f"Error synthesizing speech: {result.error_details}")

    except Exception as e:
        logger.error(f"Azure TTS error: {e}")
        raise


def transcribe_audio(file_path: str) -> str:
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1"
            )
        return transcript.text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise


@bot.message_handler(func=lambda message: message.text.lower() in ['да', 'нет'])
def handle_save_answer(message):
    chat_id = message.chat.id
    user_state = user_states.get(chat_id, {})

    if message.text.lower() == 'нет':
        bot.send_message(chat_id, "Хорошо, перевод не сохранён.")
        return

    try:
        # Получаем данные из состояния
        original = user_state.get('original_text')
        translated = user_state.get('translated_text')
        direction = user_state.get('direction')

        if not all([original, translated, direction]):
            raise ValueError("Missing translation data")

        # Создаем документ для базы
        doc = {
            "russian": "",
            "english": "",
            "georgian": "",
            "turkey": "",
            "example": ""
        }

        # Заполняем соответствующие поля
        mapping = direction_map.get(direction)
        if mapping:
            doc[mapping['source']] = original
            doc[mapping['target']] = translated

        # Сохраняем в MongoDB
        collection.insert_one(doc)
        bot.send_message(chat_id, "✅ Перевод успешно сохранен в базе!")

    except Exception as e:
        logger.error(f"MongoDB save error: {e}")
        bot.send_message(chat_id, "❌ Ошибка при сохранении перевода")
    finally:
        # Очищаем временные данные
        keys = ['original_text', 'translated_text']
        for key in keys:
            if key in user_states[chat_id]:
                del user_states[chat_id][key]


if __name__ == "__main__":
    logger.info("Бот запущен")
    bot.infinity_polling(none_stop=True)
