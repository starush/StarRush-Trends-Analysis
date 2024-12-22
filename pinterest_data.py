#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time

BASE_URL = "https://www.pinterest.com"

def clean_main_topic_name(name: str) -> str:
    """Для главной темы берём часть строки до запятой."""
    return name.split(',')[0].strip()

def clean_subtopic_name(name: str) -> str:
    """Для подтемы убираем 'XXPins' (например, 'Brat summer95Pins' -> 'Brat summer')."""
    name = re.sub(r'\d+Pins', '', name)
    return name.strip()

def clean_topics_structure(topics_dict: dict) -> dict:
    cleaned = {}
    for key, value in topics_dict.items():
        main_topic = clean_main_topic_name(key)

        # Если value — не словарь или в нем нет "subtopics", пропустим/продолжим
        if not isinstance(value, dict):
            # Например, если внезапно встретили список, просто сохраняем как есть
            cleaned[main_topic] = {
                "pins": [],
                "subtopics": {}
            }
            continue

        subtopics_value = value.get("subtopics", {})
        # Если всё же subtopics_value оказалось списком, тоже пропустим
        if not isinstance(subtopics_value, dict):
            cleaned[main_topic] = {
                "pins": value.get("pins", []),
                "subtopics": {}
            }
            continue

        # Теперь subtopics_value точно словарь
        cleaned_subtopics = {}
        for subkey, subvalue in subtopics_value.items():
            cleaned_subtopic_key = clean_subtopic_name(subkey)
            cleaned_subtopics[cleaned_subtopic_key] = clean_topics_structure(subvalue)

        cleaned[main_topic] = {
            "pins": value.get("pins", []),
            "subtopics": cleaned_subtopics
        }
    return cleaned

def fetch_pin_details(soup: BeautifulSoup) -> list:
    """
    Извлекает массив пинов (title, alt-текст, и т.д.) с текущей страницы.
    Селекторы придётся корректировать под реальный HTML.
    """
    pins_data = []
    # Пример селектора для блоков пинов. Возможно, требуется уточнить для актуальной структуры
    pin_cards = soup.select('div[data-test-id="pinWrapper"]')
    
    for card in pin_cards:
        img_tag = card.select_one('img')
        if not img_tag:
            continue
        
        # Извлекаем URL изображения
        img_url = img_tag.get('src', '')
        # Извлекаем alt-текст
        alt_text = img_tag.get('alt', '')
        
        # Пример: возможные заголовки или описания
        title_tag = card.select_one('h3')
        description_tag = card.select_one('div[data-test-id="pinDescription"]')
        
        title_text = title_tag.get_text(strip=True) if title_tag else ''
        description_text = description_tag.get_text(strip=True) if description_tag else ''

        pins_data.append({
            "image_url": img_url,
            "alt_text": alt_text,
            "title": title_text,
            "description": description_text
        })
    return pins_data

def fetch_subtopics(url: str, depth: int = 0, max_depth: int = 2, visited=None) -> dict:
    """
    Рекурсивный сбор тем/подтем с Pinterest. Возвращает структуру:
    {
      "subtopics": { ... },
      "pins": [...]
    }
    """
    if visited is None:
        visited = set()
    visited.add(url)

    if depth > max_depth:
        return {"subtopics": {}, "pins": []}

    print(f"Сканируем: {url} (глубина={depth})")
    time.sleep(1)

    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Собираем пины текущей страницы
    pins = fetch_pin_details(soup)

    # Собираем подтемы
    subtopics = {}
    links = soup.select('a[href]')
    for link in links:
        href = link.get('href')
        if href and href.startswith('/trends/') and href != '/trends/':
            full_url = urljoin(BASE_URL, href)
            if full_url in visited:
                continue

            topic_name = link.get_text(strip=True)
            if not topic_name:
                topic_name = urlparse(href).path.strip('/').split('/')[-1]

            subtopics[topic_name] = fetch_subtopics(
                full_url,
                depth=depth + 1,
                max_depth=max_depth,
                visited=visited
            )

    return {
        "subtopics": subtopics,
        "pins": pins
    }

def fetch_pinterest_trends() -> list:
    """
    Основная точка входа: собираем иерархию тем/подтем + пины,
    затем достаём оттуда только названия подтем, чтобы выдавать список для Google Trends.
    """
    start_url = "https://www.pinterest.com/trends/"
    raw_hierarchy = fetch_subtopics(start_url, max_depth=2)
    
    # Уровень 0 (root) содержит subtopics и pins
    top_level_subtopics = raw_hierarchy.get("subtopics", {})
    top_level_pins = raw_hierarchy.get("pins", [])
    
    # Рекурсивно приводим к «чистым» именам
    cleaned_hierarchy = clean_topics_structure(top_level_subtopics)

    # Если хотим сохранить пины верхнего уровня - можно тоже добавить, 
    # но сейчас нам нужно только получить список подтем для Google Trends
    # Поэтому соберём в один список названия всех субтопиков 1-2 уровней.
    all_subtopics = []

    # Рекурсивная функция, которая собирает ключи (подтемы) из вложенной структуры
    def collect_subtopic_keys(node: dict):
        # node = {"pins": [...], "subtopics": {...}}
        for subtopic_name, subtopic_data in node.items():
            # subtopic_data = {"pins": [...], "subtopics": {...}}
            all_subtopics.append(subtopic_name)
            if "subtopics" in subtopic_data:
                collect_subtopic_keys(subtopic_data["subtopics"])

    collect_subtopic_keys(cleaned_hierarchy)
    
    # Вернём список уникальных подтем
    return list(set(all_subtopics))

if __name__ == "__main__":
    # Тестовый запуск
    pinterest_trends = fetch_pinterest_trends()
    print("\nСписок собранных подтем:")
    for trend in pinterest_trends:
        print("-", trend)