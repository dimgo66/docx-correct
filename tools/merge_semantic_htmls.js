/**
 * @file: merge_semantic_htmls.js
 * @description: Скрипт для объединения всех тематических секций из промежуточных HTML-файлов в итоговый pisk.semantic.full.html
 * @dependencies: Node.js (fs, path)
 * @created: 2024-07-05
 *
 * Запуск: node tools/merge_semantic_htmls.js
 */

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', 'reports');
const files = [
  'pisk.semantic.1000.html',
  'pisk.semantic.2000.html',
  'pisk.semantic.3000.html',
  'pisk.semantic.4000.html',
];
const fullFile = path.join(root, 'pisk.semantic.full.html');

function extractSections(html) {
  // Извлекает все <section>...</section> из HTML
  const sections = [];
  const regex = /<section[\s\S]*?<\/section>/gi;
  let match;
  while ((match = regex.exec(html))) {
    sections.push(match[0]);
  }
  return sections;
}

function mergeSections() {
  // Читаем шаблон итогового файла
  let full = fs.readFileSync(fullFile, 'utf8');

  // Для каждого файла ищем маркер и вставляем секции
  files.forEach((fname, idx) => {
    const marker = `[SECTION_${(idx + 1) * 1000}]`;
    const filePath = path.join(root, fname);
    if (!fs.existsSync(filePath)) return;
    const html = fs.readFileSync(filePath, 'utf8');
    const sections = extractSections(html).join('\n');
    full = full.replace(marker, sections + '\n');
  });

  // Удаляем неиспользованные маркеры
  full = full.replace(/\[SECTION_\d+\]/g, '');

  // Сохраняем итоговый файл
  fs.writeFileSync(fullFile, full, 'utf8');
  console.log('Объединение завершено. Итоговый файл:', fullFile);
}

mergeSections(); 