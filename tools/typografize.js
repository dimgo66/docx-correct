/**
 * @file: typografize.js
 * @description: Автоматическая типографская обработка HTML — только ключевые теги, результат в указанный файл
 * @dependencies: typograf-7.4.4, jsdom
 * @created: 2024-06-08
 * @updated: 2024-07-05
 */

const fs = require('fs');
const path = require('path');
const Typograf = require(path.join(__dirname, '../typograf-7.4.4/dist/typograf.js'));
const { JSDOM } = require('jsdom');

const [,, INPUT = 'src/index.html', OUTPUT = 'reports/index.typograf.html'] = process.argv;

const tp = new Typograf({ locale: ['ru', 'en-US'] });

const KEY_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'blockquote'];
const KEY_CLASSES = ['informant-quote', 'folktext', 'poetry'];

const html = fs.readFileSync(INPUT, 'utf8');
const dom = new JSDOM(html);
const { document } = dom.window;

// Обработка тегов
KEY_TAGS.forEach(tag => {
    document.querySelectorAll(tag).forEach(el => {
        let processed = tp.execute(el.innerHTML);
        // Исправление дефиса на тире в начале строки/абзаца (диалоги)
        processed = processed.replace(/(^|[>\s])-(?=\S)/gm, '$1— ');
        el.innerHTML = processed;
        if (tag === 'p') {
            el.innerHTML = el.innerHTML.replace(/^/, '\t');
        }
    });
});
// Обработка по классам
KEY_CLASSES.forEach(cls => {
    document.querySelectorAll('.' + cls).forEach(el => {
        el.innerHTML = tp.execute(el.innerHTML);
    });
});

fs.writeFileSync(OUTPUT, dom.serialize(), 'utf8');
console.log(`Типографская обработка завершена. Результат: ${OUTPUT}`); 