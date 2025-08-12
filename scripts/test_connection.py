#!/usr/bin/env python3
"""
Тестовый скрипт для проверки доступности сайта и базовой структуры HTML
Использует только стандартные библиотеки Python
"""

import urllib.request
import urllib.parse
import html.parser
import re
import os
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
            text = ""
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

def test_site_connection(url):
    """
    Тестирование подключения к сайту без внешних зависимостей
    """
    print(f"Тестируем подключение к: {url}")
    
    try:
        # Создаем запрос с заголовками браузера
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
            }
        )
        
        # Выполняем запрос
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            content = response.read().decode('utf-8', errors='ignore')
            
            print(f"✓ Статус код: {status_code}")
            print(f"✓ Размер контента: {len(content)} символов")
            
            # Парсим HTML
            parser = SimpleHTMLParser()
            parser.feed(content)
            
            print(f"✓ Заголовок страницы: {parser.title}")
            print(f"✓ Найдено ссылок на уроки: {len(parser.links)}")
            
            # Выводим первые несколько ссылок для анализа
            if parser.links:
                print("\nПервые 5 найденных ссылок на уроки:")
                for i, link in enumerate(parser.links[:5]):
                    print(f"  {i+1}. {link}")
            else:
                print("\n❌ Не найдено ссылок на уроки!")
                print("\nПервые 1000 символов HTML для анализа:")
                print(content[:1000])
                print("...")
            
            # Создаем директорию для тестовых результатов
            test_dir = "./test_results"
            os.makedirs(test_dir, exist_ok=True)
            
            # Сохраняем результаты тестирования
            test_results = {
                'url': url,
                'status_code': status_code,
                'title': parser.title,
                'content_size': len(content),
                'lesson_links_found': len(parser.links),
                'lesson_links': parser.links[:10],  # Первые 10 ссылок
                'test_time': datetime.now().isoformat()
            }
            
            with open(os.path.join(test_dir, 'connection_test.json'), 'w', encoding='utf-8') as f:
                json.dump(test_results, f, ensure_ascii=False, indent=2)
            
            # Сохраняем HTML для анализа
            with open(os.path.join(test_dir, 'page_content.html'), 'w', encoding='utf-8') as f:
                f.write(content)
                
            print(f"\n✓ Результаты сохранены в: {os.path.abspath(test_dir)}")
            
            return True, test_results
            
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP ошибка: {e.code} - {e.reason}")
        return False, None
    except urllib.error.URLError as e:
        print(f"❌ Ошибка URL: {e.reason}")
        return False, None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False, None

def main():
    url = 'https://dev.1c-bitrix.ru/learning/course/index.php?COURSE_ID=43&INDEX=Y'
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К САЙТУ BITRIX")
    print("=" * 60)
    
    success, results = test_site_connection(url)
    
    if success:
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ: ✓ ПОДКЛЮЧЕНИЕ УСПЕШНО")
        print("=" * 60)
        if results['lesson_links_found'] > 0:
            print("✓ Парсинг ссылок на уроки работает")
            print("✓ Основной скрипт должен работать после установки зависимостей")
        else:
            print("⚠️  Ссылки на уроки не найдены - возможно изменилась структура сайта")
    else:
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ: ❌ ПРОБЛЕМЫ С ПОДКЛЮЧЕНИЕМ")
        print("=" * 60)
        print("Проверьте интернет-соединение и доступность сайта")

if __name__ == "__main__":
    main()
