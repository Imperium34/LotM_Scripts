# LotM Türkçe Çeviri — Araçlar

Bu klasör çeviri sürecinin araçlarını ve istemlerini barındırır.
**Bu depo private olmalı.** Sitenin kendisi ayrı ve public bir depodadır.

---

## Klasör düzeni

```
~/LotM/
├── Imperium34.github.io/     ← PUBLIC git deposu (Jekyll sitesi)
│   ├── _data/sozluk.yml          tek doğruluk kaynağı
│   ├── _chapters/0001.md …       yayımlanmış bölümler
│   └── sozluk.html               sözlük sayfası şablonu
│
├── Source/                   ← HİÇBİR DEPODA OLMAMALI
│   ├── Lord_of_the_Mysteries.epub
│   └── LotM_Volumes/*.txt        epub'dan dönüştürülmüş ciltler
│
└── Tools/                    ← PRIVATE git deposu (burası)
    ├── Prompts/                  çeviri istemleri
    ├── Reports/                  üretilen raporlar (gitignore'da)
    ├── Test_Chapters/            eski deneme çevirileri
    └── *.py, calistir.sh
```

`Source/` kardeş dizinde durur, alt dizinde değil. Sebep basit: alt
dizinde olsaydı dikkatsiz bir `git add .` romanın tamamını public depoya
sokabilirdi. Betiklerin hepsi kaynak yolunu argüman olarak alır, bu yüzden
klasörün taşınmasına gerek yok.

---

## 1. Çeviri döngüsü (bölüm başına, elle)

| # | Girdi | Çıktı |
|---|-------|-------|
| 1 | `lotm_chapter_template.md` + `sozluk.yml` + ses haritası | o bölüme özel istem |
| 2 | üretilen istem + `lotm_system_prompt.md` + kaynak bölüm | ham çeviri |
| 3 | ~1 saat okuma ve düzeltme | yayına hazır bölüm |
| 4 | `lotm_socials_prompt.md` + çevrilmiş bölüm | Instagram açıklaması + alıntı |

**Üretilen istemi saklayın.** Adım 1'deki istem o anki `sozluk.yml`
durumundan üretilir. Sözlük değiştikçe eski bölümler artık geçerli olmayan
bir sözlük durumuna göre çevrilmiş olur. İstemi bölümün yanında saklamak
"12. bölümde neden bu karşılık kullanılmış" sorusunu aylar sonra
cevaplanabilir kılar. Öneri: `Prompts/uretilen/0012.md`.

---

## 2. Bakım döngüsü (periyodik, otomatik)

```bash
cd Tools
./calistir.sh              # tam zincir
./calistir.sh denetim      # sadece çeviri denetimi (hızlı, sık kullanılan)
```

Zincirin sırası bağımlılıktan gelir:

```
searcher.py    Source/LotM_Volumes  →  Reports/rapor.tsv
etiketle.py    rapor.tsv            →  _data/sozluk.yml   (yerinde yazar)
denetci2.py    sozluk.yml + _chapters → Reports/denetim.txt
```

### searcher.py — İngilizce metin taraması
Terimlerin romanın metninde geçip geçmediğini belirler (`metinde`).
Harf duyarlı çalışır, çünkü Mertebe adları özel isimdir. Nadiren
çalıştırılır; yalnızca sözlüğe yeni terim eklendiğinde gerekir.

### etiketle.py — alan yazımı
`kaynak`, `mudahale`, `metinde`, `denetim` alanlarını yazar. Bütün
kurallar dosyanın başındaki blokta; elle yazılmış değer yoktur, bu yüzden
yeniden çalıştırmak güvenlidir ve diff denetim kaydı işlevi görür.
Bölüm numaraları **yalnızca ileri** taşınır; elle kararlaştırılanlar
`BOLUM_ELLE` bloğunda tutulur.

### denetci2.py — çeviri tutarlılık denetimi
Yayımlanmış bölümleri sözlüğe karşı denetler. Dört soru:
1. Sonradan değiştirilen bir karşılık eski hâliyle mi duruyor? (`eski_karsiliklar`)
2. İngilizce terim çevrilmeden mi kalmış?
3. Terim kendi `bolum_siniri`'ndan önce mi kullanılmış?
4. Envanter: hangi terim nerede geçiyor?

**En çok kullanılacak olan budur.** Yirmi bölümde bir çalıştırmak,
terminoloji kaymasını daha alışkanlık hâline gelmeden yakalar.

### lotm_splitter.py — epub → txt
Tek seferlik. Ciltler zaten `Source/` içinde duruyor.

---

## Bilinmesi gerekenler

**Çeviri, dönüştürülmüş İngilizce metinden daha güvenilirdir.**
`LotM_Volumes/*.txt` dosyaları epub'dan komutla üretildi ve bazı yerleri
bozuk. 21. bölüm örneğinde tarayıcı Roselle'in günlüğündeki geçişi
kaçırdı, çeviri ise doğru gösterdi. İkisi çeliştiğinde çeviri kazanır.

**Bulgular hata değil adaydır.** "Kara İmparator" 5. bölümde Solomon
İmparatorluğu'nun hükümdarı anlamına gelir. Metin aynı, gönderge farklı.
Ölçüt şudur: *okuyucu o noktada terimi bir Mertebe adı olarak tanıyabilir
mi?* Tanıyamıyorsa geçiş sayılmaz.

**Kısa terimler uzun terimlerin içinde saklanır.** `Avcı`, `Gizem
Avcısı`'nın içinde geçer. Denetçi en uzun terimi önce eşleştirip aralığı
tüketerek bunu çözer, ama yeni terim eklerken akılda tutmak gerekir.

**Sözlükteki her alanın tek bir işi vardır.** Proje boyunca tekrar eden
hata, tek alana iki soru yükletmekti: `kanon_durumu` hem "nereden geldi"
hem "ne yapıldı" sorusunu; `bolum_siniri` hem "ilk nerede geçiyor" hem
"okuyucuya ne zaman gösterilsin" sorusunu cevaplıyordu. Yeni alan
eklerken önce sorunun tek olduğundan emin olun.

---

## Ses haritaları

Karakter ses haritaları çeviri isteminin girdisidir, tıpkı `sozluk.yml`
gibi. `Tools/` içinde tutulmalı ve **asla site deposuna girmemeli**.

Sözlükte terim kayması için bir denetçi var; ses kayması için yok.
Karakterlerin konuşma tarzı 1400 bölümde kayabilir ve bunu yakalayan
otomatik bir kontrol bulunmuyor. Şimdilik el yordamıyla; ileride
gerekirse ses haritalarını da denetime dahil etmek mümkün.
