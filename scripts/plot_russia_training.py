"""Scientific training plot from the three actual CPU training logs."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/russia'
panels=[('stage1.jsonl','Краткие вопросы'),('expanded.jsonl','Разные формулировки'),('calibrated.jsonl','Короткие естественные вопросы'),('corrected.jsonl','Уточнение источников')]
fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
for ax,(name,title) in zip(axes.flat,panels):
    rows=[json.loads(s) for s in (OUT/name).read_text().splitlines()]
    x=[r['step'] for r in rows]
    ax.plot(x,[r['loss'] for r in rows],color='#2563eb',label='Обучение')
    ax.plot(x,[r['validation_loss'] for r in rows],color='#d97706',label='Удержанные вопросы')
    ax.set(title=title,xlabel='Шаг этапа',ylabel='Потери CE',ylim=(0,None))
    ax.grid(alpha=.2)
    ax.legend(frameon=False,fontsize=8)
fig.suptitle('Tiny-RU 2.1r3: 1000 фактов о России, seed 42')
fig.savefig(OUT/'training-loss.png',dpi=150)
fig.savefig(OUT/'training-loss.svg')
print(OUT/'training-loss.png')
