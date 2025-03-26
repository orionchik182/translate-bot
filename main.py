import  telebot
from  telebot import types

bot = telebot.TeleBot('7870707188:AAEaNCvN1yFQQgaEmz5QbC3lBGn-iswEin4')

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('send foto')
    markup.row(btn1)
    btn2 = types.InlineKeyboardButton('Удалить фото')
    btn3 = types.InlineKeyboardButton('Изменить текст')
    markup.row(btn2, btn3)
    bot.send_message(message.chat.id, 'Привет', reply_markup=markup)
    bot.register_next_step_handler(message, on_click)

def on_click(message):
    if message.text == 'send foto':
       file = open('./translate.webp', 'rb')
       bot.send_photo(message.chat.id, file)
    elif message.text == 'Удалить фото':
        bot.send_message(message.chat.id, "Deleted")
    elif message.text == 'Изменить текст':
        bot.send_message(message.chat.id, "Edited")


@bot.message_handler(content_types=['photo'])
def get_photo(message):
    markup =types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Перейти на сайт', url="https://google.com")
    markup.row(btn1)
    btn2 = types.InlineKeyboardButton('Удалить фото', callback_data="delete")
    btn3 = types.InlineKeyboardButton('Изменить текст', callback_data="edit")
    markup.row(btn2, btn3)
    bot.reply_to(message, 'Какое странное фото', reply_markup=markup)

@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    if callback.data == 'delete':
        bot.delete_message(callback.message.chat.id, callback.message.message_id - 1)
    elif callback.data == 'edit':
        bot.edit_message_text('Edited text', callback.message.chat.id, callback.message.message_id)

@bot.message_handler()
def info(message):
    if message.text.lower() == 'привет':
        bot.send_message(message.chat.id, f'Hi, {message.from_user.first_name}')
    elif message.text.lower() == 'id':
        bot.reply_to(message, f'ID {message.from_user.id}')

bot.polling(none_stop=True)