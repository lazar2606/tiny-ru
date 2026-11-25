# Воспроизведение обучения

## Какие веса включены

| Файл | Роль |
|---|---|
| `training/release.pt` | Финальная русская модель r3 |
| `experiments/r2-release/baseline.pt` | Начальная русская модель для этапов r3 |
| `experiments/v2-release/baseline.pt` | Начальная русская модель для воспроизведения r2 |

В старом v2-чекпоинте пути запуска приведены к относительным. Тензоры,
состояния оптимизатора и генераторов случайных чисел проверены на точное
совпадение. Метаданные подготовки к публикации — `PUBLICATION.json`.
Финальный чекпоинт и BIN оставлены побайтно исходными.

Чекпоинты используют сериализацию PyTorch; загружайте `.pt` из доверенного источника.
Для запуска программы достаточно BIN, файлы `.pt` нужны для разработки.

## Окружение и данные

Подготовьте Python-окружение по [BUILD.md](BUILD.md). Исходное обучение выполнялось
с PyTorch 2.4.1+cpu и NumPy 1.24.4, seed 42, два потока CPU.
Чекпоинты фиксируют настройки, SHA-256 словаря и train, optimizer и RNG.
Различия версий библиотек и аппаратуры могут менять результат и время обучения.

Данные и снимки Wikidata уже включены. Для воспроизведения этого выпуска
скачивать свежие данные не нужно: другой срез источников даст другой эксперимент.
Перед изменением данных сохраните эталоны, относящиеся к прежним весам.

Последовательность генераторов:

```sh
python3 training/tokenizer.py
python3 scripts/generate_strings.py
python3 training/gen_ru.py
python3 training/gen_improved.py
python3 training/gen_russia.py
python3 training/expand_russia.py
python3 training/calibrate_russia.py
python3 training/correct_russia.py
```

Финальный текущий набор — `data/russia-final/`. Ранние снимки нужны для
воспроизведения этапов, но содержат впоследствии исправленные эталоны.
Генераторы проверяют длины, словарь и пересечения формулировок.

## r3 из сохранённого r2: 9500 шагов

Короткий вариант, с сохранением результатов отдельно от поставляемой модели:

```sh
sh scripts/train_release.sh
```

По умолчанию результаты попадут в `build/reproduced/`. Можно указать другую папку:

```sh
sh scripts/train_release.sh build/my-run
```

Скрипт использует включённые в репозиторий данные. Его команды соответствуют
четырём выполненным этапам ниже.

### 1. Краткие вопросы: 3000 выполненных шагов

```sh
python3 training/train2.py train --data data/russia/train.jsonl --validation data/russia/validation.jsonl --control data/russia/control.jsonl --init experiments/r2-release/baseline.pt --out build/reproduced/russia-stage1.pt --steps 8000 --stop-after 3000 --batch-size 32 --lr 0.001 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format
```

`--steps 8000` задаёт исходный график learning rate, `--stop-after 3000` — число
фактически выполненных шагов. Для воспроизведения этого этапа нужны оба параметра.

### 2. Расширенные формулировки: 5000 шагов

```sh
python3 training/train2.py train --data data/russia-expanded/train.jsonl --validation data/russia-expanded/validation.jsonl --control data/russia-expanded/control.jsonl --init build/reproduced/russia-stage1.pt --out build/reproduced/russia-expanded.pt --steps 5000 --batch-size 32 --lr 0.0007 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format --augment-prefixes
```

### 3. Короткие естественные вопросы: 1000 шагов

```sh
python3 training/train2.py train --data data/russia-calibration/train.jsonl --validation data/russia-expanded/validation.jsonl --control data/russia-expanded/control.jsonl --init build/reproduced/russia-expanded.pt --out build/reproduced/russia-calibrated.pt --steps 1000 --batch-size 32 --lr 0.0003 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format
```

### 4. После уточнения источников: 500 шагов

```sh
python3 training/train2.py train --data data/russia-final/train.jsonl --validation data/russia-final/validation.jsonl --control data/russia-final/control.jsonl --init build/reproduced/russia-calibrated.pt --out build/reproduced/russia-final.pt --steps 500 --batch-size 32 --lr 0.00015 --loss-per-example --focus-prefix россия: --focus-probability 0.8 --no-curriculum --augment-format
```

Исправления затронули пять записей: устья Волги, Деймы и Гюльгерычая,
исторический период Румянцевского музея и отличение музея «Гатчина» от города.
Первичные ответы источников сохранены, а итоговые эталоны исправлены открыто.

## Предыдущие этапы

Русский v2 обучался со случайных весов:

```sh
python3 training/train2.py train --steps 6000 --batch-size 24 --lr 0.002 --augment-prefixes --question-weight 0.1 --out build/v2.pt
```

r2 из сохранённого v2:

```sh
python3 training/train2.py train --data data/improved/train.jsonl --validation data/improved/test.jsonl --control data/improved/control.jsonl --init experiments/v2-release/baseline.pt --out build/r2-stage1.pt --steps 2000 --batch-size 32 --lr 0.0007 --loss-per-example --arithmetic-probability 0.5 --no-curriculum --augment-format --augment-prefixes
python3 training/train2.py train --data data/improved/train.jsonl --validation data/improved/test.jsonl --control data/improved/control.jsonl --init build/r2-stage1.pt --out build/r2.pt --steps 1000 --batch-size 32 --lr 0.0003 --loss-per-example --arithmetic-probability 0.5 --no-curriculum --augment-format
```

Чтобы использовать собственные пересозданные веса как старт r3, замените
`--init experiments/r2-release/baseline.pt` на путь к своему r2-чекпоинту.
Всего выполненные исходные этапы составляют 6000 + 3000 + 9500 шагов;
время подготовки данных и сборки в это число не входит.

## Продолжение и экспорт

`--resume` продолжает тот же запуск с optimizer и RNG. Сохраняйте его данные,
целевое число шагов, seed, размер батча, LR и режимы аугментации/выборки.
Для другого набора или новых настроек используйте новый этап через `--init`.

Экспорт и проверка отдельного результата:

```sh
python3 training/train2.py export build/reproduced/russia-final.pt build/reproduced/TINY.BIN
python3 training/train2.py eval build/reproduced/TINY.BIN --questions data/russia-final/control.jsonl --out build/reproduced/evaluation.json
python3 training/train2.py ask build/reproduced/TINY.BIN "кто президент россии?"
```

Оценка читает именно экспортированный BIN, а C-runtime дополнительно проверяется
отдельным прогоном из-за своего KV-cache и вычислений с плавающей точкой.
Для обновления программы сначала экспортируйте выбранные веса в `dos/TINY.BIN`,
затем пересоберите Windows либо скопируйте тот же BIN рядом с её EXE.
При изменении словаря нужно перегенерировать заголовки, переобучить модель
и пересобрать EXE. Используйте веса и токенизатор одной версии.

Команда `scripts/evaluate_russia.sh` сохраняет новые измерения в `reports/russia/`
и использует кандидат из `build/russia/`. Перед её запуском соберите `build/tiny-native`
и создайте `build/russia/`. Поставляемые исторические отчёты будут перезаписаны.

Полный сборщик `write_russia_report.py` дополнительно ожидает промежуточные
чекпоинты и завершённые DOS-пакеты. Готовые опубликованные отчёты доступны
без повторения обучения.
