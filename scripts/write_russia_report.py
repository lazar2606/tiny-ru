"""Publish measured r3 results, sources, training settings and release hashes."""
import hashlib
import json
from pathlib import Path
import torch

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'reports'
OUT=REPORTS/'russia'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    read=lambda n:json.loads((OUT/(n+'.json')).read_text(encoding='utf-8'))
    measured={k:read(k) for k in ('float','int8','native','unseen-all','user-regressions','previous-skills','dos')}
    data=json.loads((ROOT/'data/russia/manifest.json').read_text(encoding='utf-8'))
    expanded=json.loads((ROOT/'data/russia-final/manifest.json').read_text(encoding='utf-8'))
    weights=digest(ROOT/'dos/TINY.BIN')
    for name in ('TINY.EXE','TINY.BIN'):
        assert digest(ROOT/'dos'/name)==digest(ROOT/'build/russia'/name)
    assert measured['native']['weights_sha256']==measured['dos']['weights_sha256']==weights
    assert measured['int8']['metrics']['russia_familiar']['total']==1000
    assert measured['unseen-all']['total']==1000
    assert measured['dos']['examples'][0]['correct'], 'President answer failed in DOS'
    tests=(OUT/'unit-tests.log').read_text(encoding='utf-8')
    assert 'Ran 18 tests' in tests and '\nOK\n' in tests
    ck=torch.load(ROOT/'training/release.pt',map_location='cpu',weights_only=False)
    assert ck['data_sha256']==expanded['sha256']['train']
    meta={key:ck[key] for key in ('cfg','vocab_sha256','data_sha256','step','run')}
    stages=[]
    for filename in ('training/russia-stage1.pt','training/russia-expanded.pt','training/russia-calibrated.pt','training/release.pt'):
        stage=torch.load(ROOT/filename,map_location='cpu',weights_only=False)
        stages.append(dict(file=filename,step=stage['step'],data_sha256=stage['data_sha256'],run=stage['run']))
    meta['stages']=stages
    (REPORTS/'checkpoint.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    environment=json.loads((ROOT/'experiments/r2-release/environment.json').read_text(encoding='utf-8'))
    environment['release']='2.1r3'
    environment['files']={name:dict(bytes=(ROOT/name).stat().st_size,sha256=digest(ROOT/name))
                          for name in ('dos/TINY.EXE','dos/TINY.BIN','training/release.pt')}
    (REPORTS/'environment.json').write_text(json.dumps(environment,indent=2)+'\n',encoding='utf-8')
    metric=lambda m:'%d/%d (%.1f%%)'%(m['correct'],m['total'],100*m['accuracy'])
    table=[]
    for split,label in [('russia_familiar','Знакомые формулировки всех фактов'),('russia_unseen','Удержанные формулировки, выборка')]:
        table.append('| '+label+' | '+' | '.join(metric(measured[k]['metrics'][split]) for k in ('float','int8','native'))+' |')
    baseline=read('baseline-int8')['metrics']['russia_familiar']
    old_baseline=json.loads((ROOT/'experiments/r2-release/int8.json').read_text(encoding='utf-8'))['metrics']
    previous=measured['previous-skills']['metrics']
    old_table='\n'.join('| '+label+' | '+metric(old_baseline[k])+' | '+metric(previous[k])+' |'
                        for k,label in [('familiar','Знакомые вопросы старых тем'),('paraphrase','Перефразировки старых тем'),
                                        ('арифметика','Арифметика: новые формулировки'),('неизвестное','Неизвестные вопросы')])
    categories='\n'.join('| '+k.replace('россия: ','',1)+' | '+str(v)+' |' for k,v in data['categories'].items())
    dos=measured['dos']
    examples='\n'.join('| '+r['question']+' | '+r['answer']+' | '+('да' if r['correct'] else 'нет')+' |' for r in dos['examples'])
    scope=dict(version='2.1r3',facts=1000,source_date='2026-11-24',weights_sha256=weights,
               dos_questions=dos['total'],python_control=1200,native_control=1200,
               all_unseen_wordings=1000,checkpoint_step=ck['step'],additional_training_steps=sum(s['step'] for s in stages))
    (REPORTS/'release-r3.json').write_text(json.dumps(scope,indent=2)+'\n',encoding='utf-8')
    text='''# Tiny-RU 2.1r3: 1000 фактов о России

В русскую модель добавлен набор из 1000 фактических записей о России,
её географии, государстве, истории городов, науке и культуре. Варианты одного
вопроса и старые арифметические упражнения не увеличивают число новых фактов.
Объём набора не означает, что модель безошибочно воспроизводит все сведения.

## Содержание и происхождение

| Тема | Фактов |
|---|---:|
'''+categories+'''

Читаемый список: `data/russia-final/facts.txt`; полный JSONL с происхождением —
`data/russia-final/facts.jsonl`. Структурированные связи импортированы из Wikidata
по CC0-1.0, вопросы написаны для проекта. У каждой записи есть URL источника
и дата сверки; снимки исходных запросов и ответов API приложены.
Ручное ядро проверялось по сайту президента, Конституции на сайте Минюста,
Банку России и Центру подготовки космонавтов. Полный независимый аудит каждой
импортированной связи не проводился. Неоднозначные названия и даты исключались.
История Российской империи и СССР включена как связанная тематика;
это не утверждение о национальной принадлежности всех советских достижений.

На срез 24 ноября 2026 года президент России — Владимир Путин.
Это сведение помечено как изменяемое. Офлайн-модель не обновляет факты сама.

## Обучение

Сохранена архитектура 4 слоя, D96, H4, FFN256, 366528 параметров и словарь
97 токенов. Дообучение начато с русского r2, seed42, PyTorch CPU, два потока.
80% выборок предназначены новым фактам; остальные повторяют прежние области.
Короткие ответы имеют равный вес примера с длинными, президентский вопрос
получает больший вес. Английские веса не использовались.
Никакие таблицы ответов или калькулятор в DOS runtime не добавлены.

Этапы: 3000 шагов на кратких формах, 5000 на расширенных, затем 1000 шагов
калибровки на коротких естественных вопросах и 500 шагов после сверки неоднозначных
источников. В частности, из ответов об устье Волги удалена Кама, а для
Румянцевского музея указан исторический период. Первичные снимки оставлены
для воспроизведения; актуальные эталоны находятся только в `data/russia-final`.
Команды воспроизведения находятся
в README. Точные запуски и шаги чекпоинтов —
`reports/checkpoint.json`, логи — `reports/russia/stage1.log`, `training.log`,
`calibration.log` и JSONL. График — `reports/russia/training-loss.png`.
Исходный r2-чекпоинт включён в архив: `experiments/r2-release/baseline.pt`.
Все удержанные формулировки проверены на отсутствие пересечений с train
исходного v2, r2 и текущего этапа. Для каждого известного факта обучаются
одни вопросы, а удерживается другая формулировка. Это проверка формулировок,
а не умения узнать факты, которых не было в обучении.

## Измеренные результаты

| Проверка | FP32 Python | int8 Python | Нативный C |
|---|---|---|---|
'''+ '\n'.join(table)+'''

Старый r2 BIN на первоначальном контроле нового набора: '''+metric(baseline)+'''.
После этого часть эталонов и два вопроса были уточнены; данное историческое
измерение не следует считать строго парным сравнением с финальным набором.
Все 1000 удержанных формулировок, Python int8: '''+metric(measured['unseen-all']['metrics']['russia_unseen'])+'''.
Старые 8 пользовательских регрессий, Python int8: '''+metric(measured['user-regressions']['metrics']['user_regression'])+'''.
На старых темах сохранились знакомые ответы, однако обобщение ухудшилось:

| Старый контроль, Python int8 | r2 | r3 |
|---|---|---|
'''+old_table+'''

Это измеренное ограничение дообучения маленькой модели. Подробности старых
140 контрольных вопросов — `previous-skills.json`; прежние веса сохранены
в `experiments/r2-release/TINY.BIN`.
Метрика: точное совпадение с одним из эталонов после регистра и конечной пунктуации.
C может отличаться от Python из-за округления и int8 KV-cache.
Сложные или иначе сформулированные вопросы всё ещё могут давать неверный ответ.

## Реальные DOS-проверки

В DOSBox-X выполнено '''+str(dos['total'])+''' вопросов; совпали с эталоном '''+str(sum(r['correct'] for r in dos['examples']))+''' из '''+str(dos['total'])+'''.
Оставшаяся ошибка на развёрнутой формулировке вопроса о президенте показывает
ограничение обобщения: обычное «кто президент россии?» отвечает верно,
а другая формулировка может дать бессмысленное имя. Результаты:

| Ввод | Ответ | Совпадение с эталоном |
|---|---|---|
'''+examples+'''

Полные 1200 вопросов выполнены в нативном C и Python, не в DOS.
CP866-транскрипты DOS и проверка их EXE/BIN сохранены отдельно.
Сессии используют LOADFIX 72 КиБ; для запуска рекомендуется около 540 КиБ
свободной обычной памяти. Реальное оборудование не проверялось.
18 автоматических тестов включают точное продолжение обучения с выборкой
новой области, 1000 уникальных связей, отсутствие утечки и ограничения DOS.

EXE: 16-битный DOS Open Watcom Large 386/387. BIN: 381808 байт, формат TNY2.
SHA-256 готовых файлов и версии среды — `reports/environment.json`.
Для загрузки новых весов завершите старую программу и запустите её заново.
Начальный заголовок — `Tiny-RU 2.1r3`.
'''
    (REPORTS/'REPORT.md').write_text(text,encoding='utf-8')
    (OUT/'REPORT.md').write_text(text,encoding='utf-8')
    for name in ('float','int8','native'):
        (REPORTS/(name+'.json')).write_bytes((OUT/(name+'.json')).read_bytes())
    print(json.dumps(scope,indent=2))


if __name__=='__main__':main()
