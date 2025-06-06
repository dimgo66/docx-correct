"""
/**
 * @file: parse_languagetool_report.py
 * @description: Скрипт для парсинга JSON-отчета от LanguageTool и вывода информации об ошибках в читаемом формате.
 * @dependencies: Python 3
 * @created: 2024-07-26
 */
"""

import argparse
import json
import sys

def parse_report(json_file_path):
    """
    Парсит JSON-отчет LanguageTool и выводит информацию об ошибках.

    :param json_file_path: Путь к JSON-файлу отчета.
    :return: True, если парсинг прошел успешно, иначе False.
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: Файл отчета не найден: {json_file_path}", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON из файла {json_file_path}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Непредвиденная ошибка при чтении файла {json_file_path}: {e}", file=sys.stderr)
        return False

    if not report_data or 'matches' not in report_data:
        print("Отчет не содержит совпадений ('matches') или пуст.", file=sys.stderr)
        # Если файл software.name и software.version есть, но нет matches - это не ошибка файла, а просто нет ошибок
        if 'software' in report_data and report_data.get('software', {}).get('name') == 'LanguageTool':
            print(f"LanguageTool: {report_data.get('software', {}).get('version', 'N/A')}, язык: {report_data.get('language', {}).get('name', 'N/A')}")
            print("Ошибок не найдено.")
            return True
        return False
        
    print(f"Отчет LanguageTool для: {report_data.get('language', {}).get('name', 'N/A')} (Версия LanguageTool: {report_data.get('software', {}).get('version', 'N/A')})")
    print(f"Всего найдено потенциальных проблем: {len(report_data['matches'])}\n")

    for match in report_data['matches']:
        print("--------------------------------------------------")
        print(f"Сообщение: {match.get('message')}")
        print(f"Правило: {match.get('rule', {}).get('id', 'N/A')} ({match.get('rule', {}).get('description', 'N/A')})")
        
        context = match.get('context', {})
        context_text = context.get('text', '')
        offset = context.get('offset', 0)
        length = context.get('length', 0)
        
        # Выделяем ошибку в контексте, если это возможно
        if length > 0 and len(context_text) >= offset + length:
            highlighted_context = (
                context_text[:offset] + 
                "--->" + 
                context_text[offset:offset+length] + 
                "<---" + 
                context_text[offset+length:]
            )
            print(f"Контекст: {highlighted_context.strip()}")
        else:
            print(f"Контекст: {context_text.strip()}")
            
        print(f"   Местоположение: смещение {offset}, длина {length}")

        if match.get('replacements'):
            print("   Предлагаемые замены:")
            for i, replacement in enumerate(match['replacements']):
                print(f"     {i+1}. {replacement.get('value')}")
        else:
            print("   Предлагаемых замен нет.")
        print("--------------------------------------------------\n")
        
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Парсит JSON-отчет LanguageTool и выводит информацию об ошибках.")
    parser.add_argument("json_report_file", help="Путь к JSON-файлу отчета LanguageTool.")
    parser.add_argument("-o", "--output-file", help="(Опционально) Путь к файлу для сохранения отчета. Если не указан, вывод будет в консоль.", default=None)


    args = parser.parse_args()

    # Если указан файл для вывода, перенаправляем stdout
    original_stdout = sys.stdout
    output_file_handle = None
    if args.output_file:
        try:
            output_file_handle = open(args.output_file, 'w', encoding='utf-8')
            sys.stdout = output_file_handle
            print(f"Отчет будет сохранен в: {args.output_file}\n")
        except Exception as e:
            sys.stdout = original_stdout # Возвращаем stdout на место
            print(f"Ошибка при открытии файла для вывода {args.output_file}: {e}", file=sys.stderr)
            sys.exit(1)

    success = parse_report(args.json_report_file)

    # Возвращаем stdout, если он был перенаправлен, и закрываем файл
    if output_file_handle:
        sys.stdout = original_stdout
        output_file_handle.close()
        if success:
            print(f"Отчет успешно сохранен в: {args.output_file}")

    if not success:
        print("Парсинг отчета LanguageTool завершился с ошибками.", file=sys.stderr)
        sys.exit(1)
    else:
        if not args.output_file: # Если выводили в консоль
             print("Парсинг отчета LanguageTool завершен успешно.") 