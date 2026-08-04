# sozluk.yml — Şema ve Kural Belgesi

**Sürüm:** 2 · **Tarih:** 2026-07-24
**Kaynak sürümleri:** Webnovel resmî İngilizce çevirisi · Circle of Inevitability

Bu belge `_data/sozluk.yml` dosyasının şemasını ve dosyaya uygulanan kuralları
tanımlar. Okuyucuya dönük açıklama için `/sozluk/hakkinda/` sayfasına bakınız;
bu belge bakım içindir.

**Tüketiciler:** `sozluk.html` (Jekyll/Liquid + JS) · `Tools/searcher.py` ·
`Tools/etiketle.py` · `Tools/denetci2.py`

---

## 1. Kök yapı

Kök bir **listedir**, eşleme değil. Bu yüzden dosyaya `meta:` gibi üst düzey bir
anahtar eklenemez; eklenirse her tüketici kırılır. Şema belgesi bu yüzden ayrı
dosyada durur.

İki tür girdi vardır:

- **Terim girdisi** — `aciklama` taşır, `mertebeler` taşımaz.
- **Yol girdisi** — `mertebeler` taşır, `aciklama` taşımaz. Kategorisi daima
  `Aşkın Yolları`'dır.

İkisi farklı alan kümesi kullanır. Bu bilinçlidir ama şu an bir maliyeti var:
en çok tartışılan çevirmen notları Mertebe katmanında durur ve o katmanda
`mudahale` / `denetim` alanları yoktur (bkz. §4.2).

---

## 2. Alanlar — terim girdisi

| Alan                  | Zorunlu | Tip   | Açıklama                                                                                |
| --------------------- | ------- | ----- | --------------------------------------------------------------------------------------- |
| `terim`               | evet    | dize  | Türkçe madde başı. Tarot Kulübü'nde İngilizce kart adı parantez içinde buraya katlanır. |
| `ingilizce`           | evet    | dize  | **Arama anahtarı** (bkz. §3).                                                           |
| `kategori`            | evet    | dize  | Sabit küme, bkz. §2.1.                                                                  |
| `yol_grubu`           | hayır   | dize  | `Türkçe (İngilizce)` biçiminde ilah/yol ailesi.                                         |
| `aciklama`            | hayır   | dize  | Tanım ya da tazim ismi. `<br>` satır ayracıdır (bkz. §4.5).                             |
| `cevirmen_notu`       | hayır   | dize  | Tercihin gerekçesi.                                                                     |
| `cevirmen_notu_sinir` | hayır   | int   | Notun açılacağı bölüm. Verilmezse `bolum_siniri`.                                       |
| `cevirmen_notu_ek`    | hayır   | liste | `{sinir, baslik, metin}` — kademeli açılan ek notlar.                                   |
| `bolum_siniri`        | evet    | int   | Bölüm kapısı (bkz. §4.3).                                                               |
| `kaynak`              | evet    | enum  | `metin` / `yazar_beyani` / `karma` / `metin_coi` (bkz. §4.4).                           |
| `mudahale`            | evet    | enum  | `ceviri` / `degistirme` / `tamamlama` / `ozgun` / `birlestirme` (bkz. §4.1).            |
| `denetim`             | evet    | enum  | `tamam` / `denetlenmedi` (bkz. §4.6).                                                   |

### 2.1 Kategoriler

`Temel Kavramlar` · `Organizasyonlar` · `İlahlar ve Yüce Kadimler` ·
`Tarot Kulübü` · `Aşkın Yolları` · `Coğrafya ve Mekanlar`

> **Bilinen sorun.** `Coğrafya ve Mekanlar` tek girdi taşır ve o girdi
> (_Antigonus Ailesinin El Yazması_) bir mekân değil bir nesnedir. `Temel
Kavramlar` ise ontoloji, teknik, kozmoloji ve gündelik dünya kurgusunu tek
> torbada tutar. Kategori ekseni yeniden düşünülmeyi bekliyor.

---

## 3. `ingilizce` alanı — anahtar, karşılık değil

`ingilizce`, **Webnovel resmî İngilizce çevirisinde geçen ifadedir.** Türkçe
terimin çevirisi değildir. Tek işlevi, İngilizce metni okumuş birinin terimi
bulabilmesidir.

Bu ayrım yalnızca tek yerde görünür hâle gelir:

```yaml
- seviye: 6
  isim: "Gulyabani (Devil)"
- seviye: 4
  isim: "Şeytan (Demon)"
```

Resmî İngilizce çeviri bu iki Mertebenin adlarını birbiriyle değiştirmiştir.
Sözlük İngilizce adlara değil her Mertebenin kanonik doğasına uyar; `ingilizce`
alanı ise anahtar olduğu için Webnovel'deki hâliyle bırakılır. **Bu bir hata
değildir ve düzeltilmemelidir.**

> **Bilinen tutarsızlık.** Tarot Kulübü'nün on iki girdisinden on birinde
> `ingilizce` alanı kart adını değil karakterin adını taşır
> (`terim: "Adalet (Justice)"`, `ingilizce: "Audrey Hall"`). Yani o kategoride
> alan §3 kuralını izlemez. Arama katmanı her iki alanda alt dize eşleşmesi
> yaptığı ve `terim` içinde `Justice` bulunduğu için erişim kaybı yoktur;
> tutarsızlık yalnızca şema düzeyindedir.

---

## 4. Kurallar

### 4.1 `mudahale` = köken, algı değil

`mudahale` **sayılabilir bir kanonik nesneyle** kurulan ilişkiyi bildirir:

| Değer         | Anlamı                                                       |
| ------------- | ------------------------------------------------------------ |
| `ceviri`      | Hiçbir kanonik satır çıkarılmadı, değiştirilmedi, eklenmedi. |
| `degistirme`  | Kanonik satır(lar) başkasıyla değiştirildi.                  |
| `tamamlama`   | Kanon eksikti, tamamlandı.                                   |
| `ozgun`       | Kanonda karşılık yoktu, tamamı yazıldı.                      |
| `birlestirme` | Kanonik satırlar birleştirildi.                              |

**Karar ölçütü budur.** Bir tercihin çağrışım katmanında
ne kadar derin çalıştığı `mudahale` alanını ilgilendirmez; o iş çevirmen
notunundur. Sık karıştırılan örnekler, hepsi `ceviri`:

- **Ebedi Gece Tanrıçası:** "Ece" tercihi Asena/Bozkurt göndermesi taşıyan bir
  headcanon'dır, ama hiçbir kanonik satırı değiştirmez.
- **İlahların Metruk Diyarı:** "metruk" kelimesinin doğal kapsamı bilinçli
  olarak zorlanır; satır yine de kanoniktir.
- **Yıldızlı Gökkubbe:** "gökkubbe" ne Çince ne İngilizce kaynakta bulunan bir
  mimari çağrışım ekler, ama gönderge aynıdır.

### 4.2 `mudahale` Mertebe adlarına uygulanmaz — ve bu bilinçlidir

Mertebe adlarında `mudahale` alanı **yoktur ve eklenmemelidir.** Sebep, alanın
sayılabilir bir kanonik nesne varsaymasıdır. Tazim isimlerinde böyle bir nesne
vardır: satırları saymak, tutmak, düşürmek, değiştirmek mümkündür. Mertebe
adlarında yoktur. Ortada bir ad, bir yetenek demeti, bir ilerleme ayini ve
güvenilirliği tartışmalı bir İngilizce çeviri vardır. Neye sadık kalındığı
sayılamaz.

Bu yüzden Mertebe adlarında gerekçe **yalnızca `cevirmen_notu` ile taşınır.**
Alanın yokluğu bir eksiklik değil, kapsam sınırıdır.

### 4.3 `bolum_siniri`

Girdinin açılacağı bölüm numarası. **Sentinel değer yoktur**; her değer gerçek
bir bölüm numarasıdır. İki özel değer:

- **`0`** — bölüm kapısı yok. İki durumda kullanılır: (a) giriş düzeyi terimler,
  (b) kaynak ekseninde kapalı olduğu için bölüm ekseninde kapıya ihtiyaç duymayan
  girdiler.
- **`1409`** — LotM'un son bölümü. **İki farklı anlamı vardır ve ayrılamaz:**
  "seri bitmeden açılmaz" (Mertebe 0 adları) ve "gerçek bölüm henüz tespit
  edilmedi".

**`SON_BOLUM = 1409` üç yerde tekrarlanır** ve birlikte güncellenmelidir:
`sozluk.html` (JS sabiti), `Tools/denetci2.py` (modül sabiti), bu belge.

### 4.4 `kaynak` — ikinci ve bağımsız eksen

`kaynak`, girdinin nereden geldiğini bildirir ve **bölüm ekseninden bağımsız
olarak kapı işlevi görür.** Bir girdinin görünmesi için iki eşiğin de geçilmesi
gerekir.

| Değer          | Kapı                  | Anlamı                                      |
| -------------- | --------------------- | ------------------------------------------- |
| `metin`        | yok                   | LotM metninden.                             |
| `yazar_beyani` | "metin dışı" anahtarı | Yazarın metin dışı açıklamaları.            |
| `karma`        | "metin dışı" anahtarı | Karışık; **en kısıtlayıcı tabana tabidir.** |
| `metin_coi`    | "CoI" anahtarı        | Circle of Inevitability metninden.          |

CoI ayrı bir eksendir çünkü LotM bölüm numaralarıyla ölçülemez: ayrı bir eser ve
hâlâ yayımlanıyor. LotM'u bitirmek CoI içeriğini açmaz.

İlke: **etiket ifşadan sonra bilgi verir, anahtar ifşadan önce karar verdirir.**
Rozet tek başına yeterli değildir.

### 4.5 `denetim` durum, doğruluk iddiası değil

`tamam`, girdinin **ikinci geçişten geçtiğini** bildirir; kanona uygunluğunun
kanıtlandığını değil. `denetlenmedi` bilerek görünür rozet alır:
**rozetin yokluğu "doğrulandı" anlamına gelmemelidir.**

> **Bilinen sorun — sıra bağımlılığa ters.** Tazim isimleri denetlendi
> (`tamam`), kavram girdileri denetlenmedi. Ama tazim isimleri kavram
> girdilerinden **kurulur**: _Esrarın Hükümdarı_ içinde "Alem-i Ervah Hakimi" ve
> "Aslî Kale'nin Tecessümü" geçer, _Kadir-i Mutlak_ içinde "Alem-i Misal
> Efendisi" geçer. Bu üç kavram girdisi de `denetlenmedi`. İkinci geçiş bunları
> değiştirirse, onları içeren her tazim ismi yeniden açılır. Yapraklar köklerden
> önce denetlendi.

---

## 5. Adlandırma kuralları

Bunlar tek tek girdilerde değil sözlüğün bütününde geçerlidir.

**Kayıt katmanlaması.** Kozmoloji ve ilahiyatta klasik Arapça-Farsça kayıt
esastır. Öz Türkçe kelimeler **işaretli istisnadır**, varsayılan değil; her biri
kendi girdisinde gerekçelendirilir (Ece, Bora Kamı).

**Bölgesel adlar.** `bolgesel` alanı şu an yalnızca Avcı Yolu'nda kullanılır.
Intis adları Fransızca kökenli kayıttadır (Provokatör, Piroman, Komplocu,
Mareşal); bu, Türkçenin gerçek Fransızca ödünçleme katmanına yaslanır ve Intis'in
Fransa kodlamasıyla örtüşür. Diğer yollara genişletilebilir; alanın yokluğu
"veri eksik" değil "kapsam dışı" demektir.

**Yıldız işareti.** Bir Mertebe adının başındaki `*`, karşılığın geçici olduğunu
ve daha iyi bir alternatif bulunursa değiştirileceğini bildirir. Şu an tek
kullanım: Avcı Yolu S5 Intis: `Mareşal`.

**`Mentor` → `Mürşid`, yalnızca ahlaken muğlak yollarda.** `Mürşid` sıcak ve
saygın bir kelimedir; işlevi, `Hile` ve `Fitne` gibi soğuk kelimelerin yanında
**gerilim üretmektir**. Gerilim üretecek bir şey yoksa cihaz boşa ateşlenir ve
okuyucu olmayan bir ironi arar. Bu yüzden ahlaken saf yollarda `Üstad` kullanılır.

- `Hile Mürşidi` — Kapkaççı Yolu S3
- `Fitne Mürşidi` — Avukat Yolu S5
- `Adalet Üstadı` — Ozan Yolu S3 _(Güneş yolu ahlaken saftır)_

Kural yolun ahlaki muğlaklığına bakar, adına değil.

**`Efsuncu` üç yerde ve tesadüf değil.** Garabet Efsuncusu (Kâhin S4), Sır
Efsuncusu (Çırak S4), Ruh Efsuncusu (Uykusuz S5). Tekrar, bu üç Yol arasındaki
kanonik tarihsel bağı yankılar. **Bu bağın dışındaki yollarda kullanılmamalıdır**.
Avcı Yolu S2 bu yüzden `Bora Efsuncusu` değil `Bora Kamı`dır.

**Sıcak kelime + karanlık kelime.** Genel bir cihazdır: Felaket Müjdecisi, Fitne
Arıtan, Meczup. Amaç ironi değil, çözülmemiş bir gerilimi kelimenin içinde
tutmaktır.

---

## 6. Araç sözleşmesi

### 6.1 `searcher.py`

İngilizce ciltleri tarar, `rapor.tsv` üretir. `bolum_siniri`'yi yalnızca raporun
`mevcut` sütununda gösterir.

> **Bilinen sorun.** `str(... or "")` kullandığı için **`0` değeri boş dize
> olarak basılır.** Raporda "kasten kapısız" ile "değer girilmemiş" ayırt
> edilemez. Şu an 27 terim etkileniyor. Yalnızca insan okuduğu sütunu etkiler.

### 6.2 `etiketle.py`

`rapor.tsv`'den `kaynak` / `mudahale` / `metinde` / `denetim` alanlarını yazar.
`ruamel.yaml` kullanır çünkü PyYAML `# ---` bölüm başlıklarını siler, anahtarları
alfabetik sıralar ve uzun dizeleri yeniden sarar; dosya anlamca aynı kalır ama
diff okunamaz hâle gelir.

> **Aynı hata bu dosyada bir kez yapıldı.** Sürüm 2 geçişi önce PyYAML ile
> yazıldı ve 24 bölüm başlığı yorumu silindi. Geçiş satır düzeyi düzenlemeyle
> yeniden yapıldı. **`sozluk.yml`'i asla PyYAML ile yeniden yazmayın.**

> **Tek yön kuralı.** `if tarayici and mevcut and tarayici > mevcut` — bölüm
> numaraları yalnızca ileri gider. Yüksek bir değere park edilmiş bir girdi
> araçla düzeltilemez (bkz. §4.3).

### 6.3 `denetci2.py`

Yayımlanmış Türkçe bölümleri sözlüğe karşı denetler.

`SON_BOLUM` sabiti burada tanımlıdır ve `bolum_siniri >= SON_BOLUM` olan adlar
kapı denetiminden **çıkarılır**. Sebep: bu eşikteki 24 addan 15'i gündelik
Türkçe kelimedir (Ana, Ay, Kapı, Ölüm, Karanlık, Güneş, Şan, Keşiş...) ve her
bölümde yanlış pozitif üretirler. Sürüm 1'de bu iş `!= 9999` ile yapılıyordu.

> **Kabul edilen kör nokta.** Bu istisna, gerçek bir sızıntıyı da kaçırır:
> _Soytarı_ 50. bölümde geçse araç sessiz kalır. Takas bilinçlidir. Gündelik
> kelimelerde sessizlik, finale ait adlarda kapsam kaybı karşılığında alınmıştır.

> **Ölü kod.** `sozluk_yukle`, `eski_karsiliklar` alanını okur. Bu alan şemada
> yoktur ve hiç var olmamıştır. "Eskimiş karşılıklar" denetimi hiçbir zaman veri
> görmemiştir; **temiz raporlaması boş olduğu içindir, doğru olduğu için değil.**

### 6.4 `sozluk.html`

`SON_BOLUM` JS sabiti burada da tanımlıdır. Kapı mantığı `ogeAcikMi()`
içindedir ve iki ekseni birlikte uygular. `karma`, `yazar_beyani` ile aynı
anahtara bağlıdır (§4.4).

---

## 7. Değişiklik günlüğü

**Sürüm 2 — 2026-07-24**

- `spoiler` alanı kaldırıldı; `bolum_siniri > 0` ile türetiliyor.
- `9999` sentinel değeri kaldırıldı; tüm değerler gerçek bölüm numarası.
- `kaynak` ikinci bir kapı eksenine dönüştü; CoI ve metin dışı içerik varsayılan
  olarak kapalı.
- "Seriyi bitirdim" 9999 yerine 1409 yazıyor.
- `birlestirme` için rozet eklendi (daha önce hiç gösterilmiyordu).
- Mertebe adları aramaya dahil edildi (`data-mertebeler`).
- Spoiler durumu açılır menüsü kaldırıldı, yerine kaynak anahtarları geldi.
