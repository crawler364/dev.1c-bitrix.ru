#!/usr/bin/env python3
"""
Парсер курсов Bitrix (Автономная версия)
Парсер для скачивания курсов с сайта dev.1c-bitrix.ru
Версия без внешних зависимостей - использует только стандартные библиотеки Python

Использование:
    python bitrix_course_parser_standalone.py [--limit N] [--output DIR]
    
Аргументы:
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
import gzip
import html
from datetime import datetime

# Импорт функций генерации карты курсов
try:
    from course_map_generator import scan_courses_directory, generate_course_map
except ImportError:
    # Если модуль не найден, создаем заглушки
    def scan_courses_directory(data_dir):
        return []
    def generate_course_map(courses, output_file):
        pass


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
            # Улучшенное определение ссылок на уроки
            if href:
                # Проверяем ссылки связанные с уроками
                if ('lesson' in href.lower() or 
                    'LESSON_ID' in href or 
                    'CHAPTER_ID' in href or
                    ('/learning/course/' in href and ('LESSON_ID=' in href or 'CHAPTER_ID=' in href))):
                    # Пропускаем CSS и другие не относящиеся к контенту ссылки
                    if not href.endswith('.css') and not href.endswith('.js'):
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
            if text:
                self.text_content.append(text)
    
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            setattr(self, f'in_{tag}', False)
    
    def get_text_content(self):
        cleaned_lines = []
        for line in self.text_content:
            line = line.strip()
            if line and len(line) > 1:
                cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)


class MarkdownExtractorParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.content_parts = []
        self.headers = []
        self.text_content = []
        self.current_tag = None
        self.in_script = False
        self.in_style = False
        self.in_courses_right_side = False
        self.div_nesting_level = 0  # Отслеживаем глубину вложенности div
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        
        if tag in ['script', 'style']:
            setattr(self, f'in_{tag}', True)
        elif tag == 'div':
            # Проверяем наличие класса courses-right-side
            has_courses_right_side = False
            for attr_name, attr_value in attrs:
                if attr_name == 'class' and 'courses-right-side' in attr_value:
                    has_courses_right_side = True
                    break
            
            if has_courses_right_side:
                self.in_courses_right_side = True
                self.div_nesting_level = 1  # Начинаем отслеживать вложенность с уровня 1
            elif self.in_courses_right_side:
                # Мы внутри courses-right-side и нашли еще один div
                self.div_nesting_level += 1
        elif tag == 'a' and not self.in_script and not self.in_style:
            href = None
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    href = attr_value
            if href and href.startswith('http'):
                self.current_link_href = href
                self.current_link_text = ""
    
    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
            
        text = data.strip()
        if not text:
            return
            
        # Сохраняем только контент из courses-right-side блока
        if not self.in_courses_right_side:
            return
            
        if self.current_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(self.current_tag[1]) + 1  # Смещаем уровень на 1
            self.headers.append(f"{'#' * level} {text}")
        elif hasattr(self, 'current_link_href'):
            self.current_link_text += text
        else:
            self.text_content.append(text)
    
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            setattr(self, f'in_{tag}', False)
        elif tag == 'div' and self.in_courses_right_side:
            # Уменьшаем уровень вложенности при закрытии div внутри courses-right-side
            self.div_nesting_level -= 1
            # Выходим из courses-right-side только когда закрываем основной div (уровень 0)
            if self.div_nesting_level == 0:
                self.in_courses_right_side = False
        elif tag == 'a' and hasattr(self, 'current_link_href'):
            if self.current_link_text:
                # Добавляем только текст ссылки как жирный текст, без URL
                bold_text = f"**{self.current_link_text.strip()}**"
                self.text_content.append(bold_text)
            delattr(self, 'current_link_href')
            if hasattr(self, 'current_link_text'):
                delattr(self, 'current_link_text')
        
        self.current_tag = None
    
    def get_markdown_content(self, url, title="Без названия"):
        md_lines = []
        
        # Добавляем заголовок страницы
        md_lines.append(f"# {title}")
        md_lines.append("")
        
        # Добавляем метаданные
        md_lines.append("## Метаданные")
        md_lines.append("")
        md_lines.append(f"- **URL:** {url}")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        
        # Добавляем содержимое
        md_lines.append("## Содержимое")
        md_lines.append("")
        
        # Добавляем заголовки
        if self.headers:
            md_lines.extend(self.headers)
            md_lines.append("")
        
        # Добавляем основной текст
        if self.text_content:
            md_lines.append("### Основной текст")
            md_lines.append("")
            cleaned_lines = []
            for line in self.text_content:
                line = line.strip()
                if line and len(line) > 1:
                    # Избегаем дублирования заголовков
                    is_header = False
                    for header in self.headers:
                        if line in header:
                            is_header = True
                            break
                    if not is_header:
                        cleaned_lines.append(line)
            md_lines.extend(cleaned_lines)
        
        return '\n'.join(md_lines)
    
    def has_courses_right_side_content(self):
        """
        Проверяет, был ли найден и обработан контент из блока courses-right-side
        
        Returns:
            bool: True если найден контент из courses-right-side, False иначе
        """
        # Проверяем наличие заголовков или текстового контента
        return bool(self.headers or self.text_content)


class BitrixCourseParser:
    def __init__(self, start_url, output_dir="./course_data", page_limit=None, timeout=0.5):
        """
        Инициализация парсера
        
        Args:
            start_url: Начальный URL для парсинга
            output_dir: Директория для сохранения данных
            page_limit: Максимальное количество страниц для скачивания
            timeout: Таймаут между скачиваниями в секундах
        """
        self.start_url = start_url
        self.output_dir = output_dir
        self.page_limit = page_limit
        self.timeout = timeout
        self.downloaded_pages = 0
        self.visited_urls = set()
        
        # Создаем директорию для вывода
        os.makedirs(output_dir, exist_ok=True)
        
    def sanitize_filename(self, filename):
        """Очистка имени файла от недопустимых символов"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip().strip('.')
        return filename[:200]  # Ограничиваем длину имени файла
    
    def get_page_content(self, url):
        """
        Получение содержимого страницы
        
        Args:
            url: URL страницы
            
        Returns:
            (parser, content) или (None, None) в случае ошибки
        """
        try:
            print(f"Загружаем: {url}")
            
            # Создаем запрос с заголовками браузера
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                # Читаем необработанный контент
                raw_content = response.read()
            
                # Пытаемся распаковать если сжато gzip
                try:
                    if response.headers.get('Content-Encoding') == 'gzip':
                        content = gzip.decompress(raw_content).decode('utf-8', errors='ignore')
                    else:
                        # Пытаемся gzip в любом случае если заголовок отсутствует
                        try:
                            content = gzip.decompress(raw_content).decode('utf-8', errors='ignore')
                        except:
                            content = raw_content.decode('utf-8', errors='ignore')
                except Exception as e:
                    content = raw_content.decode('utf-8', errors='ignore')
            
                # Декодируем HTML сущности
                content = html.unescape(content)
            
                # Парсим HTML
                parser = SimpleHTMLParser()
                parser.feed(content)
            
                return parser, content
                
        except urllib.error.HTTPError as e:
            print(f"HTTP ошибка при загрузке {url}: {e.code} - {e.reason}")
            return None, None
        except urllib.error.URLError as e:
            print(f"Ошибка URL при загрузке {url}: {e.reason}")
            return None, None
        except Exception as e:
            print(f"Неожиданная ошибка при обработке {url}: {e}")
            return None, None
    
    def extract_course_info(self, parser):
        """
        Извлечение информации о курсе
        
        Args:
            parser: SimpleHTMLParser object
            
        Returns:
            dict с информацией о курсе
        """
        course_info = {
            'title': parser.title or 'Курс Bitrix',
            'description': '',
            'lessons': [],
            'metadata': {}
        }
        
        # Обрабатываем найденные ссылки
        print(f"Отладка: найдено {len(parser.links)} сырых ссылок")
        lesson_links = []
        base_url = f"{urllib.parse.urlparse(self.start_url).scheme}://{urllib.parse.urlparse(self.start_url).netloc}"
        
        for href in parser.links:
            if href:
                # Преобразуем относительные URL в абсолютные
                if href.startswith('/'):
                    full_url = base_url + href
                elif href.startswith('http'):
                    full_url = href
                else:
                    full_url = urllib.parse.urljoin(self.start_url, href)
                
                # Генерируем заголовок на основе параметров URL
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
                
                if full_url not in [l['url'] for l in lesson_links]:
                    lesson_links.append({
                        'title': title,
                        'url': full_url
                    })
        
        course_info['lessons'] = lesson_links
        return course_info
    
    def save_page_content(self, url, parser, content, page_info=None):
        """
        Сохранение содержимого страницы в формате MD
        
        Args:
            url: URL страницы
            parser: SimpleHTMLParser object
            content: Сырое содержимое HTML
            page_info: Дополнительная информация о странице
        """
        try:
            # Создаем имя файла на основе URL
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            filename_parts = []
            if 'COURSE_ID' in query_params:
                filename_parts.append(f"course_{query_params['COURSE_ID'][0]}")
            if 'LESSON_ID' in query_params:
                filename_parts.append(f"lesson_{query_params['LESSON_ID'][0]}")
            
            if not filename_parts:
                filename_parts.append(f"page_{self.downloaded_pages + 1}")
            
            if page_info and page_info.get('title'):
                safe_title = self.sanitize_filename(page_info['title'])
                filename_parts.append(safe_title)
            
            base_filename = "_".join(filename_parts)
            
            # Извлекаем содержимое в формате Markdown
            md_parser = MarkdownExtractorParser()
            md_parser.feed(content)
            
            # Проверяем, был ли найден блок courses-right-side с контентом
            if not md_parser.has_courses_right_side_content():
                print(f"Пропускаем сохранение страницы {url}: блок courses-right-side не найден или пуст")
                return
            
            title = page_info.get('title', parser.title) if page_info else parser.title
            if not title:
                title = "Без названия"
            
            md_content = md_parser.get_markdown_content(url, title)
            
            # Сохраняем в папку соответствующую названию курса
            if 'COURSE_ID' in query_params:
                course_id = query_params['COURSE_ID'][0]
                course_subdir = os.path.join(self.output_dir, f"course_{course_id}")
                os.makedirs(course_subdir, exist_ok=True)
                
                course_md_filename = os.path.join(course_subdir, f"{base_filename}.md")
                with open(course_md_filename, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            else:
                # Если ID курса не удалось определить, сохраняем в папку data/course
                course_subdir = os.path.join(self.output_dir, "course")
                os.makedirs(course_subdir, exist_ok=True)
                
                course_md_filename = os.path.join(course_subdir, f"{base_filename}.md")
                with open(course_md_filename, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            
            print(f"Сохранено в MD: {base_filename}")
            
        except Exception as e:
            print(f"Ошибка при сохранении страницы {url}: {e}")
    
    def parse_course(self):
        """
        Основной метод парсинга курса
        """
        print(f"Начинаем парсинг курса: {self.start_url}")
        print(f"Директория для сохранения: {self.output_dir}")
        if self.page_limit:
            print(f"Ограничение страниц: {self.page_limit}")
        
        # Загружаем начальную страницу
        parser, content = self.get_page_content(self.start_url)
        if not parser:
            print("Не удалось загрузить начальную страницу")
            return
        
        # Извлекаем информацию о курсе
        print(f"Отладка: найдено {len(parser.links)} сырых ссылок")
        if parser.links:
            print(f"Первые 5 ссылок: {parser.links[:5]}")
        
        course_info = self.extract_course_info(parser)
        print(f"Найден курс: {course_info['title']}")
        print(f"Количество уроков: {len(course_info['lessons'])}")
        
        # Сохраняем в папку соответствующую названию курса
        parsed_url = urllib.parse.urlparse(self.start_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'COURSE_ID' in query_params:
            course_id = query_params['COURSE_ID'][0]
            course_subdir = os.path.join(self.output_dir, f"course_{course_id}")
            os.makedirs(course_subdir, exist_ok=True)
            
            course_info_subfile = os.path.join(course_subdir, 'course_info.json')
            with open(course_info_subfile, 'w', encoding='utf-8') as f:
                json.dump(course_info, f, ensure_ascii=False, indent=2)
        else:
            # Если ID курса не удалось определить, сохраняем в папку data/course
            course_subdir = os.path.join(self.output_dir, "course")
            os.makedirs(course_subdir, exist_ok=True)
            
            course_info_subfile = os.path.join(course_subdir, 'course_info.json')
            with open(course_info_subfile, 'w', encoding='utf-8') as f:
                json.dump(course_info, f, ensure_ascii=False, indent=2)
        
        # Сохраняем начальную страницу
        self.save_page_content(
            self.start_url, 
            parser, 
            content, 
            {'title': course_info['title'] or 'course_index'}
        )
        self.downloaded_pages += 1
        self.visited_urls.add(self.start_url)
        
        # Обрабатываем уроки
        for i, lesson in enumerate(course_info['lessons']):
            if self.page_limit and self.downloaded_pages >= self.page_limit:
                print(f"Достигнуто ограничение в {self.page_limit} страниц")
                break
            
            if lesson['url'] in self.visited_urls:
                continue
            
            print(f"Обрабатываем урок {i+1}/{len(course_info['lessons'])}: {lesson['title']}")
            
            # Небольшая задержка между запросами
            time.sleep(self.timeout)
            
            lesson_parser, lesson_content = self.get_page_content(lesson['url'])
            if lesson_parser and lesson_content:
                self.save_page_content(
                    lesson['url'],
                    lesson_parser,
                    lesson_content,
                    {'title': lesson['title']}
                )
                self.downloaded_pages += 1
                self.visited_urls.add(lesson['url'])
        
        print(f"Парсинг завершен. Скачано страниц: {self.downloaded_pages}")
        print(f"Файлы сохранены в: {os.path.abspath(self.output_dir)}")
        
        # Генерируем карту курсов после завершения парсинга
        print("📝 Генерация карты курсов...")
        try:
            # Определяем корневую директорию проекта (на уровень выше output_dir)
            project_root = os.path.dirname(os.path.abspath(self.output_dir))
            data_dir = os.path.abspath(self.output_dir)
            output_file = os.path.join(project_root, 'COURSES_MAP.md')
            
            # Сканируем курсы и генерируем карту
            courses = scan_courses_directory(data_dir)
            if courses:
                generate_course_map(courses, output_file)
                print(f"✅ Карта курсов обновлена: {output_file}")
            else:
                print("⚠️  Курсы для карты не найдены")
        except Exception as e:
            print(f"❌ Ошибка при генерации карты курсов: {e}")


def main():
    parser = argparse.ArgumentParser(description='Парсер курсов Bitrix (Standalone версия)')
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
    parser.add_argument(
        '--timeout',
        type=float,
        default=0.5,
        help='Таймаут между скачиваниями в секундах (по умолчанию: 0.5)'
    )
    
    args = parser.parse_args()
    
    # Создаем и запускаем парсер
    course_parser = BitrixCourseParser(
        start_url=args.url,
        output_dir=args.output,
        page_limit=args.limit,
        timeout=args.timeout
    )
    
    try:
        course_parser.parse_course()
    except KeyboardInterrupt:
        print("\nПарсинг прерван пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
