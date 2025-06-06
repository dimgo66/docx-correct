#!/usr/bin/env python3
"""
@file: add_spaces_to_paragraphs.py
@description: Добавляет 8 неразрывных пробелов (&nbsp;) в начало каждого <p>...</p> в HTML-файле.
@dependencies: Python 3, BeautifulSoup4
@created: 2024-07-05
"""
import sys
import argparse
from bs4 import BeautifulSoup

def add_spaces_to_paragraphs(input_path, output_path):
    """
    Читает HTML-файл, добавляет 8 &nbsp; в начало каждого тега <p> и сохраняет результат.
    """
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        for p_tag in soup.find_all('p'):
            # Создаем 8 неразрывных пробелов
            spaces = soup.new_string(u'\u00A0' * 8) # \u00A0 это &nbsp;
            
            # Вставляем пробелы в начало содержимого тега <p>
            if p_tag.string: # Если внутри тега только текст
                p_tag.string.insert_before(spaces)
            else: # Если внутри тега есть другие теги (например, <a>, <span>)
                # Вставляем пробелы перед первым дочерним элементом
                # или просто в начало, если дочерних элементов нет (пустой <p></p>)
                if p_tag.contents:
                    p_tag.contents[0].insert_before(spaces)
                else:
                    p_tag.append(spaces)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        
        # print(f"Successfully added spaces to paragraphs in '{input_path}' and saved to '{output_path}'")

    except FileNotFoundError:
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Добавляет 8 &nbsp; в начало каждого тега <p> в HTML-файле.')
    parser.add_argument('input_html', help='Путь к входному HTML файлу.')
    parser.add_argument('output_html', help='Путь для сохранения измененного HTML файла.')

    args = parser.parse_args()

    add_spaces_to_paragraphs(args.input_html, args.output_html) 