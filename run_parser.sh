#!/bin/bash

# Скрипт запуска парсера курсов Bitrix

# Настройки по умолчанию
DEFAULT_URL="https://dev.1c-bitrix.ru/learning/course/index.php?COURSE_ID=43&INDEX=Y"
DEFAULT_OUTPUT="./data"
DEFAULT_LIMIT=""
DEFAULT_TIMEOUT="0.5"

# Функция показа помощи
show_help() {
    echo "Использование: $0 [N] [OPTIONS]"
    echo ""
    echo "Позиционные аргументы:"
    echo "  N                    Ограничение количества страниц (по умолчанию: без ограничений)"
    echo ""
    echo "Опции:"
    echo "  -u, --url URL        URL курса для парсинга (по умолчанию: $DEFAULT_URL)"
    echo "  -o, --output DIR     Директория для сохранения (по умолчанию: $DEFAULT_OUTPUT)"
    echo "  -l, --limit N        Ограничение количества страниц"
    echo "  -t, --timeout SEC    Таймаут между скачиваниями в секундах (по умолчанию: $DEFAULT_TIMEOUT)"
    echo "  -h, --help           Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0                                    # Запуск без ограничений (скачать всё)"
    echo "  $0 5                                 # Ограничить скачивание 5 страницами"
    echo "  $0 10 -o ./my_data                   # Лимит 10 страниц, своя папка"
    echo "  $0 -l 5                              # Ограничить скачивание 5 страницами"
    echo "  $0 -t 2.0                            # Таймаут 2 секунды между скачиваниями"
    echo "  $0 -l 10 -t 1.5                      # Лимит 10 страниц с таймаутом 1.5 сек"
    echo "  $0 -u \"https://example.com\" -l 20     # Другой URL и лимит 20 страниц"
}

# Инициализация переменных
URL="$DEFAULT_URL"
OUTPUT="$DEFAULT_OUTPUT"
LIMIT="$DEFAULT_LIMIT"
TIMEOUT="$DEFAULT_TIMEOUT"

# Проверяем на позиционный аргумент (число)
if [[ $# -eq 1 && $1 =~ ^[0-9]+$ ]]; then
    LIMIT="$1"
    shift
fi

# Обработка аргументов командной строки
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            URL="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -l|--limit)
            LIMIT="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Неизвестная опция: $1"
            echo "Используйте -h или --help для справки"
            exit 1
            ;;
    esac
done

# Проверяем существование директории scripts
SCRIPT_DIR="./scripts"
PARSER_SCRIPT="$SCRIPT_DIR/bitrix_course_parser_standalone.py"

if [ ! -d "$SCRIPT_DIR" ]; then
    echo "Ошибка: Директория $SCRIPT_DIR не найдена!"
    exit 1
fi

if [ ! -f "$PARSER_SCRIPT" ]; then
    echo "Ошибка: Скрипт парсера $PARSER_SCRIPT не найден!"
    exit 1
fi

# Создаем выходную директорию если она не существует
mkdir -p "$OUTPUT"

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python 3 не найден. Установите Python 3 для продолжения."
    exit 1
fi

# Примечание: Используется standalone версия парсера, которая не требует внешних зависимостей
# Все необходимые модули входят в стандартную библиотеку Python

# Выводим информацию о запуске
echo "================================================="
echo "Запуск парсера курсов Bitrix"
echo "================================================="
echo "URL: $URL"
echo "Выходная директория: $OUTPUT"
if [ -z "$LIMIT" ]; then
    echo "Ограничение страниц: без ограничений"
else
    echo "Ограничение страниц: $LIMIT"
fi
echo "Таймаут между скачиваниями: $TIMEOUT сек"
echo "Дата запуска: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================="
echo ""

# Запускаем парсер
if [ -z "$LIMIT" ]; then
    python3 "$PARSER_SCRIPT" --url "$URL" --output "$OUTPUT" --timeout "$TIMEOUT"
else
    python3 "$PARSER_SCRIPT" --url "$URL" --output "$OUTPUT" --limit "$LIMIT" --timeout "$TIMEOUT"
fi

# Проверяем результат выполнения
if [ $? -eq 0 ]; then
    echo ""
    echo "================================================="
    echo "Парсинг завершен успешно!"
    echo "Результаты сохранены в: $(realpath "$OUTPUT")"
    echo "================================================="
else
    echo ""
    echo "================================================="
    echo "Ошибка при выполнении парсера!"
    echo "================================================="
    exit 1
fi
