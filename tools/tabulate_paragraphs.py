#!/usr/bin/env python3
"""
@file: tabulate_paragraphs.py
@description: Добавляет символ табуляции в начало каждого <p>...</p> в HTML-файле
@dependencies: Python 3
@created: 2024-07-05
"""
import sys
import re

if len(sys.argv) != 3:
    print("Usage: python3 tabulate_paragraphs.py input.html output.html")
    sys.exit(1)

input_path = sys.argv[1]
output_path = sys.argv[2]

with open(input_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Добавляем табуляцию в начало каждого <p>...</p>
html = re.sub(r'(<p[^>]*>)([ \t\r\n]*)', r'\1\2\t', html)

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html) 