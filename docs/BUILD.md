# Сборка и проверки

Все команды выполняются из корня репозитория. Для запуска готовых Windows
и DOS-программ среда Python и компиляторы не нужны.

## Python для разработки

Исходные измерения выполнены с Python 3.8.5, PyTorch 2.4.1+cpu и NumPy 1.24.4.
Для нового окружения используйте совместимый Python 3.8–3.11. Пример Linux/WSL:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1
python3 -m pip install -r requirements.txt
```

Для построения графиков дополнительно:

```sh
python3 -m pip install -r requirements-report.txt
```

## Нативный Linux runtime

Нужен GCC. Команды:

```sh
sh scripts/build_native.sh
python3 -m unittest discover -s tests -v
python3 scripts/utf8_console.py build/tiny-native
```

C-ядро Linux принимает CP866; мост `utf8_console.py` преобразует обычный UTF-8
терминала. Он запускает отдельный процесс на вопрос. Windows-адаптер, напротив,
сам обрабатывает Unicode и загружает веса один раз на сеанс.

Пример оценки C на финальном контроле:

```sh
python3 scripts/evaluate_c.py --executable build/tiny-native --questions data/russia-final/control.jsonl --transcript reports/russia/native-output.cp866.txt --out reports/russia/native.json
```

Команда обновляет соответствующие файлы измерений.

## Windows 10/11 x64

### Сборка из Linux/WSL

С установленным MinGW-w64:

```sh
sh scripts/build_windows.sh
```

Компилятор по умолчанию — `x86_64-w64-mingw32-gcc`. Его путь можно задать
через `TINY_WINDOWS_CC`. Для воспроизведения поставляемой сборки использован Zig 0.14.1:

```sh
export TINY_ZIG=/path/to/zig
sh scripts/build_windows.sh
```

Получатся `windows/TINYWIN.EXE` и копия `dos/TINY.BIN` в `windows/`.
Ветка Windows использует то же нейросетевое ядро, подключая `windows/console.c`.
Интерфейс — консольный, EXE — PE32+ AMD64. Скомпонованные runtime и их
уведомления перечислены в `windows/THIRD_PARTY.txt`.

### Проверка на Windows

В PowerShell:

```powershell
./scripts/test_windows.ps1
```

Тест запускает настоящий EXE на 1200 вопросах. Также проверяются UTF-8 BOM,
CP866/CP1251, окончания строк, длинные строки, повреждённые веса и путь с кириллицей.
Он создаёт временные файлы в `build/` и обновляет `reports/windows/`.

Для отдельного теста настоящей Unicode-консоли сначала соберите помощник в WSL:

```sh
mkdir -p build
"$TINY_ZIG" cc -target x86_64-windows-gnu -std=c99 -O2 -municode tests/windows_console_probe.c -o build/windows-console-probe.exe
```

Затем в PowerShell:

```powershell
./scripts/test_windows_console.ps1
```

Помощник создаёт свою скрытую консоль, устанавливает в ней кодовую страницу
1252, вводит русский вопрос и проверяет русский ответ. Существующие пользовательские
консоли не перенастраиваются. При обычном запуске используются `ReadConsoleW`
и `WriteConsoleW`, а при перенаправлении — UTF-8-потоки.

## DOS

### Поставляемый путь: Open Watcom

Нужен установленный Open Watcom v2 с инструментами Linux и библиотеками DOS.
Укажите корень установки:

```sh
export WATCOM=/path/to/watcom
sh scripts/build_watcom.sh
```

Параметры сборки: `-bt=dos -ml -3 -fpi87 -os`, 16-битный DOS Large, 386/387.
Источник русского словаря — `training/vocab.json`; заголовки
`dos/VOCAB.H` и `dos/RUSTR.H` генерируются скриптами:

```sh
python3 training/tokenizer.py
python3 scripts/generate_strings.py
```

Для экспериментальной сборки в другую папку:

```sh
TINY_DOS_OUTPUT_DIR=../build/dos-candidate sh scripts/build_watcom.sh
```

Путь `TINY_DOS_OUTPUT_DIR` отсчитывается от `dos/`, куда переходит скрипт.
Тексты исходника и заголовков ASCII; русские строковые константы представлены
CP866-байтами в escape-последовательностях.

### Turbo C

`dos/BUILD.BAT` содержит вариант Turbo C 2.0 Large. Нужны собственная установка
и настройка пути `TC`. Этот вариант и полноэкранный интерфейс ветки Turbo C
в текущем выпуске не проверялись. Готовый Watcom EXE использует текстовый режим.

### Проверка в DOSBox-X

DOSBox-X устанавливается отдельно. Его дистрибутив и компиляторы не включены
в репозиторий. Подготовьте семь коротких пакетов:

```sh
mkdir -p build/russia
cp dos/TINY.EXE dos/TINY.BIN build/russia/
python3 scripts/prepare_russia_smoke.py
```

В PowerShell повторите команду для индексов от 0 до 6:

```powershell
./scripts/run_dosbox.ps1 -Dosbox "C:\DOSBox-X\dosbox-x.exe" -TestName russia-smoke-0 -InputFile build/russia-smoke-0/INPUT.TXT -Executable build/russia/TINY.EXE -Weights build/russia/TINY.BIN -ReserveKB 72 -TimeoutSeconds 900
```

`ReserveKB` использует LOADFIX, уменьшая доступную обычную память. Скрипт
запускает отдельный скрытый процесс эмулятора; файлы записываются в `build/`.
Далее в Linux/WSL:

```sh
python3 scripts/collect_russia_dos.py
python3 scripts/evaluate_c.py --model-dir build/russia --questions data/russia-final/smoke.jsonl --transcript reports/russia/dos-output.cp866.txt --out reports/russia/dos.json
```

Сборщик проверяет совпадение EXE и BIN всех пакетов. Готовые исторические
транскрипты в `reports/` относятся к поставляемым весам, поэтому при изменении
модели измерения нужно повторить.

Для проверки консольного ввода через BIOS: `sh scripts/build_console_probe.sh`,
затем `scripts/test_console.ps1 -Dosbox "C:\DOSBox-X\dosbox-x.exe"`.

## Упаковка

После проверки текущих артефактов:

```sh
mkdir -p dist
python3 scripts/package_release.py
python3 scripts/package_windows.py
python3 scripts/package_source.py
```

Первые два скрипта используют уже подготовленные измерения и уведомления runtime.
При смене компилятора нужно актуализировать относящиеся к нему уведомления.
`package_source.py` включает исходники, данные, текущие сборки, три необходимых
чекпоинта и отчёты, исключая инструменты и промежуточные объекты.

Результат в `dist/`: ZIP Windows, ZIP DOS, незагрузочный FAT12-образ 1,44 МБ
и архив исходников. Образ проверяется `scripts/test_floppy.ps1` с явно указанным
путём `-Dosbox`. Файлы `dist/` исключены из Git и подходят для прикрепления к релизу.
