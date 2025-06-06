"""
 * @file: convert_docx_to_html.py
 * @description: Скрипт для конвертации DOCX файлов в HTML с использованием Pandoc.
 * @dependencies: pandoc
 * @created: 2024-07-24
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

def create_directories(path):
    """Создает директорию, если она не существует."""
    os.makedirs(path, exist_ok=True)

def convert_docx_to_html(input_docx_path, output_dir_base):
    """
    Конвертирует DOCX файл в HTML с помощью Pandoc.

    Args:
        input_docx_path (str): Путь к входному DOCX файлу.
        output_dir_base (str): Базовая директория для сохранения HTML и медиафайлов (например, "reports").
                               Структура будет: output_dir_base/имя_файла_без_расширения/имя_файла.html
    """
    if not os.path.exists(input_docx_path):
        print(f"Ошибка: Входной файл не найден: {input_docx_path}")
        sys.exit(1)

    base_name = os.path.basename(input_docx_path)
    file_name_without_ext = os.path.splitext(base_name)[0]
    
    # Директория для конкретного сконвертированного документа
    # Например, reports/my_document/
    output_doc_specific_dir = os.path.join(output_dir_base, file_name_without_ext)
    
    output_html_path = os.path.join(output_doc_specific_dir, f"{file_name_without_ext}.html")
    media_output_dir = os.path.join(output_doc_specific_dir, "media") # Директория для медиа

    # Создаем необходимые директории
    create_directories(output_doc_specific_dir)
    # create_directories(media_output_dir) # Pandoc сам создаст папку media, если ее нет, но родительская должна быть

    pandoc_command = [
        "pandoc",
        input_docx_path,
        "-o", output_html_path,
        "--to", "html5",
        "--standalone",
        f"--extract-media={media_output_dir}", # Pandoc создаст эту папку, если не существует
        "--wrap=none",
        "--strip-comments"
    ]

    try:
        print(f"Конвертация файла: {input_docx_path}...")
        print(f"Команда: {' '.join(pandoc_command)}")
        
        # Запускаем Pandoc
        process = subprocess.run(pandoc_command, check=True, capture_output=True, text=True, encoding='utf-8')
        
        print(f"HTML сохранен в: {output_html_path}")
        print(f"Медиафайлы сохранены (или должны быть сохранены) в: {media_output_dir}")
        
        if process.stdout:
            print("Pandoc stdout:")
            print(process.stdout)
        # Pandoc часто выводит информационные сообщения в stderr, даже при успехе
        if process.stderr:
            print("Pandoc stderr:")
            print(process.stderr)
            
        print("Конвертация успешно завершена.")
        return output_html_path

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении Pandoc для файла {input_docx_path}:")
        print(f"Код возврата: {e.returncode}")
        print("Stdout:")
        print(e.stdout)
        print("Stderr:")
        print(e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Ошибка: команда 'pandoc' не найдена. Убедитесь, что Pandoc установлен и доступен в PATH.")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Конвертирует DOCX файл в HTML с использованием Pandoc.",
        formatter_class=argparse.RawTextHelpFormatter, # Для лучшего отображения help
        epilog="""Пример использования:
python3 tools/convert_docx_to_html.py src/pisk.docx --output_dir reports
"""
    )
    parser.add_argument("input_docx_path", help="Путь к входному DOCX файлу (например, src/my_document.docx).")
    parser.add_argument(
        "--output_dir", 
        default="reports", 
        help="Базовая директория для сохранения результатов (по умолчанию: reports)."
             " Результат будет в output_dir/имя_файла_без_расширения/имя_файла.html"
    )

    args = parser.parse_args()

    # Обновляем дату в заголовке файла при каждом запуске (если так задумано правилами)
    # Но лучше один раз при создании файла. Оставим как есть.
    # В FILE_HEADER дата уже захардкожена на момент создания этого сообщения.
    # Если нужно динамически обновлять дату в самом файле - это отдельная задача.

    # Выполняем конвертацию
    converted_html_path = convert_docx_to_html(args.input_docx_path, args.output_dir)
    if converted_html_path:
        print(f"\nСкрипт завершен. Итоговый HTML: {converted_html_path}") 