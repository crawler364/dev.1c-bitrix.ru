#!/usr/bin/env python3
"""
Bitrix Course Parser - Финальная рабочая версия
Парсер для скачивания курсов с сайта dev.1c-bitrix.ru
Основан на проверенном тестовом коде

Usage:
    python bitrix_parser_final.py [--limit N] [--output DIR]
    
Arguments:
    --limit N    : Ограничить количество скачиваемых страниц (по умолчанию: без ограничений)
    --output DIR : Директория для сохранения файлов (по умолчанию: ./course_data)
"""

import urllib.request
import urllib.parse
import html.parser
import os
import argparse
import time
import re
import json
from datetime import datetime

class SimpleHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.title = ""
        self.in_title = False
        
    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True
        elif tag == 'a':
            href = None
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    href = attr_value
            if href and ('lesson' in href.lower() or 'LESSON_ID' in href):
                self.links.append(href)
    
    def handle_data(self, data):
        if self.in_title:
            self.title += data.strip()
    
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

class TextExtractorParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_content = []
        self.in_script = False
        self.in_style = False
        
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            setattr(self, f'in_{tag}', True)
    
    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            text = data.strip()
            if text and len(text) > 1:
                self.text_content.append(text)
    
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            setattr(self, f'in_{tag}', False)
    
    def get_text_content(self):
        return '\n'.join(self.text_content)

def get_page_content(url):
    """Получение содержимого страницы"""
    try:
        print(f"Загружаем: {url}")
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
            }
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8', errors='ignore')
            
            parser = SimpleHTMLParser()
            parser.feed(content)
            
            return parser, content
            
    except Exception as e:
        print(f"Ошибка при загрузке {url}: {e}")
        return None, None

def sanitize_filename(filename):
    """Очистка имени файла"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip().strip('.')
    return filename[:200]

def save_page_content(url, parser, content, output_dir, page_info=None, page_num=1):
    """Сохранение содержимого страницы"""
    try:
        # Создаем имя файла
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        filename_parts = []
        if 'COURSE_ID' in query_params:
            filename_parts.append(f"course_{query_params['COURSE_ID'][0]}")
        if 'LESSON_ID' in query_params:
            filename_parts.append(f"lesson_{query_params['LESSON_ID'][0]}")
        elif 'CHAPTER_ID' in query_params:
            filename_parts.append(f"chapter_{query_params['CHAPTER_ID'][0]}")
        
        if not filename_parts:
            filename_parts.append(f"page_{page_num}")
        
        if page_info and page_info.get('title'):
            safe_title = sanitize_filename(page_info['title'])
            filename_parts.append(safe_title)
        
        base_filename = "_".join(filename_parts)
        
        # Сохраняем HTML
        html_filename = os.path.join(output_dir, f"{base_filename}.html")
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Сохраняем текстовое содержимое
        text_parser = TextExtractorParser()
        text_parser.feed(content)
        text_content = text_parser.get_text_content()
        
        if text_content:
            text_filename = os.path.join(output_dir, f"{base_filename}.txt")
            with open(text_filename, 'w', encoding='utf-8') as f:
                f.write(text_content)
        
        # Сохраняем метаданные
        metadata = {
            'url': url,
            'title': page_info.get('title', '') if page_info else '',
            'downloaded_at': datetime.now().isoformat(),
            'filename_base': base_filename
        }
        
        metadata_filename = os.path.join(output_dir, f"{base_filename}_metadata.json")
        with open(metadata_filename, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Сохранено: {base_filename}")
        return True
        
    except Exception as e:
        print(f"Ошибка при сохранении {url}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Парсер курсов Bitrix (Финальная версия)')
    parser.add_argument(
        '--url',
        default='https://dev.1c-bitrix.ru/learning/course/index.php?COURSE_ID=43&INDEX=Y',
        help='URL курса для парсинга'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Максимальное количество страниц для скачивания'
    )
    parser.add_argument(
        '--output',
        default='./course_data',
        help='Директория для сохранения файлов'
    )
    
    args = parser.parse_args()
    
    # Создаем директорию
    os.makedirs(args.output, exist_ok=True)
    
    print(f"Начинаем парсинг курса: {args.url}")
    print(f"Директория для сохранения: {args.output}")
    if args.limit:
        print(f"Ограничение страниц: {args.limit}")
    
    # Загружаем главную страницу
    main_parser, main_content = get_page_content(args.url)
    if not main_parser:
        print("Не удалось загрузить главную страницу")
        return
    
    print(f"Найдено ссылок на уроки: {len(main_parser.links)}")
    print(f"Заголовок курса: {main_parser.title}")
    
    if main_parser.links:
        print("\nПервые 5 ссылок:")
        for i, link in enumerate(main_parser.links[:5]):
            print(f"  {i+1}. {link}")
    
    # Создаем список уроков
    base_url = f"{urllib.parse.urlparse(args.url).scheme}://{urllib.parse.urlparse(args.url).netloc}"
    lessons = []
    
    for href in main_parser.links:
        if href:
            if href.startswith('/'):
                full_url = base_url + href
            elif href.startswith('http'):
                full_url = href
            else:
                full_url = urllib.parse.urljoin(args.url, href)
            
            # Генерируем название урока
            parsed_url = urllib.parse.urlparse(full_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            title_parts = []
            if 'LESSON_ID' in query_params:
                title_parts.append(f"Урок {query_params['LESSON_ID'][0]}")
            elif 'CHAPTER_ID' in query_params:
                title_parts.append(f"Глава {query_params['CHAPTER_ID'][0]}")
            else:
                title_parts.append("Урок")
            
            title = " ".join(title_parts)
            
            if full_url not in [l['url'] for l in lessons]:
                lessons.append({
                    'title': title,
                    'url': full_url
                })
    
    # Сохраняем информацию о курсе
    course_info = {
        'title': main_parser.title or 'Курс Bitrix',
        'url': args.url,
        'lessons_count': len(lessons),
        'lessons': lessons[:10],  # Первые 10 для просмотра
        'downloaded_at': datetime.now().isoformat()
    }
    
    with open(os.path.join(args.output, 'course_info.json'), 'w', encoding='utf-8') as f:
        json.dump(course_info, f, ensure_ascii=False, indent=2)
    
    # Сохраняем главную страницу
    save_page_content(args.url, main_parser, main_content, args.output, 
                     {'title': main_parser.title or 'course_index'}, 1)
    
    downloaded_pages = 1
    
    # Скачиваем уроки
    for i, lesson in enumerate(lessons):
        if args.limit and downloaded_pages >= args.limit:
            print(f"Достигнуто ограничение в {args.limit} страниц")
            break
        
        print(f"Обрабатываем урок {i+1}/{len(lessons)}: {lesson['title']}")
        
        time.sleep(1)  # Пауза между запросами
        
        lesson_parser, lesson_content = get_page_content(lesson['url'])
        if lesson_parser and lesson_content:
            success = save_page_content(lesson['url'], lesson_parser, lesson_content, 
                                      args.output, {'title': lesson['title']}, 
                                      downloaded_pages + 1)
            if success:
                downloaded_pages += 1
    
    print(f"\nПарсинг завершен!")
    print(f"Скачано страниц: {downloaded_pages}")
    print(f"Найдено уроков: {len(lessons)}")
    print(f"Файлы сохранены в: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
