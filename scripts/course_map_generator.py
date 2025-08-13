#!/usr/bin/env python3
"""
Генератор карты курсов для Bitrix Framework
Создает MD файл с картой всех курсов, найденных в директории data
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path


def extract_metadata_from_md(md_file_path):
    """
    Извлекает метаданные из MD файла курса
    
    Args:
        md_file_path: Путь к MD файлу
        
    Returns:
        dict: Словарь с метаданными (url, views, last_modified)
    """
    metadata = {}
    
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Извлекаем URL из раздела Метаданные
        url_match = re.search(r'- \*\*URL:\*\* (.+)', content)
        if url_match:
            metadata['url'] = url_match.group(1)
            
        # Извлекаем дату последнего изменения
        date_match = re.search(r'Дата последнего изменения: (\d{2}\.\d{2}\.\d{4})', content)
        if date_match:
            metadata['last_modified'] = date_match.group(1)
            
        # Извлекаем количество просмотров
        views_match = re.search(r'Просмотров: ([\d\s]+)', content)
        if views_match:
            views_str = views_match.group(1).replace(' ', '')
            metadata['views'] = int(views_str) if views_str.isdigit() else 0
            
        # Извлекаем основные разделы (заголовки уровня 5)
        sections = re.findall(r'^##### (.+)$', content, re.MULTILINE)
        if sections:
            metadata['sections'] = sections[:8]  # Ограничиваем до 8 основных разделов
            
    except Exception as e:
        print(f"Ошибка при обработке MD файла {md_file_path}: {e}")
        
    return metadata


def extract_title_from_md(md_file_path):
    """
    Извлекает заголовок урока из MD файла
    Ищет первый заголовок третьего уровня (###) в разделе "Содержимое"
    
    Args:
        md_file_path: Путь к MD файлу
        
    Returns:
        str: Заголовок урока или имя файла если заголовок не найден
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем раздел "## Содержимое"
        content_section_match = re.search(r'## Содержимое\s*\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if content_section_match:
            content_section = content_section_match.group(1)
            
            # Ищем первый заголовок третьего уровня в разделе содержимое
            title_match = re.search(r'^### (.+)$', content_section, re.MULTILINE)
            if title_match:
                return title_match.group(1).strip()
        
        # Если не найден заголовок в разделе содержимое, ищем любой заголовок третьего уровня
        title_match = re.search(r'^### (.+)$', content, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()
            
    except Exception as e:
        print(f"Ошибка при извлечении заголовка из {md_file_path}: {e}")
    
    # Возвращаем имя файла без расширения как fallback
    filename = os.path.basename(md_file_path)
    return filename.replace('.md', '')


def extract_course_id_from_path(course_dir):
    """
    Извлекает ID курса из пути к директории
    
    Args:
        course_dir: Путь к директории курса (например, "course_43")
        
    Returns:
        str: ID курса или None если не удалось извлечь
    """
    match = re.search(r'course_(\d+)', os.path.basename(course_dir))
    return match.group(1) if match else None


def scan_courses_directory(data_dir):
    """
    Сканирует директорию data и извлекает информацию о всех курсах
    
    Args:
        data_dir: Путь к директории data
        
    Returns:
        list: Список словарей с информацией о курсах
    """
    courses = []
    
    if not os.path.exists(data_dir):
        print(f"Директория {data_dir} не найдена")
        return courses
    
    # Перебираем все поддиректории в data
    for item in os.listdir(data_dir):
        course_path = os.path.join(data_dir, item)
        
        if os.path.isdir(course_path) and item.startswith('course_'):
            course_info = process_course_directory(course_path, item)
            if course_info:
                courses.append(course_info)
    
    # Сортируем курсы по ID
    courses.sort(key=lambda x: int(x.get('course_id', '0')))
    
    return courses


def process_course_directory(course_path, course_dirname):
    """
    Обрабатывает директорию одного курса
    
    Args:
        course_path: Путь к директории курса
        course_dirname: Имя директории курса
        
    Returns:
        dict: Информация о курсе
    """
    course_info = {
        'course_id': extract_course_id_from_path(course_dirname),
        'directory': course_dirname,
        'path': course_path
    }
    
    # Ищем course_info.json
    course_info_path = os.path.join(course_path, 'course_info.json')
    if os.path.exists(course_info_path):
        try:
            with open(course_info_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                course_info['title'] = json_data.get('title', 'Без названия')
                course_info['description'] = json_data.get('description', '')
                course_info['lessons_count'] = len(json_data.get('lessons', []))
                course_info['lessons'] = json_data.get('lessons', [])
        except Exception as e:
            print(f"Ошибка при чтении course_info.json в {course_path}: {e}")
            return None
    else:
        print(f"Файл course_info.json не найден в {course_path}")
        return None
    
    # Ищем главный MD файл курса
    main_md_file = None
    for file in os.listdir(course_path):
        if file.endswith('.md') and not ('lesson' in file.lower() or 'урок' in file.lower() or 'глава' in file.lower()):
            main_md_file = os.path.join(course_path, file)
            break
    
    if main_md_file:
        metadata = extract_metadata_from_md(main_md_file)
        course_info.update(metadata)
    
    # Подсчитываем количество MD файлов в директории
    md_files = [f for f in os.listdir(course_path) if f.endswith('.md')]
    course_info['md_files_count'] = len(md_files)
    
    return course_info


def generate_course_map(courses, output_file):
    """
    Генерирует файл карты курсов в формате Markdown
    Создает только блок со ссылками на офлайн файлы из папки data
    
    Args:
        courses: Список курсов
        output_file: Путь к выходному файлу
    """
    
    # Начинаем формирование содержимого
    content = []
    
    # Заголовок документа
    content.append("# Карта курсов Bitrix Framework")
    content.append("")
    content.append("Автоматически сгенерированная карта ссылок на офлайн файлы курсов.")
    content.append(f"**Дата генерации:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    content.append("")
    
    # Блок ссылок на файлы
    content.append("## 📂 Ссылки на файлы курсов")
    content.append("")
    
    # Для каждого курса находим все MD файлы и создаем ссылки
    for course in courses:
        course_directory = course.get('directory', '')
        course_path = course.get('path', '')
        
        if not course_path or not os.path.exists(course_path):
            continue
            
        # Получаем все MD файлы в директории курса
        try:
            md_files = [f for f in os.listdir(course_path) if f.endswith('.md')]
            md_files.sort()  # Сортируем файлы по алфавиту
            
            if md_files:
                course_title = course.get('title', 'Без названия')
                content.append(f"### {course_title}")
                content.append("")
                
                for md_file in md_files:
                    # Создаем относительную ссылку
                    relative_path = f"data/{course_directory}/{md_file}"
                    # Извлекаем заголовок из содержимого MD файла
                    md_file_path = os.path.join(course_path, md_file)
                    link_text = extract_title_from_md(md_file_path)
                    content.append(f"- [{link_text}]({relative_path})")
                
                content.append("")
                
        except Exception as e:
            print(f"Ошибка при обработке курса {course_directory}: {e}")
            continue
    
    # Footer
    content.append("---")
    content.append("")
    content.append("*Автоматически сгенерировано парсером курсов Bitrix Framework*")
    content.append(f"*Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}*")
    
    # Записываем файл
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        print(f"✅ Карта курсов сохранена в: {output_file}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении карты курсов: {e}")


def main():
    """
    Главная функция генератора карты курсов
    """
    # Определяем пути
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(current_dir, 'data')
    output_file = os.path.join(current_dir, 'COURSES_MAP.md')
    
    print("🔍 Сканирование директории курсов...")
    courses = scan_courses_directory(data_dir)
    
    if not courses:
        print("⚠️  Курсы не найдены в директории data")
        return
    
    print(f"📚 Найдено курсов: {len(courses)}")
    
    print("📝 Генерация карты курсов...")
    generate_course_map(courses, output_file)
    
    print("✅ Готово!")


if __name__ == "__main__":
    main()
