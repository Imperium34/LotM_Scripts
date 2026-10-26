# Sistem Kuralları #10 — İmlâ ve Şapka

Bu sözlüğün imlâ mercii **TDK değildir.** Gerekçe kurumsal değil, pratiktir:
TDK şapka konusunda birden fazla kez kendi kararını geri almıştır ve arkaik
bir kayıtta yazılmış bir metne hizmet etmek gibi bir gayesi yoktur. Sabit bir
merci gerekiyor. Bu sözlükte **Kubbealtı Lugatı** esas alınır; ihtilâflı
hâllerde Devellioğlu'na bakılır.

Şapkanın bu metinde üç ayrı işi vardır ve üçü ayrı ayrı karara bağlanır.

## 10.1 — Damaksıllaşma (k / g / l inceltmesi)

Şapka burada uzunluk değil, ünsüzün inceliğini gösterir: **kâğıt, mekân,
imkân, rüzgâr, pekâlâ, yegâne, sükûnet, ilâveten.** Şapkasız karşılıkları
ayrı bir kelime değildir, dolayısıyla **daima yazılır.** `sapka.py` bu
grubu otomatik uygular.

**İstisna: lâzım.** Şapkalı biçim doğru olsa da bu kelime günlük konuşma
malzemesidir ve otomatik uygulamanın dışında tutulmuştur (`sapka.py`'de
ayrı `KAYIT KARARI` grubunda). Klein'ın iç sesinde ve gündelik replikte
şapkasız kalabilir; bkz. aşağıdaki istisna maddesi.

**Kayıt ayrımı (26 Eki 2026).** Aynı gerekçeyle damaksıl grup ikiye
ayrıldı. Kayıt kelimeleri otomatik şapkalanır: **lâkin, kelâm, lâyık,
ahlâk, evlât.** Gündelik kelimeler `lâzım` ile aynı `KAYIT` grubundadır,
otomatik değişmez: **laf, lamba, selam, plan, telaş, ilan, ilaç.**

## 10.2 — Arapça alıntılarda uzunluk

**âdeta, dâhil, hâdise, zât** ve bütün **hâl** ailesi (_hâlde, hâline,
hâlinde, hâlihazırda, herhâlde_). Bu bir kayıt tercihidir ve bu sözlük
arkaik kayıttan yana olduğu için **yazılır.** `sapka.py` bu grubu da
otomatik uygular.

**İstisna — Klein'ın sesi.** Anlatıcı arkaik, Klein'ın iç sesi moderndir.
Günlük konuşma malzemesi olan kelimeler (_lâzım_ gibi) Klein'ın italik iç
sesinde ve Melissa'nın mutfak repliğinde şapkasız bırakılabilir; şapka
takmak, ayırmaya çalıştığınız iki sesi birbirine karıştırır.

## 10.3 — Nisbet -î

**DAİMA YAZILIR.** Bu grup imlâ değil, **anlam** meselesidir:

| şapkalı | manası     | şapkasız | manası              |
| ------- | ---------- | -------- | ------------------- |
| resmî   | official   | resmi    | onun resmi          |
| tarihî  | historical | tarihi   | onun tarihi         |
| askerî  | military   | askeri   | askeri (nesne hâli) |
| hayalî  | imaginary  | hayali   | onun hayali         |
| madenî  | metallic   | madeni   | madeni (nesne hâli) |
| dinî    | religious  | dini     | onun dini           |
| ilmî    | scientific | ilmi     | onun ilmi           |

Nisbet ekiyle iyelik/belirtme eki aynı harfle yazıldığında cümle iki ayrı
şey söyler. Şapkasız yazmak bir sadeleştirme değil, bir belirsizlik
üretimidir. Bu yüzden bu grup TDK'nın tavrından bağımsız olarak yazılır.

Otomatik uygulanmaz: her geçiş okunup hangi mananın kastedildiğine karar
verilir. `sapka.py --elle` adayları listeler.

## 10.4 — Anlam ayırıcı çiftler

Şapka bu çiftlerde **mecburîdir**, zira aksi hâlde kelime başka bir kelimedir:

- **hâkim** (hükmeden, yöneten) ~ **hakîm** (bilge, filozof)
  Sistem Kuralları #2'nin Mürşid yedeği _hakîm_'dir; ilâhî unvanlardaki
  _hâkim_ ise hükümranlık ailesine aittir (bkz. _Ece_ notu). Adalet
  Mertebesi *Kadı*ya çevrildiği için ikisi artık Mertebe adlarında
  çakışmaz — ama ayrım ancak şapka yazıldığında görünür. Mekanik olarak
  10.3'teki nisbet çiftleriyle aynı hastalık: tek bir yazım iki ayrı
  kelimeyi taşıyor, şapka ikisini ayırıyor.
- **âlim** (bilgin) ~ **alîm** (her şeyi bilen; esmâdan)
- **hâlâ** (henüz) ~ **hala** (teyze)
- **âdet** (görenek) ~ **adet** (sayı)
- **âlem** (dünya) ~ **alem** (bayrak, sancak tepeliği)
- **kâr** (kazanç) ~ **kar** (yağan)
- **hâle** (hâl + yönelme) ~ **hale** (ayla, nur halkası)

## 10.5 — Denetim

`sozluk_lint.py --sadece diyakritik` şapkasız sapmaları listeler. Otomatik
tarama **aday üretir, karar vermez**: gerçek eşadlıları (10.4) ayıramaz,
önünüze getirir.

`sozluk_lint.py`'nin arkaik yoğunluk ölçümü şapkasız biçim üzerinden eşleşir;
bu sayede yalnızca imlâyı düzeltmek — metne tek kelime eklemeden — register
rakamını değiştirmez.
