"""Build a non-bootable 1.44 MB FAT12 data floppy and runtime ZIP."""
import hashlib
import json
import struct
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'dist'
DOS_README='''Tiny-RU 2.1r3 - русская нейросеть для DOS

Запуск: TINY /P 0
Нужны 486DX/Pentium, DOS, шрифт и раскладка CP866, около 540 КиБ свободно.
В DOSBox-X перед запуском: KEYB RU 866
Alt + правый Shift: русский; Alt + левый Shift: латинский.
Для выхода: QUIT (латиницей).

Примеры: привет, как дела?
         кто президент россии?
         какая столица россии?
         сколько будет 2+2
Вопрос - до 72 символов. Длинные строки отклоняются без обрезки.
Точность зависит от формулировки. Сеть может ошибаться и выдумывать ответы.
Обучение дополнено 1000 фактами о России (срез 24.11.2026).
Контроль России int8: знакомые вопросы {familiar:.1f}%, новые формулировки {paraphrase:.1f}%.
Источники: Wikidata CC0 и официальные сайты; сведения могут устаревать.
Это экспериментальная модель, не справочник и не калькулятор.

Архитектура: Transformer, 4 слоя, D=96, H=4, FFN=256, контекст 128.
Веса TINY.BIN: 381808 байт, int8. Ответ вычисляется нейросетью офлайн.
EXE: 16-битный DOS, Open Watcom Large, 386/387. Никакого DOS-extender.
Код/формулировки: MIT, см. LICENSE.TXT. Данные Wikidata: CC0.
Исходная база: github.com/WollyMonjac/Tiny-2.1 (MIT).
Полные исходники, обучение и отчёт находятся в проекте Tiny-RU.

Образ дискеты содержит файлы программы, но не содержит загрузочную DOS.
'''


def build_image(files):
    image=bytearray(1474560)
    boot=memoryview(image)[:512]
    boot[:3]=b'\xeb\x3c\x90'
    boot[3:11]=b'TINYRU21'
    struct.pack_into('<HBHBHHBHHHII',boot,11,512,1,1,2,224,2880,0xf0,9,18,2,0,0)
    boot[36:39]=bytes([0,0,0x29])
    struct.pack_into('<I',boot,39,0x20261124)
    boot[43:54]=b'TINY-RU    '
    boot[54:62]=b'FAT12   '
    # No DOS operating system is included. INT 18h is a boot fallback.
    boot[62:66]=b'\xcd\x18\xeb\xfe'
    boot[510:512]=b'\x55\xaa'
    fat=bytearray(9*512)
    fat[:3]=b'\xf0\xff\xff'
    def set_fat(cluster,value):
        off=cluster*3//2
        pair=fat[off] | (fat[off+1]<<8)
        pair=(pair&0x000f)|(value<<4) if cluster&1 else (pair&0xf000)|value
        fat[off]=pair&255
        fat[off+1]=pair>>8
    cluster=2
    entries=[]
    for index,(name,data) in enumerate(files.items()):
        stem,ext=name.split('.')
        if len(stem)>8 or len(ext)>3:raise ValueError('DOS 8.3 name required')
        first=cluster
        count=(len(data)+511)//512
        if cluster+count>2849:raise ValueError('Floppy capacity exceeded')
        for n in range(count):
            set_fat(cluster,0xfff if n==count-1 else cluster+1)
            offset=(33+cluster-2)*512
            chunk=data[n*512:(n+1)*512]
            image[offset:offset+len(chunk)]=chunk
            cluster+=1
        offset=19*512+index*32
        image[offset:offset+11]=(stem.ljust(8)+ext.ljust(3)).encode('ascii')
        image[offset+11]=0x20
        struct.pack_into('<HHHI',image,offset+22,0,((2026-1980)<<9)|(11<<5)|24,first,len(data))
        entries.append(dict(name=name,bytes=len(data),first_cluster=first,clusters=count,sha256=hashlib.sha256(data).hexdigest()))
    image[512:10*512]=fat
    image[10*512:19*512]=fat
    return image,entries


def verify_image(image,files):
    assert len(image)==1474560 and image[510:512]==b'\x55\xaa'
    assert image[512:5120]==image[5120:9728]
    fat=image[512:5120]
    for i,(name,data) in enumerate(files.items()):
        offset=19*512+i*32
        cluster=struct.unpack_from('<H',image,offset+26)[0]
        size=struct.unpack_from('<I',image,offset+28)[0]
        result=bytearray()
        seen=set()
        while cluster<0xff8:
            assert 2<=cluster<2849 and cluster not in seen
            seen.add(cluster)
            start=(33+cluster-2)*512
            result.extend(image[start:start+512])
            foff=cluster*3//2
            pair=fat[foff]|(fat[foff+1]<<8)
            cluster=(pair>>4)&0xfff if cluster&1 else pair&0xfff
        assert bytes(result[:size])==data


def main():
    DEST.mkdir(exist_ok=True)
    metrics=json.loads((ROOT/'reports/int8.json').read_text(encoding='utf-8'))['metrics']
    readme=DOS_README.format(familiar=100*metrics['russia_familiar']['accuracy'],paraphrase=100*metrics['russia_unseen']['accuracy'])
    (ROOT/'dos/README.TXT').write_bytes(readme.replace('\n','\r\n').encode('cp866'))
    files={name:(ROOT/'dos'/name).read_bytes() for name in ('TINY.EXE','TINY.BIN','README.TXT')}
    files['LICENSE.TXT']=(ROOT/'LICENSE').read_bytes()
    files['WATCOM.TXT']=(ROOT/'docs/OPEN_WATCOM_LICENSE.txt').read_bytes()
    files['NOTICE.TXT']=(
        'Tiny-RU source and Russian data: MIT; see LICENSE.TXT.\r\n'
        'Russia facts include Wikidata structured data (CC0-1.0), snapshot 2026-11-24.\r\n'
        'https://www.wikidata.org/wiki/Wikidata:Data_access\r\n'
        'This EXE links the unmodified Open Watcom C runtime.\r\n'
        'Runtime portions: Copyright (c) 1983-2002 Sybase, Inc. and Open Watcom contributors.\r\n'
        'Runtime/toolchain terms: WATCOM.TXT (Sybase Open Watcom Public License 1.0).\r\n'
        'Runtime source: https://github.com/open-watcom/open-watcom-v2/tree/master/bld/clib\r\n'
        'Compiler project: https://github.com/open-watcom/open-watcom-v2\r\n'
    ).encode('ascii')
    (ROOT/'dos/NOTICE.TXT').write_bytes(files['NOTICE.TXT'])
    (ROOT/'dos/WATCOM.TXT').write_bytes(files['WATCOM.TXT'])
    image,entries=build_image(files)
    verify_image(image,files)
    (DEST/'TINY-RU.IMG').write_bytes(image)
    with zipfile.ZipFile(DEST/'tiny-ru-dos.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():
            info=zipfile.ZipInfo(name,date_time=(2026,11,24,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    manifest=dict(image_bytes=len(image),runtime_bytes=sum(len(b) for b in files.values()),files=entries,bootable=False,codepage=866)
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
