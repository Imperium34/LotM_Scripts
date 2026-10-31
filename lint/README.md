# sozluk_lint

LotM Türkçe çevirisi için tutarlılık denetleyicisi.

## Ne işe yarar

Bu araç, **okuyarak yakalanamayan** hata sınıfını hedefler. Bir bölümü ne kadar
dikkatle okursanız okuyun, kanıt başka bir dosyada olduğu için göremeyeceğiniz
şeyler vardır: 5. bölümde "bir libre koyun eti" yazıp 11. bölümde "yarım kiloluk
koyun eti" yazdığınızı, 18. bölümde aynı sayfada hem "Yaradan" hem "Yaratıcı"
kullandığınızı, `Klein'ın` seksen altı kez geçerken bir kez `Klein'in` yazdığınızı.

Bunlar dikkat hatası değil, **mesafe** hatasıdır. Otomatikleştirilmeleri gerekir
ki okuma dikkatiniz gerçekten okumak gerektiren şeye kalsın: anlam, ton, tempo,
Çince ile karşılaştırma.

## Kullanım

```bash
python3 sozluk_lint.py --sozluk sozluk.yml --kurallar lint-kurallari.yml bolumler/*.md
```

Seçenekler:

```bash
--sadece varyant,diyakritik     # yalnızca belirli denetimleri çalıştır
--format json                    # CI / betik için makine okunur çıktı
```

Çıkış kodu: hata varsa 1, yoksa 0. Git kancasına veya CI'ya doğrudan takılabilir.

## Denetimler

| Denetim | Ne arar |
|---|---|
| `varyant` | Aynı kavramın terk edilmiş yazımları (`Fırtına Hakimi` → `Fırtınalar Hakimi`) |
| `yasakli` | Revize edilmiş eski tercihler (`Kukla Üstadı` → `Sır Kuklabazı`) |
| `diyakritik` | (a) Anlam ayırıcı çiftler: `hakim` = *hâkim* mi *hakîm* mi? (b) Şapka tutarsızlığının otomatik taraması — büyük/küçük harf farkı yok sayılır, yalnızca şapka farkı raporlanır |
| `kesme` | Düz `'` ile kıvrık `’` karışımı |
| `ek-uyumu` | Özel adlara gelen eklerin ünlü uyumu (`Klein'ın` / `Klein'in`). Doğru ek `ozel_adlar` altında elle bildirilebilir; bildirilmezse çoğunluğa bakılır ve sonuç TAHMİN olarak işaretlenir |
| `anakronizm` | Dünya dışı sözcüklerin anlatıcı sesine sızması |
| `register` | Bölüm başına arkaik sözcük yoğunluğu, hedef banda göre |

## Kural dosyası

`lint-kurallari.yml` elle bakımı yapılan kısımdır. Yeni bir terim kararı
verdiğinizde eski biçimi `varyantlar` veya `yasakli` altına ekleyin; araç geriye
dönük olarak tüm bölümleri tarar.

Geçiş dönemleri bu araçta değildir. Bir karşılık bir bölüme kadar doğru,
sonra eskimişse (`ritüel → Ayin`, `mistisizm → İlm-i Esrar`), bu `sozluk.yml`'de
`eski_karsiliklar` + `bolum_siniri` olarak tutulur ve `yayim_denetle.py`
denetler. `ogrenme_bolumu`, `kesin_gecis` ve `sadece_anlatici` artık
tanınmayan anahtarlardır: kural atlanır ve hata raporlanır.

Kural başına isteğe bağlı alanlar:

- `istisna:` — bağlamı bu regex'lere uyan eşleşmeler atlanır. Birimin bir kez
  tanımlandığı cümle gibi meşru istisnalar için.
- `harf_duyarsiz: true` — kural büyük/küçük harf ayrımı gözetmez. **Varsayılan
  kapalıdır ve öyle kalmalı:** Türkçe karşılıkların çoğu günlük kelimelerden
  seçildiği için (Yol/yolu, Haz/hazine, San/şanslı) harf duyarsız eşleşme
  yanlış pozitif üretir. Yalnızca terim tek anlamlıysa açın.

## Neyi yakalamaz

- **Anlam hataları.** 焯 (haşlama) yerine "kavurmak" yazdığınızı bu araç
  göremez; onun için Çince gerekir.
- **Register'ın içerikle uyumu.** `register` denetimi yoğunluğu ölçer ama
  sahnenin ne olduğunu bilmez. 3. bölümün 32.8 ile listenin başında olması
  bir bulgudur, hüküm değil — hükmü siz verirsiniz.
- **Diyakritik taramasında gerçek eşadlılar.** `adet` (sayı) ile `âdet` (görenek)
  ayrı kelimelerdir; araç ikisini de aynı gruba koyup önünüze getirir. Aday
  üretir, karar vermez.
- **Hangi ekin doğru olduğunu.** Ünlü uyumu telaffuza bağlıdır ve çoğunluk
  yanılabilir: metinde 6 `Alger'ın` / 3 `Alger'in` var ama doğru olan azınlıktır.
  Bu yüzden karar `ozel_adlar` altında elle verilir.

## Örnek çıktı

```
────────────────────────────────────────────────────────────────────────
VARYANT  (21)
────────────────────────────────────────────────────────────────────────
!! 0018.md:17  “Yaratıcı” → “Yaradan”  [The Creator]
       Aslî Yaradan girdisiyle hizalı. Ch18'de aynı bölümde ikisi birden geçiyor.
       … Neredeyse her baskın ırkın, Yaratıcı’nın bedenindeki belli bir organa …

────────────────────────────────────────────────────────────────────────
EK-UYUMU  (6)
────────────────────────────────────────────────────────────────────────
!! 0018.md:3  “Klein'in” azınlıkta ({'ın': 86, 'in': 1}) — ünlü uyumu tutarsız
```

## Kesin düzeltmeler: `./calistir.sh duzelt`

Bulgunun kendisi tek doğru sonucu söylüyorsa düzeltme otomatiktir; gerisi
rapor kalır. Tek yazma yolu `duzelt.py`'dir: önce fark, `--uygula` ile soru,
yedek (`LotM/yedek/<tarih>/duzelt-<saat>/`) ve yazma.

```
./calistir.sh duzelt                    # hepsi, KURU (fark gösterir)
./calistir.sh duzelt lint --bolum 68    # yalnız lint, yalnız 68
./calistir.sh duzelt --uygula           # fark + soru + yedek + yaz
./calistir.sh duzelt --geri-al yedek/2026-10-31/duzelt-143005
```

`sozluk_lint.py` için kesin sayılanlar:

- **varyant** — yalnız `duzelt` anahtarı olan kurallar (`true` ya da
  `{yanlış: doğru}`). Doğru biçim yanlışın yerine kelimesi kelimesine
  oturmuyorsa (`Kaos Çağı'nda` → `Heyûlâ'da`, `yarım kilo` → `libre`) açmayın.
- **yasakli** — `bicim` → `yerine`, büyük harf korunur; `duzelt: false` kapatır.
- **ek-uyumu** — yalnız `dogru_ekler`'i tanımlı adlar. Ünlüyle biten adlarda
  (Melissa, Audrey) yalnız -dan/-da: `Melissa'ın` kaynaştırma ister, aile içi
  değişim onu yine yanlış bırakırdı. Çoğunluk tahmini hiç düzeltilmez.

Önizleme tek başına: `python3 lint/sozluk_lint.py --duzelt _chapters/`.

### Özel ad adayları

Lint çıktısının sonunda **ÖZEL AD ADAYLARI**: kesmeyle ek alan ama
`ozel_adlar`'da kuralı olmayan adlar, sayımları ve `dogru_ekler` önerisiyle,
yapıştırmaya hazır. Öneri önce metinde kullanılan biçimden, yoksa yazımdan
çıkar (`# metinden` / `# tahmin`); telaffuzu siz kontrol edin. Elenenler:
Türkçe harfli kelimeler, metinde küçük harfle de geçenler, sözlükte Türkçe
adı geçenler (Basiret, Efendi). Ad olmayan kalırsa `ozel_ad_disi`'na ekleyin.

Ünlüyle biten adlarda kaynaştırmalı biçim yazılır (`Melissa: nın, ya, yı,
dan, da`); `Melissa'ın` gibi kaynaştırma hatası da kesin düzeltilir.

### sapka ELLE tabanı

`./calistir.sh sapka-taban` şimdiki kayıt / nisbet / eşadlı geçişlerini
okunmuş sayar (`lint/sapka-taban.tsv`); sonra `sapka`, `belgeler` ve
`duzelt` yalnız YENİ geçişleri gösterir. Taban bir karardır: önce listeyi
okuyun, sürüm denetimine ekleyin.
