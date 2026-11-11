from datetime import datetime, timedelta, timezone
from html import escape
import http.server
import os
import socketserver
import threading
import time
import requests
import telebot
from telebot import types
from config import open_weather_api_key

# --- ВЕБ-СЕРВЕР ДЛЯ РАБОТЫ НА RENDER ---
PORT = int(os.environ.get("PORT", 10000))


class SimpleHandler(http.server.BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Bot is alive and running!")

  def log_message(self, format, *args):
    pass


def run_web_server():
  try:
    with socketserver.TCPServer(("0.0.0.0", PORT), SimpleHandler) as httpd:
      print(f"Web server running on port {PORT}")
      httpd.serve_forever()
  except Exception as e:
    print(f"Web server error: {e}")


# Запускаем веб-сервер в фоновом потоке
threading.Thread(target=run_web_server, daemon=True).start()

# Создаем бота
bot = telebot.TeleBot("8247005293:AAE-T3d4J_7Thi1avj9PQt_HxXGyqM6mBb8")

# Хранение состояний по чатам
active_chats = set()
user_languages = {}
user_cities = {}
weather_state = {}

WEATHER_NAMES = {
    "uz": {
        "Clear": "Quyoshli ☀️",
        "Clouds": "Bulutli ☁️",
        "Rain": "Yomg'irli 🌧",
        "Drizzle": "Mayda yomg'ir 🌧",
        "Thunderstorm": "Momaqaldiroq ⚡",
        "Snow": "Qor ❄️",
        "Mist": "Tuman 🌫",
        "Fog": "Tuman 🌫",
        "Haze": "Xira havo 🌫",
        "Dust": "Chang 💨",
    },
    "ru": {
        "Clear": "Ясно ☀️",
        "Clouds": "Облачно ☁️",
        "Rain": "Дождливо 🌧",
        "Drizzle": "М. дождь 🌧",
        "Thunderstorm": "Гроза ⚡",
        "Snow": "Снег ❄️",
        "Mist": "Туман 🌫",
        "Fog": "Туман 🌫",
        "Haze": "Дымка 🌫",
        "Dust": "Пыль 💨",
    },
}

TEXTS = {
    "uz": {
        "welcome": (
            "Ob-havo stansiyasi aloqada! 🌤\nOb-havoni bilish uchun shahar"
            " nomini yozing.\n\nHar kuni soat 08:00 da ertalabki ma'lumot va"
            " har 5 daqiqada ob-havo keskin o'zgarsa ogohlantirish"
            " yuboraman!\n\nTilni o'zgartirish: /lang"
        ),
        "stopped": (
            "Ob-havo stansiyasi vaqtincha yopildi 🌡️\nQayta yoqish uchun /start"
            " yuboring."
        ),
        "choose_type": (
            "Tanlangan shahar: <b>{city}</b>.\nQaysi ob-havo ma'lumoti kerak?"
        ),
        "btn_today": "☀️ Bugungi ob-havo",
        "btn_week": "📅 Haftalik ob-havo",
        "city_too_long": (
            "❌ Shahar nomi juda uzun. Qisqaroq yozib ko'ring."
        ),
        "not_found": (
            "❌ Shahar topilmadi. Nomini tekshirib, qaytadan yozing."
        ),
        "not_found_alert": "Xatolik! Shahar topilmadi.",
        "unknown_weather": "Derazadan qarab ko'ring! 🤔",
        "today_msg": (
            "🌍 Shahar: <b>{city}</b>\n🌡 Harorat: <b>{temp}℃</b>  {weather}\n🥶 His"
            " qilinishi: {feels_like}℃\n💧 Namlik: {humidity}%\n📊 Bosim:"
            " {pressure} mm sim. ust.\n💨 Shamol: {wind} m/s\n\n💡"
            " <b>Maslahat:</b> {advice}\n\nKuningiz xayrli o'tsin! 😉"
        ),
        "week_header": "🌍 <b>{city}</b> uchun hafta prognozi:\n\n",
        "week_footer": "\nKuningiz xayrli o'tsin! 😉",
        "morning_msg": (
            "🌅 <b>Xayrli tong! {city} shahri uchun kunlik"
            " ma'lumot:</b>\n🌡 Harorat: {temp}℃  {weather}\n💡 {advice}\n\nYaxshi"
            " kun tilayman!"
        ),
        "alert_header": (
            "🚨 <b>Ob-havo keskin o'zgardi ({city})!</b>\n🌡 Hozir: {temp}℃\n"
        ),
        "alert_rain": (
            "☔ <b>Yomg'ir boshlandi! Soyabon olishni unutmang!</b>\n"
        ),
        "alert_cold": (
            "🥶 <b>Harorat birdan {diff}℃ ga tushib ketdi! Issiqroq"
            " kiyining.</b>"
        ),
        "adv_cold": (
            "🧥 Qalin kurtka, shapka va sharf kiying — ko'chada haqiqiy sovuq!"
        ),
        "adv_chilly": (
            "🧥 Issiqroq kurtka yoki palto kiying, oddiy koftada sovqotasiz."
        ),
        "adv_cool": (
            "🧥 Vetrovka yoki qalin tolstovka/sviter kiying, futbolka yetmaydi."
        ),
        "adv_mild": (
            "👕 Yengil kofta yoki ko'ylak yetarli, lekin kechga tomon"
            " salqinlashishi mumkin."
        ),
        "adv_warm": "👕 Futbolka yetarli, ko'chada bemalol issiq.",
        "adv_rain": "☔ Albatta soyabon oling!",
        "adv_snow": "🥾 Qor yog'yapti, sirpanmaydigan issiq poyabzal kiying.",
        "adv_sun": "🕶️ Quyoshli havo, quyoshdan saqlaydigan ko'zoynak oling.",
    },
    "ru": {
        "welcome": (
            "Метеостанция на связи! 🌤\nНапиши название города, чтобы узнать"
            " погоду.\n\nЯ также буду присылать утреннюю сводку в 08:00 и"
            " каждые 5 минут следить за резкими изменениями погоды!\n\nСменить"
            " язык: /lang"
        ),
        "stopped": (
            "Метеостанция закрыта на техобслуживание 🌡️\nОтправь /start, чтобы"
            " включить."
        ),
        "choose_type": (
            "Выбран город: <b>{city}</b>.\nКакой прогноз тебя интересует?"
        ),
        "btn_today": "☀️ На сегодня",
        "btn_week": "📅 На неделю",
        "city_too_long": (
            "❌ Слишком длинное название города. Попробуй короче."
        ),
        "not_found": (
            "❌ Город не найден. Проверь название и отправь заново."
        ),
        "not_found_alert": "Ошибка! Город не найден.",
        "unknown_weather": "Посмотри в окно! 🤔",
        "today_msg": (
            "🌍 Город: <b>{city}</b>\n🌡 Температура: <b>{temp}℃</b>"
            "  {weather}\n🥶 Ощущается: {feels_like}℃\n💧 Влажность:"
            " {humidity}%\n📊 Давление: {pressure} мм рт. ст.\n💨 Ветер: {wind}"
            " м/с\n\n💡 <b>Совет:</b> {advice}\n\nОтличного дня! 😉"
        ),
        "week_header": "🌍 Прогноз на неделю для <b>{city}</b>:\n\n",
        "week_footer": "\nОтличного дня! 😉",
        "morning_msg": (
            "🌅 <b>Доброе утро! Сводка для города {city}:</b>\n🌡 Температура:"
            " {temp}℃  {weather}\n💡 {advice}\n\nХорошего дня!"
        ),
        "alert_header": (
            "🚨 <b>Резкое изменение погоды ({city})!</b>\n🌡 Сейчас: {temp}℃\n"
        ),
        "alert_rain": "☔ <b>Начался дождь! Берите зонты!</b>\n",
        "alert_cold": (
            "🥶 <b>Похолодало на {diff}℃! Одевайтесь теплее.</b>"
        ),
        "adv_cold": (
            "🧥 Надевай пуховик, шапку и шарф — на улице дубак!"
        ),
        "adv_chilly": (
            "🧥 Нужна тёплая куртка или пальто, в одной кофте точно замёрзнешь."
        ),
        "adv_cool": (
            "🧥 Накинь ветровку или плотную толстовку/свитер, футболки уже мало."
        ),
        "adv_mild": (
            "👕 Подойдёт лёгкая кофта или рубашка, но к вечеру может"
            " похолодать."
        ),
        "adv_warm": "👕 Достаточно футболки, на улице тепло.",
        "adv_rain": "☔ Обязательно бери зонт!",
        "adv_snow": (
            "🥾 Идет снег, обувайся теплее и аккуратнее на дорогах."
        ),
        "adv_sun": "🕶️ Солнечно, захвати солнцезащитные очки.",
    },
}


def get_lang(chat_id):
  return user_languages.get(chat_id, "ru")


def get_clothing_advice(temp, weather_desc, lang):
  t = TEXTS[lang]
  advice = []
  if temp < 5:
    advice.append(t["adv_cold"])
  elif temp < 12:
    advice.append(t["adv_chilly"])
  elif temp < 18:
    advice.append(t["adv_cool"])
  elif temp < 24:
    advice.append(t["adv_mild"])
  else:
    advice.append(t["adv_warm"])

  if any(w in weather_desc for w in ["Rain", "Drizzle", "Thunderstorm"]):
    advice.append(t["adv_rain"])
  elif "Snow" in weather_desc:
    advice.append(t["adv_snow"])
  elif "Clear" in weather_desc and temp >= 24:
    advice.append(t["adv_sun"])
  return " ".join(advice)


def send_language_menu(chat_id):
  keyboard = types.InlineKeyboardMarkup()
  btn_uz = types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang:uz")
  btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")
  keyboard.add(btn_uz, btn_ru)
  bot.send_message(
      chat_id, "🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:", reply_markup=keyboard
  )


@bot.message_handler(commands=["start"])
def start_command(message):
  active_chats.add(message.chat.id)
  send_language_menu(message.chat.id)


@bot.message_handler(commands=["lang"])
def lang_command(message):
  active_chats.add(message.chat.id)
  send_language_menu(message.chat.id)


@bot.message_handler(commands=["stop"])
def stop_command(message):
  if message.chat.id in active_chats:
    active_chats.remove(message.chat.id)
  lang = get_lang(message.chat.id)
  bot.send_message(message.chat.id, TEXTS[lang]["stopped"])


@bot.message_handler(content_types=["text"])
def ask_weather_type(message):
  chat_id = message.chat.id
  if chat_id not in active_chats:
    return
  lang = get_lang(chat_id)
  t = TEXTS[lang]
  city = message.text.strip()
  if len(city.encode("utf-8")) > 55:
    bot.send_message(chat_id, t["city_too_long"])
    return
  user_cities[chat_id] = city
  keyboard = types.InlineKeyboardMarkup()
  btn_today = types.InlineKeyboardButton(
      t["btn_today"], callback_data=f"today:{city}"
  )
  btn_week = types.InlineKeyboardButton(
      t["btn_week"], callback_data=f"week:{city}"
  )
  keyboard.add(btn_today, btn_week)
  bot.send_message(
      chat_id,
      t["choose_type"].format(city=escape(city)),
      parse_mode="HTML",
      reply_markup=keyboard,
  )


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
  chat_id = call.message.chat.id
  try:
    action, value = call.data.split(":", 1)
    if action == "lang":
      lang = value if value in TEXTS else "ru"
      user_languages[chat_id] = lang
      active_chats.add(chat_id)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          TEXTS[lang]["welcome"],
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
      )
      return

    lang = get_lang(chat_id)
    t = TEXTS[lang]
    city = value

    if action == "today":
      r = requests.get(
          f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_api_key}&units=metric",
          timeout=10,
      )
      data = r.json()
      if data.get("cod") != 200:
        raise ValueError("City not found")
      city_name = escape(data["name"])
      cur_weather = round(data["main"]["temp"], 1)
      weather_desc = data["weather"][0]["main"]
      wd = WEATHER_NAMES[lang].get(weather_desc, t["unknown_weather"])
      feels_like = round(data["main"]["feels_like"], 1)
      humidity = data["main"]["humidity"]
      pressure = round(data["main"]["pressure"] * 0.75006)
      wind = data["wind"]["speed"]
      advice = get_clothing_advice(cur_weather, weather_desc, lang)
      answer = t["today_msg"].format(
          city=city_name,
          temp=cur_weather,
          weather=wd,
          feels_like=feels_like,
          humidity=humidity,
          pressure=pressure,
          wind=wind,
          advice=advice,
      )
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
      )
    elif action == "week":
      r = requests.get(
          f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={open_weather_api_key}&units=metric",
          timeout=10,
      )
      data = r.json()
      if str(data.get("cod")) != "200":
        raise ValueError("City not found")
      city_name = escape(data["city"]["name"])
      forecast_lines = [t["week_header"].format(city=city_name)]
      for item in data["list"]:
        if "12:00:00" in item["dt_txt"]:
          date = item["dt_txt"].split(" ")[0]
          temp = round(item["main"]["temp"], 1)
          weather_desc = item["weather"][0]["main"]
          wd = WEATHER_NAMES[lang].get(weather_desc, "🤔")
          forecast_lines.append(f"📅 <b>{date}</b>: <b>{temp}℃</b> {wd}")
      answer = "\n".join(forecast_lines) + t["week_footer"]
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
      )
  except Exception:
    lang = get_lang(chat_id)
    bot.answer_callback_query(call.id, TEXTS[lang]["not_found_alert"])
    bot.edit_message_text(
        TEXTS[lang]["not_found"],
        chat_id=chat_id,
        message_id=call.message.message_id,
    )


def morning_scheduler():
  while True:
    try:
      # Установлено время Узбекистана (UTC+5)
      now = datetime.now(timezone(timedelta(hours=5)))
      if now.hour == 8 and now.minute == 0:
        for chat_id in list(active_chats):
          city = user_cities.get(chat_id, "Namangan")
          lang = get_lang(chat_id)
          t = TEXTS[lang]
          r = requests.get(
              f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_api_key}&units=metric",
              timeout=10,
          )
          data = r.json()
          if data.get("cod") != 200:
            continue
          temp = round(data["main"]["temp"], 1)
          desc = data["weather"][0]["main"]
          wd = WEATHER_NAMES[lang].get(desc, "")
          advice = get_clothing_advice(temp, desc, lang)
          morning_text = t["morning_msg"].format(
              city=escape(data["name"]), temp=temp, weather=wd, advice=advice
          )
          bot.send_message(chat_id, morning_text, parse_mode="HTML")
        time.sleep(60)
    except Exception as e:
      print(f"Ошибка в утреннем планировщике: {e}")
    time.sleep(30)


def weather_monitor():
  while True:
    try:
      for chat_id in list(active_chats):
        city = user_cities.get(chat_id, "Namangan")
        lang = get_lang(chat_id)
        t = TEXTS[lang]
        r = requests.get(
            f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_api_key}&units=metric",
            timeout=10,
        )
        data = r.json()
        if data.get("cod") != 200:
          continue
        current_temp = round(data["main"]["temp"], 1)
        current_desc = data["weather"][0]["main"]
        last_data = weather_state.get(
            chat_id, {"temp": current_temp, "desc": current_desc}
        )
        is_raining_now = (
            "Rain" in current_desc or "Thunderstorm" in current_desc
        )
        was_raining_before = (
            "Rain" in last_data["desc"] or "Thunderstorm" in last_data["desc"]
        )
        temp_drop = (last_data["temp"] - current_temp) >= 4

        if (is_raining_now and not was_raining_before) or temp_drop:
          alert_text = t["alert_header"].format(
              city=escape(data["name"]), temp=current_temp
          )
          if is_raining_now and not was_raining_before:
            alert_text += t["alert_rain"]
          if temp_drop:
            alert_text += t["alert_cold"].format(
                diff=int(last_data["temp"] - current_temp)
            )
          bot.send_message(chat_id, alert_text, parse_mode="HTML")
        weather_state[chat_id] = {"temp": current_temp, "desc": current_desc}
    except Exception as e:
      print(f"Ошибка в мониторинге погоды: {e}")
    time.sleep(300)


if __name__ == "__main__":
  threading.Thread(target=morning_scheduler, daemon=True).start()
  threading.Thread(target=weather_monitor, daemon=True).start()
  print("Бот успешно запущен на Render со встроенным веб-сервером!")
  bot.infinity_polling(skip_pending=True)
