#!/usr/bin/env python3
"""
Bitrix Course Parser
Парсер для скачивания курсов с сайта dev.1c-bitrix.ru

Usage:
    python bitrix_course_parser.py [--limit N] [--output DIR]
    
Arguments:
    --limit N    : Ограничить количество скачиваемых страниц (по умолчанию: без ограничений)
    --output DIR : Директория для сохранения файлов (по умолчанию: ./course_data)
"""

import requests
import os
import argparse
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import json
from datetime import datetime


class BitrixCourseParser:
    def __init__(self, start_url, output_dir="./course_data", page_limit=None):
        """
        Инициализация парсера
        
        Args:
            start_url: Начальный URL для парсинга
            output_dir: Директория для сохранения данных
            page_limit: Максимальное количество страниц для скачивания
        """
        self.start_url = start_url
        self.output_dir = output_dir
        self.page_limit = page_limit
        self.session = requests.Session()
        self.downloaded_pages = 0
        self.visited_urls = set()
        
        # Настройка заголовков для имитации браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
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
            BeautifulSoup object или None в случае ошибки
        """
        try:
            print(f"Загружаем: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Пытаемся определить кодировку
            response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup, response.text
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке {url}: {e}")
            return None, None
        except Exception as e:
            print(f"Неожиданная ошибка при обработке {url}: {e}")
            return None, None
    
    def extract_course_info(self, soup):
        """
        Извлечение информации о курсе
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            dict с информацией о курсе
        """
        course_info = {
            'title': '',
            'description': '',
            'lessons': [],
            'metadata': {}
        }
        
        # Извлекаем заголовок курса
        title_selectors = [
            'h1',
            '.course-title',
            '.learning-course-title',
            'title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                course_info['title'] = title_elem.get_text().strip()
                break
        
        # Извлекаем описание
        desc_selectors = [
            '.course-description',
            '.learning-course-description',
            '.course-detail-text',
            'meta[name="description"]'
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                if desc_elem.name == 'meta':
                    course_info['description'] = desc_elem.get('content', '').strip()
                else:
                    course_info['description'] = desc_elem.get_text().strip()
                break
        
        # Извлекаем ссылки на уроки
        lesson_links = []
        
        # Различные селекторы для ссылок на уроки
        lesson_selectors = [
            'a[href*="lesson"]',
            'a[href*="LESSON_ID"]',
            '.learning-lesson-link',
            '.course-lesson a',
            'table a[href*="lesson"]'
        ]
        
        for selector in lesson_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(self.start_url, href)
                    lesson_text = link.get_text().strip()
                    if lesson_text and full_url not in [l['url'] for l in lesson_links]:
                        lesson_links.append({
                            'title': lesson_text,
                            'url': full_url
                        })
        
        course_info['lessons'] = lesson_links
        
        return course_info
    
    def save_page_content(self, url, soup, content, page_info=None):
        """
        Сохранение содержимого страницы в формате MD
        
        Args:
            url: URL страницы
            soup: BeautifulSoup object
            content: Сырое содержимое HTML
            page_info: Дополнительная информация о странице
        """
        try:
            # Создаем имя файла на основе URL
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
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
            md_content = self.extract_markdown_content(soup, url, page_info)
            
            # Сохраняем в формате MD
            md_filename = os.path.join(self.output_dir, f"{base_filename}.md")
            with open(md_filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            print(f"Сохранено в MD: {base_filename}")
            
        except Exception as e:
            print(f"Ошибка при сохранении страницы {url}: {e}")
    
    def extract_markdown_content(self, soup, url, page_info=None):
        """
        Извлечение содержимого в формате Markdown
        
        Args:
            soup: BeautifulSoup object
            url: URL страницы
            page_info: Информация о странице
            
        Returns:
            Содержимое в формате Markdown
        """
        # Создаем заголовок документа
        md_lines = []
        
        # Добавляем заголовок страницы
        title = page_info.get('title', 'Без названия') if page_info else 'Без названия'
        md_lines.append(f"# {title}")
        md_lines.append("")
        
        # Добавляем метаданные
        md_lines.append("## Метаданные")
        md_lines.append("")
        md_lines.append(f"- **URL:** {url}")
        md_lines.append(f"- **Дата скачивания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        
        # Удаляем ненужные элементы
        for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Извлекаем основное содержимое
        content_selectors = [
            '.courses-right-side',
            '.learning-lesson-content',
            '.course-content',
            '.lesson-text',
            'main',
            '.content',
            'body'
        ]
        
        main_content = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                main_content = content_elem
                break
        
        if not main_content:
            main_content = soup
        
        # Конвертируем HTML в Markdown
        md_lines.append("## Содержимое")
        md_lines.append("")
        
        # Обрабатываем заголовки
        for i, header in enumerate(main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
            level = int(header.name[1]) + 1  # Смещаем уровень на 1
            md_lines.append(f"{'#' * level} {header.get_text().strip()}")
            md_lines.append("")
        
        # Обрабатываем ссылки
        links_found = []
        for link in main_content.find_all('a', href=True):
            link_text = link.get_text().strip()
            link_url = link.get('href')
            if link_text and link_url and link_url.startswith('http'):
                links_found.append(f"- [{link_text}]({link_url})")
        
        if links_found:
            md_lines.append("### Ссылки")
            md_lines.append("")
            md_lines.extend(links_found)
            md_lines.append("")
        
        # Обрабатываем основной текст
        text_content = main_content.get_text()
        lines = text_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 1:
                # Проверяем, не является ли это заголовком (уже обработан)
                is_header = False
                for header in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    if line.strip() == header.get_text().strip():
                        is_header = True
                        break
                
                if not is_header:
                    cleaned_lines.append(line)
        
        if cleaned_lines:
            md_lines.append("### Основной текст")
            md_lines.append("")
            md_lines.extend(cleaned_lines)
        
        return '\n'.join(md_lines)
    
    def extract_text_content(self, soup):
        """
        Извлечение текстового содержимого из HTML (оставлено для совместимости)
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Очищенное текстовое содержимое
        """
        # Удаляем ненужные элементы
        for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Извлекаем основное содержимое
        content_selectors = [
            '.courses-right-side',
            '.learning-lesson-content',
            '.course-content',
            '.lesson-text',
            'main',
            '.content',
            'body'
        ]
        
        main_content = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                main_content = content_elem
                break
        
        if not main_content:
            main_content = soup
        
        # Извлекаем текст
        text = main_content.get_text()
        
        # Очищаем текст
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 1:  # Игнорируем пустые строки и одиночные символы
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def parse_course(self):
        """
        Основной метод парсинга курса
        """
        print(f"Начинаем парсинг курса: {self.start_url}")
        print(f"Директория для сохранения: {self.output_dir}")
        if self.page_limit:
            print(f"Ограничение страниц: {self.page_limit}")
        
        # Загружаем начальную страницу
        soup, content = self.get_page_content(self.start_url)
        if not soup:
            print("Не удалось загрузить начальную страницу")
            return
        
        # Извлекаем информацию о курсе
        course_info = self.extract_course_info(soup)
        print(f"Найден курс: {course_info['title']}")
        print(f"Количество уроков: {len(course_info['lessons'])}")
        
        # Сохраняем информацию о курсе
        course_info_file = os.path.join(self.output_dir, 'course_info.json')
        with open(course_info_file, 'w', encoding='utf-8') as f:
            json.dump(course_info, f, ensure_ascii=False, indent=2)
        
        # Сохраняем начальную страницу
        self.save_page_content(
            self.start_url, 
            soup, 
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
            time.sleep(1)
            
            lesson_soup, lesson_content = self.get_page_content(lesson['url'])
            if lesson_soup and lesson_content:
                self.save_page_content(
                    lesson['url'],
                    lesson_soup,
                    lesson_content,
                    {'title': lesson['title']}
                )
                self.downloaded_pages += 1
                self.visited_urls.add(lesson['url'])
        
        print(f"Парсинг завершен. Скачано страниц: {self.downloaded_pages}")
        print(f"Файлы сохранены в: {os.path.abspath(self.output_dir)}")


def main():
    parser = argparse.ArgumentParser(description='Парсер курсов Bitrix')
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
    
    # Создаем и запускаем парсер
    course_parser = BitrixCourseParser(
        start_url=args.url,
        output_dir=args.output,
        page_limit=args.limit
    )
    
    try:
        course_parser.parse_course()
    except KeyboardInterrupt:
        print("\nПарсинг прерван пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
