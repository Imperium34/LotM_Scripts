#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
o_denetle.py -- "o"yu belirli tanımlık (İngilizce "the") gibi kullanma tiki.

Model çevirisi (özellikle Gemini) "o tekinsiz manzara", "o bilinmez
mevcudiyetler" gibi, Çincede işaret sözcüğü olmayan yerde "o" koyuyor.
Türkçede tanımlık yoktur; "o" yalnız gerçekten geri gösteriyorsa yerindedir.

Ölçüt: hizalama grubunun TR'sinde "o + sözcük" var, ZH'sinde 那 yok -> bulgu.
那 varsa "o" büyük olasılıkla kaynaktaki işareti karşılıyor, sayılmaz.
Kalıplaşmış kullanımlar (o zaman, o kadar, o sırada, o hâlde...) ve "o"nun
zamir olduğu belli olan yerler (O bana..., ... de o) hiç sayılmaz.

Rapor adımıdır; çıkış kodu bulgu olsa da 0. 26 Eki ölçümü: 1–64'te
hizalanabilen 432 "o + sözcük"ün 205'inde ZH'de 那 yok.

Kullanim:
    o_denetle.py 63            tek bolum
    o_denetle.py 55-64         aralik (sonda bolum basina sayi ozeti); 55,58,60-64 de olur
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "harita"))

import lotm  # noqa: E402
from gruplar import gruplar  # noqa: E402

# "o"dan sonra gelince kalıp ya da zamir olan sözcükler.
SABIT = set("""
zaman zamanlar zamana kadar sırada sıralar hâlde halde an anda ana anki anlarda
yüzden gün günden günkü günler günlerde günü esnada dönemde dönem denli
aynı yıl yılın yıllarda gece akşam sabah vakit noktada noktaya şekilde türden
tarafa taraftan tarafta yana yandan biçimde ölçüde derece derecede
da de ki ise bile hâlâ artık zaten yine gene sadece yalnızca yalnız gerçekten
bana beni benim bize bizi bizim sana seni senin size sizi sizin
onu ona onun benden senden bizden sizden
""".split())

KELIME = r"[a-zçğıöşüâîû]+"
RX = re.compile(r"(?<![\wçğıöşüÇĞİÖŞÜâîû'’])([Oo]) (" + KELIME + ")")


def bulgular(no: int) -> list:
    """[(¶, parca)]: ZH'sinde 那 olmayan gruplardaki şüpheli 'o + sözcük'."""
    out = []
    for p, g in gruplar(no, "tr").items():
        tr, zh = g.get("TR", ""), g.get("ZH", "")
        # ZH bos/bosluk ise (hizalama TR'yi eslemesiz birakmis) karsilastiracak Cince yok; bulgu degil gurultu
        if not tr or not zh.strip() or "那" in zh:
            continue
        for m in RX.finditer(tr):
            if m.group(2) in SABIT:
                continue
            # Cümle ortasında büyük "O": ilah zamiri, dokunma.
            if m.group(1) == "O" and m.start() > 0 and tr[:m.start()].rstrip()[-1:] not in '.!?…"“_':
                continue
            bas, son = max(0, m.start() - 40), min(len(tr), m.end() + 30)
            out.append((p, "…" + tr[bas:son].replace("\n", " ") + "…"))
    return out


bolum_listesi = lotm.bolum_listesi  # 63, 55-64, 55,58,60-64


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    nolar = bolum_listesi(sys.argv[1])
    sayilar = []
    for no in nolar:
        b = bulgular(no)
        sayilar.append((no, len(b)))
        if len(nolar) == 1 or b:
            print(f"=== {no}: {len(b)} şüpheli 'o' (ZH'de 那 yok)")
        for p, parca in b:
            print(f"  ¶{p}: {parca}")
    if len(nolar) > 1:
        print("\nözet: " + ", ".join(f"{n}:{s}" for n, s in sayilar))
    return 0


if __name__ == "__main__":
    sys.exit(main())
