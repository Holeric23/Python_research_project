import re
import nltk
from nltk.corpus import stopwords
from typing import List

# Безопасная фоновая загрузка стоп-слов NLTK
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)

RU_STOPWORDS = set(stopwords.words("russian"))
EN_STOPWORDS = set(stopwords.words("english"))
ALL_STOPWORDS = RU_STOPWORDS.union(EN_STOPWORDS)

def clean_raw_text(text: str) -> str:
    """
    Выполняет глубокую очистку текста для технического поля 'text':
    - Удаляет веб-ссылки, Telegram-ссылки, телефоны и юзернеймы.
    - Переводит все знаки конца предложения (!, ?) в точки.
    - Удаляет всю пунктуацию, кроме букв, цифр и точек.
    - Фильтрует русские и английские стоп-слова.
    - Сохраняет одиночные точки (.) для предотвращения склеивания слов на границах предложений.
    """
    text_str = str(text).lower()

    # 1. Удаление веб-ссылок, ссылок на Telegram-каналы/сообщения и телефонных номеров
    text_str = re.sub(r"https?://\S+|www\.\S+", " ", text_str)
    text_str = re.sub(r"\bt\.me/\S+|@\S+", " ", text_str)
    text_str = re.sub(r"(\+?\d[\d\s\-\(\)]{7,}\d)", " ", text_str)

    # 2. Превращение знаков конца предложения в единую точку для сохранения границ
    text_str = re.sub(r"[!?\n\r\t]+", ". ", text_str)

    # 3. Удаление всех спецсимволов и пунктуации, кроме кириллицы, латиницы, цифр и точек
    text_str = re.sub(r"[^a-zа-яё0-9.\s]", " ", text_str)

    # 4. Пословная фильтрация стоп-слов с сохранением семантических точек
    raw_tokens = text_str.split()
    cleaned_tokens: List[str] = []

    for token in raw_tokens:
        # Обрабатываем токен, если он является самостоятельной точкой
        if token == ".":
            if not cleaned_tokens or cleaned_tokens[-1] != ".":
                cleaned_tokens.append(".")
            continue

        # Обрабатываем слова, которые заканчиваются на точку (конец предложения)
        if token.endswith("."):
            clean_word = token[:-1].strip()
            if clean_word and clean_word not in ALL_STOPWORDS and not clean_word.isdigit():
                cleaned_tokens.append(clean_word)
            if not cleaned_tokens or cleaned_tokens[-1] != ".":
                cleaned_tokens.append(".")
            continue

        # Обрабатываем стандартные слова
        if token not in ALL_STOPWORDS and not token.isdigit():
            cleaned_tokens.append(token)

    # Склеиваем слова обратно в текст
    result_text = " ".join(cleaned_tokens)
    
    # Лингвистическое форматирование: убираем пробел перед точкой ("слово ." -> "слово.")
    result_text = re.sub(r"\s+\.", ".", result_text)
    
    # Схлопываем множественные точки в одну ("слово..." -> "слово.")
    result_text = re.sub(r"\.+", ".", result_text)
    
    # Удаляем лишние пробелы
    result_text = re.sub(r"\s+", " ", result_text).strip()

    return result_text