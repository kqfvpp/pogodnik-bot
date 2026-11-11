from datetime import datetime, timedelta, timezone
from html import escape
import http.server
import os
import socketserver
import threading
import time
import random
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
      print(
          f"[{datetime.now(timezone(timedelta(hours=5)))}]: Web server running on"
          f" port {PORT}"
      )
      httpd.serve_forever()
  except Exception as e:
    print(f"Web server error: {e}")


# Запускаем веб-сервер в фоновом потоке
threading.Thread(target=run_web_server, daemon=True).start()

# Создаем бота
bot = telebot.TeleBot("8247005293:AAE-T3d4J_7Thi1avj9PQt_HxXGyqM6mBb8")

# Хранение состояний и УМНЫЙ КЭШ
active_chats = set()
user_languages = {}
user_cities = {}
weather_state = {}
weather_cache = {}  # Кэш: хранит данные погоды 3 минуты

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
            "⚡ <b>ULTIMATE METEO-STATION ONLINE!</b> ⚡\nShahar nomini yozing"
            " va barcha 15 ta maxsus funksiyadan foydalaning!\n\nBuyruqlar:\n/lang"
            " - Tilni o'zgartirish\n/help - Yo'riqnoma"
        ),
        "help": (
            "🤖 <b>Ultimate Bot - Qo'llanma:</b>\n\n1️⃣ Shahar nomini yozing"
            " (masalan: <i>Namangan, Tashkent</i>).\n2️⃣ Tugmalar orqali"
            " <b>Bugun</b>, <b>Ertaga</b>, <b>Hafta</b>, <b>🔮 Bashorat</b>,"
            " <b>🌯 Shashlik/Shaurma</b> va boshqa epik funksiyalarni"
            " sinang!\n\n⚙️ /start - Qayta yuklash"
        ),
        "stopped": "Meteostansiya to'xtatildi 🌡️\n/start yuboring.",
        "choose_type": (
            "Tanlangan shahar: <b>{city}</b>.\nQaysi rejimni tanlaysiz?"
        ),
        "btn_today": "☀️ Bugun",
        "btn_tomorrow": "🌤 Ertaga",
        "btn_week": "📅 Hafta",
        "btn_fortune": "🔮 Bashorat",
        "btn_shaurma": "🌯 Shaurma/Kofe",
        "btn_drip": "🧥 Drip-Check",
        "btn_lazy": "🛋️ Lень-Index",
        "btn_back": "🔙 Orqaga",
        "city_too_long": "❌ Shahar nomi juda uzun.",
        "not_found": "❌ Shahar topilmadi.",
        "not_found_alert": "Xatolik!",
        "unknown_weather": "Noma'lum ob-havo 🤔",
        "today_msg": (
            "🌍 Shahar: <b>{city}</b>\n🌡 Harorat: <b>{temp}℃</b> {weather}\n🥶 His"
            " qilinishi: {feels_like}℃\n💧 Namlik: {humidity}%\n📊 Bosim:"
            " {pressure} mm\n💨 Shamol: {wind} m/s\n🌅 Chiqishi: {sunrise} |"
            " Botishi: {sunset}\n\n{radar}\n\n💡 <b>Maslahat:</b>"
            " {advice}\n\n{cyber}\nKuningiz xayrli o'tsin! 😉"
        ),
        "shaurma_msg": (
            "🌯 <b>Shahar: {city} | Shaurma & Kofe indeksi</b>\n\n🔥 Ob-havo"
            " sharoiti tufayli shaurma yeb, issiq kofe ichish ehtimoli:"
            " <b>{chance}%</b>!\n💬 <i>\"{text}\"</i>"
        ),
        "drip_msg": (
            "🧥 <b>Drip-Check (Uslub va Kiyinish):</b>\n\n⭐ Baho: <b>{score}</b>"
            " / 10\n💬 <i>\"{comment}\"</i>"
        ),
        "lazy_msg": (
            "🛋️ <b>Pablik-Lень Index:</b>\n\n💤 Bugun hech narsa qilmasdan"
            " o'ynash/uxlash ehtimoli: <b>{lazy}%</b>!\n💬 <i>\"{phrase}\"</i>"
        ),
        "fortune_msg": "🔮 <b>Meteo-folbinlik ({city}):</b>\n\n💬 <i>\"{fortune}\"</i>",
        "tomorrow_header": "🌍 <b>{city}</b> uchun ertangi prognoz:\n\n",
        "week_header": "🌍 <b>{city}</b> uchun hafta prognozi:\n\n",
        "week_footer": "\nKuningiz xayrli o'tsin! 😉",
        "morning_msg": (
            "🌅 <b>Xayrli tong! {city}:</b>\n🌡 Harorat: {temp}℃ {weather}\n💡"
            " {advice}\n\nKuningiz omadli kelsin!"
        ),
        "alert_header": "🚨 <b>Keskin o'zgarish ({city})!</b>\n🌡 Hozir: {temp}℃\n",
        "alert_rain": "☔ <b>Yomg'ir boshlandi! Soyabon oling!</b>\n",
        "alert_cold": "🥶 <b>Harorat {diff}℃ ga tushdi! Qalin kiyining.</b>",
    },
    "ru": {
        "welcome": (
            "⚡ <b>ULTIMATE METEO-STATION ONLINE!</b> ⚡\nОтправьте название"
            " города и активируйте все 15 убойных фич!\n\nКоманды:\n/lang -"
            " Сменить язык\n/help - Инструкция"
        ),
        "help": (
            "🤖 <b>Ultimate Бот - Справка:</b>\n\n1️⃣ Напишите город (например,"
            " <i>Namangan, Ташкент</i>).\n2️⃣ Используйте кнопки:"
            " <b>Сегодня</b>, <b>Завтра</b>, <b>Неделя</b>, <b>🔮 Прогноз</b>,"
            " <b>🌯 Шаурма-тест</b>, <b>🧥 Drip-Check</b> и <b>🛋️ Индекс"
            " лени</b>!\n\n⚙️ /start - Перезапуск"
        ),
        "stopped": "Метеостанция отключена 🌡️\nОтправь /start.",
        "choose_type": (
            "Выбран город: <b>{city}</b>.\nКакой режим активируем?"
        ),
        "btn_today": "☀️ Сегодня",
        "btn_tomorrow": "🌤 Завтра",
        "btn_week": "📅 Неделя",
        "btn_fortune": "🔮 Предсказание",
        "btn_shaurma": "🌯 Шаурма/Кофе",
        "btn_drip": "🧥 Drip-Check",
        "btn_lazy": "🛋️ Индекс лени",
        "btn_back": "🔙 Назад",
        "city_too_long": "❌ Слишком длинное название.",
        "not_found": "❌ Город не найден.",
        "not_found_alert": "Ошибка!",
        "unknown_weather": "Непонятно что за окном 🤔",
        "today_msg": (
            "🌍 Город: <b>{city}</b>\n🌡 Температура: <b>{temp}℃</b>"
            " {weather}\n🥶 Ощущается: {feels_like}℃\n💧 Влажность:"
            " {humidity}%\n📊 Давление: {pressure} мм\n💨 Ветер: {wind}"
            " м/с\n🌅 Восход: {sunrise} | Закат: {sunset}\n\n{radar}\n\n💡"
            " <b>Совет:</b> {advice}\n\n{cyber}\nОтличного дня! 😉"
        ),
        "shaurma_msg": (
            "🌯 <b>Город: {city} | Шаурма & Кофе Индекс</b>\n\n🔥 Шанс срочно"
            " отправиться за сочной шаурмой или горячим рафом составляет:"
            " <b>{chance}%</b>!\n💬 <i>\"{text}\"</i>"
        ),
        "drip_msg": (
            "🧥 <b>Drip-Check (Оценка стиля и тепла):</b>\n\n⭐ Стиль/Защита:"
            " <b>{score}</b> / 10\n💬 <i>\"{comment}\"</i>"
        ),
        "lazy_msg": (
            "🛋️ <b>Индекс Абсолютной Лени:</b>\n\n💤 Вероятность забить на все"
            " дела и проиграть в игры весь день: <b>{lazy}%</b>!\n💬"
            " <i>\"{phrase}\"</i>"
        ),
        "fortune_msg": "🔮 <b>Метео-пророчество ({city}):</b>\n\n💬 <i>\"{fortune}\"</i>",
        "tomorrow_header": "🌍 Прогноз на завтра для <b>{city}</b>:\n\n",
        "week_header": "🌍 Прогноз на неделю для <b>{city}</b>:\n\n",
        "week_footer": "\nОтличного дня! 😉",
        "morning_msg": (
            "🌅 <b>Доброе утро! {city}:</b>\n🌡 Температура: {temp}℃"
            " {weather}\n💡 {advice}\n\nПусть день пройдет мощно!"
        ),
        "alert_header": "🚨 <b>Резкий шторм ({city})!</b>\n🌡 Сейчас: {temp}℃\n",
        "alert_rain": "☔ <b>Начался ливень! Доставайте зонты!</b>\n",
        "alert_cold": "🥶 <b>Температура упала на {diff}℃! Утепляемся.</b>",
    },
}


def get_lang(chat_id):
  return user_languages.get(chat_id, "ru")


def get_clothing_advice(temp, weather_desc, lang):
  t = TEXTS[lang]
  advice = []
  if temp < 5:
    advice.append(t["adv_cold"] if "adv_cold" in t else "🧥 Дубак!")
  elif temp < 12:
    advice.append(
        t["adv_chilly"] if "adv_chilly" in t else "🧥 Нужна куртка."
    )
  elif temp < 18:
    advice.append(t["adv_cool"] if "adv_cool" in t else "🧥 Накинь ветровку.")
  elif temp < 24:
    advice.append(t["adv_mild"] if "adv_mild" in t else "👕 Легкая кофта.")
  else:
    advice.append(t["adv_warm"] if "adv_warm" in t else "👕 Футболка топ.")

  if any(w in weather_desc for w in ["Rain", "Drizzle", "Thunderstorm"]):
    advice.append("☔ Зонт обязателен!")
  elif "Snow" in weather_desc:
    advice.append("🥾 Снег, обувайся теплее.")
  elif "Clear" in weather_desc and temp >= 24:
    advice.append("🕶️ Солнечно, очки не помешают.")
  return " ".join(advice)


def get_radar_art(desc):
  if "Rain" in desc or "Drizzle" in desc:
    return "🌧️ [~ ~ ~ АНИМАЦИЯ ДОЖДЯ ~ ~ ~]"
  elif "Snow" in desc:
    return "❄️ [* . * . * СНЕГОПАД . * . *]"
  elif "Clear" in desc:
    return "☀️ [ \\ | / СОЛНЕЧНЫЙ РАДАР \\ | / ]"
  else:
    return "☁️ [ = = ОБЛАЧНЫЙ РАДАР = = ]"


def get_cyber_vibe(temp, desc):
  if temp < 0:
    return "❄️ *Режим выживания в пустошах активирован. Мороз кусает за щеки.*"
  elif "Rain" in desc:
    return "⚡ *Киберпанк-вайб: неоновые лужи отражают твое превосходство.*"
  elif temp > 25:
    return "🔥 *Пустынный зной: гидратация превыше всего, путник.*"
  else:
    return "🌐 *Системы в норме. Идеальный баланс стихий.*"


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
  lang = get_lang(message.chat.id)
  bot.send_message(message.chat.id, TEXTS[lang]["welcome"], parse_mode="HTML")
  send_language_menu(message.chat.id)


@bot.message_handler(commands=["lang"])
def lang_command(message):
  active_chats.add(message.chat.id)
  send_language_menu(message.chat.id)


@bot.message_handler(commands=["help"])
def help_command(message):
  lang = get_lang(message.chat.id)
  bot.send_message(message.chat.id, TEXTS[lang]["help"], parse_mode="HTML")


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

  print(
      f"[{datetime.now(timezone(timedelta(hours=5)))}] Пользователь {chat_id}"
      f" запросил город: {city}"
  )

  keyboard = types.InlineKeyboardMarkup(row_width=2)
  btn_today = types.InlineKeyboardButton(
      t["btn_today"], callback_data=f"today:{city}"
  )
  btn_tomorrow = types.InlineKeyboardButton(
      t["btn_tomorrow"], callback_data=f"tomorrow:{city}"
  )
  btn_week = types.InlineKeyboardButton(
      t["btn_week"], callback_data=f"week:{city}"
  )
  btn_fortune = types.InlineKeyboardButton(
      t["btn_fortune"], callback_data=f"fortune:{city}"
  )
  btn_shaurma = types.InlineKeyboardButton(
      t["btn_shaurma"], callback_data=f"shaurma:{city}"
  )
  btn_drip = types.InlineKeyboardButton(
      t["btn_drip"], callback_data=f"drip:{city}"
  )
  btn_lazy = types.InlineKeyboardButton(
      t["btn_lazy"], callback_data=f"lazy:{city}"
  )
  keyboard.add(
      btn_today,
      btn_tomorrow,
      btn_week,
      btn_fortune,
      btn_shaurma,
      btn_drip,
      btn_lazy,
  )

  bot.send_message(
      chat_id,
      t["choose_type"].format(city=escape(city)),
      parse_mode="HTML",
      reply_markup=keyboard,
  )


def make_menu_keyboard(lang, city):
  t = TEXTS[lang]
  keyboard = types.InlineKeyboardMarkup(row_width=2)
  btn_today = types.InlineKeyboardButton(
      t["btn_today"], callback_data=f"today:{city}"
  )
  btn_tomorrow = types.InlineKeyboardButton(
      t["btn_tomorrow"], callback_data=f"tomorrow:{city}"
  )
  btn_week = types.InlineKeyboardButton(
      t["btn_week"], callback_data=f"week:{city}"
  )
  btn_fortune = types.InlineKeyboardButton(
      t["btn_fortune"], callback_data=f"fortune:{city}"
  )
  btn_shaurma = types.InlineKeyboardButton(
      t["btn_shaurma"], callback_data=f"shaurma:{city}"
  )
  btn_drip = types.InlineKeyboardButton(
      t["btn_drip"], callback_data=f"drip:{city}"
  )
  btn_lazy = types.InlineKeyboardButton(
      t["btn_lazy"], callback_data=f"lazy:{city}"
  )
  keyboard.add(
      btn_today,
      btn_tomorrow,
      btn_week,
      btn_fortune,
      btn_shaurma,
      btn_drip,
      btn_lazy,
  )
  return keyboard


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

    if action == "back":
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          t["choose_type"].format(city=escape(city)),
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=make_menu_keyboard(lang, city),
      )
      return

    # УМНЫЙ КЭШ НА 3 МИНУТЫ
    cache_key = f"{city}:{action}"
    current_time = time.time()
    if cache_key in weather_cache:
      cached_data, cached_time = weather_cache[cache_key]
      if current_time - cached_time < 180:
        data = cached_data
      else:
        data = None
    else:
      data = None

    if data is None:
      API_URL = (
          f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={open_weather_api_key}&units=metric"
          if action in ["tomorrow", "week"]
          else f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_api_key}&units=metric"
      )
      try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()
        weather_cache[cache_key] = (data, current_time)
      except Exception:
        bot.answer_callback_query(
            call.id, "Internet xatosi / Ошибка сети", show_alert=True
        )
        return

    if str(data.get("cod")) not in ["200", 200]:
      raise ValueError("City not found")

    if action == "today":
      city_name = escape(data["name"])
      cur_weather = round(data["main"]["temp"], 1)
      weather_desc = data["weather"][0]["main"]
      wd = WEATHER_NAMES[lang].get(weather_desc, t["unknown_weather"])
      feels_like = round(data["main"]["feels_like"], 1)
      humidity = data["main"]["humidity"]
      pressure = round(data["main"]["pressure"] * 0.75006)
      wind = data["wind"]["speed"]

      city_tz = data.get("timezone", 0)
      sunrise_ts = data["sys"]["sunrise"] + city_tz
      sunset_ts = data["sys"]["sunset"] + city_tz
      sunrise = datetime.fromtimestamp(sunrise_ts, timezone.utc).strftime(
          "%H:%M"
      )
      sunset = datetime.fromtimestamp(sunset_ts, timezone.utc).strftime("%H:%M")

      advice = get_clothing_advice(cur_weather, weather_desc, lang)
      radar = get_radar_art(weather_desc)
      cyber = get_cyber_vibe(cur_weather, weather_desc)

      answer = t["today_msg"].format(
          city=city_name,
          temp=cur_weather,
          weather=wd,
          feels_like=feels_like,
          humidity=humidity,
          pressure=pressure,
          wind=wind,
          sunrise=sunrise,
          sunset=sunset,
          radar=radar,
          advice=advice,
          cyber=cyber,
      )

      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)

      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
      )

    elif action == "shaurma":
      city_name = escape(data.get("name", city))
      temp = data["main"]["temp"]
      chance = min(99, max(15, int(80 - temp * 2 if temp > 0 else 95)))
      phrases = [
          "Идеальный погодный тайминг для калорийного взрыва.",
          "Шаурмичная манит сильнее, чем любые дедлайны.",
          "Кофе в руке, шаурма в пакете — залог победы над климатом.",
      ]
      answer = t["shaurma_msg"].format(
          city=city_name, chance=chance, text=random.choice(phrases)
      )
      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
      )

    elif action == "drip":
      temp = data["main"]["temp"]
      score = max(1, min(10, int(10 - abs(temp - 20) / 4)))
      comments = [
          "Максимальный стиль, но можно отморозить всё на свете.",
          "Баланс между комфортом и уличным луком найден.",
          "Одевайся как капуста, иначе выживание под вопросом.",
      ]
      answer = t["drip_msg"].format(score=score, comment=random.choice(comments))
      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
      )

    elif action == "lazy":
      temp = data["main"]["temp"]
      lazy_val = 99 if temp < 5 or temp > 30 else 65
      phrases = [
          "Вселенная официально разрешает лежать под пледом.",
          "Работа подождет, пока погода шепчет спать.",
          "Энергия на нуле, включай фоновый режим лени.",
      ]
      answer = t["lazy_msg"].format(
          lazy=lazy_val, phrase=random.choice(phrases)
      )
      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
      )

    elif action == "tomorrow":
      city_name = escape(data["city"]["name"])
      now_local = datetime.now(timezone(timedelta(hours=5)))
      tomorrow_date = (now_local + timedelta(days=1)).strftime("%Y-%m-%d")

      forecast_lines = [t["tomorrow_header"].format(city=city_name)]
      found_any = False
      for item in data["list"]:
        if tomorrow_date in item["dt_txt"]:
          found_any = True
          time_str = item["dt_txt"].split(" ")[1][:5]
          temp = round(item["main"]["temp"], 1)
          weather_desc = item["weather"][0]["main"]
          wd = WEATHER_NAMES[lang].get(weather_desc, "🤔")
          forecast_lines.append(f"🕒 <b>{time_str}</b>: <b>{temp}℃</b> {wd}")

      if not found_any:
        for item in data["list"][:4]:
          dt_txt = item["dt_txt"]
          temp = round(item["main"]["temp"], 1)
          weather_desc = item["weather"][0]["main"]
          wd = WEATHER_NAMES[lang].get(weather_desc, "🤔")
          forecast_lines.append(f"📅 <b>{dt_txt}</b>: <b>{temp}℃</b> {wd}")

      answer = "\n".join(forecast_lines) + t["week_footer"]
      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
      )

    elif action == "week":
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
      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
      )

    elif action == "fortune":
      city_name = escape(data.get("name", city))
      fortunes_list = [
          "Звезды шепчут: в такую погоду идеальное преступление — остаться дома.",
          "Туман скрывает лишние заботы. Расслабься и кайфуй.",
          "Солнце светит ярко — отличный знак, чтобы порадовать себя вкусняшкой.",
          "Внезапный порыв ветра унесет все проблемы.",
      ]
      answer = t["fortune_msg"].format(
          city=city_name, fortune=random.choice(fortunes_list)
      )
      keyboard = types.InlineKeyboardMarkup()
      btn_back = types.InlineKeyboardButton(
          t["btn_back"], callback_data=f"back:{city}"
      )
      keyboard.add(btn_back)
      bot.answer_callback_query(call.id)
      bot.edit_message_text(
          answer,
          chat_id=chat_id,
          message_id=call.message.message_id,
          parse_mode="HTML",
          reply_markup=keyboard,
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
  last_sent_day = None
  while True:
    try:
      now = datetime.now(timezone(timedelta(hours=5)))
      if now.hour == 8 and now.minute == 0:
        current_day = now.date()
        if last_sent_day != current_day:
          last_sent_day = current_day
          for chat_id in list(active_chats):
            city = user_cities.get(chat_id, "Namangan")
            lang = get_lang(chat_id)
            t = TEXTS[lang]
            try:
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
            except Exception:
              pass
          print(f"[{now}]: Утренняя рассылка улетела всем пользователям!")
        time.sleep(40)
    except Exception as e:
      print(f"Ошибка в утреннем планировщике: {e}")
    time.sleep(15)


def weather_monitor():
  while True:
    try:
      for chat_id in list(active_chats):
        city = user_cities.get(chat_id, "Namangan")
        lang = get_lang(chat_id)
        t = TEXTS[lang]
        try:
          r = requests.get(
              f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={open_weather_api_key}&units=metric",
              timeout=10,
          )
          data = r.json()
        except Exception:
          continue

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

  while True:
    try:
      bot.infinity_polling(
          skip_pending=True, timeout=60, long_polling_timeout=60
      )
    except Exception as e:
      print(f"Ошибка polling: {e}, перезапуск через 5 секунд...")
      time.sleep(5)
