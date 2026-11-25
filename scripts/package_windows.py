"""Package the tested standalone Windows console application."""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WIN=ROOT/'windows'
REPORTS=ROOT/'reports/windows'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zig-root',type=Path)
    args=parser.parse_args()
    if args.zig_root:
        (WIN/'ZIG-LICENSE.txt').write_bytes((args.zig_root/'LICENSE').read_bytes())
        (WIN/'MINGW-LICENSE.txt').write_bytes((args.zig_root/'lib/libc/mingw/COPYING').read_bytes())
        gdtoa=(args.zig_root/'lib/libc/mingw/gdtoa/gdtoa.c').read_text(encoding='utf-8')
        (WIN/'GDTOA-LICENSE.txt').write_text(gdtoa.split('*/',1)[0]+'*/\n',encoding='utf-8')
    (WIN/'LICENSE.TXT').write_bytes((ROOT/'LICENSE').read_bytes())
    (WIN/'THIRD_PARTY.txt').write_text(
        'Tiny-RU source and question wording: MIT; see LICENSE.TXT.\n'
        'The model contains original factual questions and Wikidata CC0 data.\n'
        'https://www.wikidata.org/wiki/Wikidata:Data_access\n\n'
        'This Windows binary is built with Zig 0.14.1 / Clang 19.1.7.\n'
        'Zig runtime: MIT; see ZIG-LICENSE.txt.\n'
        'Unmodified mingw-w64 runtime portions: see MINGW-LICENSE.txt.\n'
        'David M. Gay / Lucent gdtoa notice: GDTOA-LICENSE.txt.\n'
        'Runtime source: https://github.com/ziglang/zig/tree/0.14.1/lib/libc/mingw\n'
        'Zig runtime source: https://github.com/ziglang/zig/tree/0.14.1/lib/compiler_rt\n'
        'Windows system DLLs and the compiler itself are not redistributed.\n',encoding='utf-8')
    exe=(WIN/'TINYWIN.EXE').read_bytes()
    pe=struct.unpack_from('<I',exe,0x3c)[0]
    assert exe[:2]==b'MZ' and exe[pe:pe+4]==b'PE\0\0'
    assert struct.unpack_from('<H',exe,pe+4)[0]==0x8664
    assert (WIN/'TINY.BIN').read_bytes()==(ROOT/'dos/TINY.BIN').read_bytes()
    console=json.loads((REPORTS/'console.json').read_text(encoding='utf-8-sig'))
    assert console['ok'] and console['exit_code']==0
    measured=json.loads((REPORTS/'evaluation.json').read_text(encoding='utf-8-sig'))
    assert measured['total']==1200 and measured['weights_sha256']==digest(WIN/'TINY.BIN')
    checks=json.loads((REPORTS/'checks.json').read_text(encoding='utf-8-sig'))
    cmd_checks=json.loads((REPORTS/'cmd-checks.json').read_text(encoding='utf-8-sig'))
    assert all(cmd_checks.values())
    imports=re.findall(r'DLL Name:\s*(\S+)',(REPORTS/'pe-imports.txt').read_text())
    assert imports and all(name.lower()=='kernel32.dll' or name.lower().startswith('api-ms-win-crt-') for name in imports)
    environment=json.loads((REPORTS/'environment.json').read_text(encoding='utf-8-sig'))
    names=['TINYWIN.EXE','TINY.BIN','START.CMD','README.txt','LICENSE.TXT','THIRD_PARTY.txt',
           'MINGW-LICENSE.txt','ZIG-LICENSE.txt','GDTOA-LICENSE.txt']
    manifest=dict(platform='Windows 10/11 x64',version='2.1r3',compiler='Zig 0.14.1 / Clang 19.1.7',
                  files={n:dict(bytes=(WIN/n).stat().st_size,sha256=digest(WIN/n)) for n in names},
                  imports=imports,console_probe=console,metrics=measured['metrics'])
    archive=ROOT/'dist/tiny-ru-windows.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
        for name in names:
            info=zipfile.ZipInfo(name,date_time=(2026,11,25,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            output.writestr(info,(WIN/name).read_bytes())
    manifest['archive_bytes']=archive.stat().st_size
    (ROOT/'dist/windows-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    m=measured['metrics']
    report=f'''# Tiny-RU 2.1r3 для Windows x64

Собран настоящий PE32+ AMD64 console EXE. Он запускается напрямую из CMD
и двойным щелчком, без DOSBox и Python. Сборка предназначена для Windows 10/11 x64.
Проверено на {environment['caption']} ({environment['version']}, {environment['architecture']}).

Общее ядро нейросети — `dos/TINY.C`; Windows-адаптер — `windows/console.c`.
При консольном вводе используются ReadConsoleW/WriteConsoleW. При перенаправлении
поддерживаются UTF-8, UTF-8 BOM и явно выбранные CP866/CP1251; вывод в файл — UTF-8.
Кодовая страница пользовательской консоли не изменяется.
Веса открываются через Unicode-путь рядом с EXE, независимо от рабочей папки.

## Проверки

* Настоящий Windows-процесс: {measured['total']} вопросов.
* Знакомые факты: {m['russia_familiar']['correct']}/{m['russia_familiar']['total']}.
* Новые формулировки, выборка: {m['russia_unseen']['correct']}/{m['russia_unseen']['total']}.
* Настоящая отдельная скрытая Windows-консоль с кодовой страницей 1252:
  введён русский вопрос, на экране прочитан ответ «владимир путин», выход — 0.
* Потоковые проверки: {len(checks)} групп; подробности — `checks.json`.
* START.CMD проверен через настоящий cmd.exe. Отсутствующие веса вызывают
  понятную ошибку; случайный TINY.BIN из рабочей папки не используется.
* Русские буквы, CR/LF/CRLF, EOF, UTF-8 BOM, старые кодировки, переполнение
  и сохранение следующего вопроса, кириллица и пробелы в пути, повреждённые веса.
* Три теста старого нативного runtime пройдены. DOS EXE, пересобранный из
  общего исходника, побайтно совпал с прежним DOS EXE.

Прямой запуск и переносимость не изменяют знания и ограничения модели r3.
Полный отчёт об обучении и ошибках: `reports/REPORT.md`.

## Сборка и поставка

Загрузка компилятора проверена SHA-256:
`24aeeec8af16c381934a6cd7d95c807a8cb2cf7df9fa40d359aa884195c4716c`.
Команда: `TINY_ZIG=/path/to/zig sh scripts/build_windows.sh`.
Метаданные импортов: `pe-imports.txt`. EXE использует системные DLL Windows;
дополнительные DLL не поставляются. Уведомления runtime приложены в Windows ZIP.

EXE: {(WIN/'TINYWIN.EXE').stat().st_size} байт, SHA-256 `{digest(WIN/'TINYWIN.EXE')}`.
BIN: {(WIN/'TINY.BIN').stat().st_size} байт, SHA-256 `{digest(WIN/'TINY.BIN')}`.
BIN побайтно совпадает с DOS r3. Нейросеть вычисляет ответы локально.
Архив: `dist/tiny-ru-windows.zip`.
'''
    (REPORTS/'REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,metrics=m),indent=2))


if __name__=='__main__':main()
