/**
 * @file: typografize-md.js
 * @description: Автоматическая типографская обработка Markdown-файла (src/piskulin.md) через typograf, результат в src/piskulin.typograf.md
 * @dependencies: typograf-7.4.4, src/piskulin.md
 * @created: 2024-06-08
 */

const fs = require('fs');
const Typograf = require('./typograf-7.4.4/dist/typograf.js');

const INPUT = 'src/piskulin.md';
const OUTPUT = 'src/piskulin.typograf.md';

const tp = new Typograf({ locale: ['ru', 'en-US'] });

const text = fs.readFileSync(INPUT, 'utf8');
const result = tp.execute(text);

fs.writeFileSync(OUTPUT, result, 'utf8');
console.log(`Типографская обработка Markdown завершена. Результат: ${OUTPUT}`); 