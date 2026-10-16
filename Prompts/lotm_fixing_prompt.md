# Gizemlerin Efendisi — Düzeltme Geçişi (v1)

Bu, çeviri prompt'u **değildir**. Bu geçiş zaten çevrilmiş bir bölümü alır ve
yalnızca **yapıyı ve imlâyı** düzeltir.

---

## 0. KAPSAM — ÖNCE BUNU OKU

Bu geçişin izin verildiği tek şey **paragraf sınırları, diyalog noktalaması
ve şapka kararlarıdır.**

**Kesinlikle dokunulmaz:**

- Sözcük seçimi. Daha iyi bir fiil aklına geliyorsa **kullanma**.
- Kayıt. Anlatının arkaikliği, Klein'ın iç sesindeki argo — olduğu gibi kalır.
- Terminoloji. Sözlükteki hiçbir karşılık değiştirilmez, "iyileştirilmez".
- Cümle yapısı. Uzun cümle bölünmez, kısa cümle birleştirilmez.
- İtalik blokların **içeriği**. Yalnızca konumları/sınırları denetlenir.
- Bilgi. Hiçbir şey eklenmez, hiçbir şey çıkarılmaz.
- **Çıktıya kaynak/atıf işareti eklenmez.**

**Ölçüt:** yaptığın her değişiklik, metnin iki hâlini yan yana koyan birine
"bu bir kural ihlaliydi" diye gösterilebilmeli. "Böylesi daha güzel oldu"
bir gerekçe değildir ve bu geçişte reddedilir.

Emin değilsen **dokunma** ve §5'teki listeye yaz. Bir kaçırılmış düzeltmenin
bedeli küçüktür; sessizce yapılmış yanlış bir düzeltmenin bedeli, bir sonraki
okumada kimsenin fark etmemesidir.

---

## 1. NE SANA GELMEZ

Şu dört iş **betiklerle** yapılır, çünkü kararı makine verebilir ve tekrar
edilebilir olması gerekir. Bunlarla uğraşma, bu geçiş onları görmez bile:

| İş                                                                                                                         | Araç                                |
| -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| Kıvrık kesme `’` → düz `'`                                                                                                 | `perl -CSD -i -pe "s/\x{2019}/'/g"` |
| Damaksıllaşma ve uzunluk şapkası (kâğıt, hâlde, âdeta…)                                                                    | `sapka.py --uygula`                 |
| Kesin geçişli karşılıklar (`ritüel` → ayin, 28'den; `mistisizm` → İlm-i Esrar, 18'den; geçişten önce eski kelime doğrudur) | `sozluk_lint.py` (`kesin_gecis`)    |
| Özel ad ek uyumu (`Alger'in` → `Alger'ın`)                                                                                 | `sozluk_lint.py --sadece ek-uyumu`  |

Sana yalnızca **karar gerektirenler** kalıyor.

---

## 2. PARAGRAF SINIRLARI

### 2.1 Varsayılan: anlatı + KENDİ repliği birleşir

Bir repliği hazırlayan hareket, bakış ya da jest, repliğin kendisiyle aynı
paragrafta durur. Çince bu ikisini ayırır; bu Çince'nin dizgi teamülüdür,
Türkçeye taşınmaz.

> İhtiyar Neil şaşkınlıkla ona bir göz attı. "Doğrudan talep edebilirsin ya!"

### 2.2 ÜÇ SINIR — bunlar birleştirmeyi durdurur

Bu kural en sık **fazla uygulanarak** bozulur. Aşağıdaki üç durumda
birleştirme **yapılmaz**:

**(a) Özne değişiyorsa.** Bir paragraf ortasında eyleyen değişmez.

> ✗ Gelişigüzel birkaç sembol daha çizdi. Klein bir yandan ezberlerken…
>
> Neil çiziyor, Klein ezberliyor. İki paragraf.

**(b) İki taraf da anlatıysa.** Kural anlatıyı **repliğe** bağlar, anlatıyı
anlatıya değil.

> ✗ İhtiyar Neil güldü, zinciri çöze çöze yerine oturdu. Yüzü çarçabuk
> durgunlaştı. Zinciri tuttuğu sol elini uzatarak…
>
> "Yüzü çarçabuk durgunlaştı" bir dönüş anıdır; kendi paragrafında durur.

**(c) Duraklamanın kendisi anlam taşıyorsa.** Bir eşiğin önünde, bir
itirafın öncesinde, esprinin düşüşünde.

> ✓ İhtiyar Neil bir an duraladı, birden elini ağzına kapatıp alçak sesle
> haykırdı.
>
> "Götürüp döksene şunu hemen!"
>
> Bölümün şakası tam da o boşlukta. Çince `低声吼道：` diyor, yani mekanik
> kural birleştir diyor — ve burada mekanik kural yanılıyor.

### 2.3 Diğer paragraf kuralları

- Farklı konuşmacılar aynı paragrafa konmaz. Her konuşmacı kendi paragrafını
  alır.
- Sahne kesmesi tek satırlık `...`.
- İtalik iç ses, düşünenin kendi anlatısıyla (jest, bakış, tepki, kendi
  repliği) aynı paragrafta durabilir; italik kapanışından sonra bir boşluk
  bırakılır. Bu geçiş böyle bir paragrafı yalnızca iki durumda böler:
  özne değişiyorsa (§2.2a) veya aynı blokta başka bir konuşmacının repliği
  varsa. Kendi paragrafında duran bir iç sesi anlatıya **birleştirmez**:
  çevirmen onu ayırdıysa duraklama bilinçlidir (§2.2c).

---

## 3. DİYALOG NOKTALAMASI

Bunlar tartışmasızdır; bulduğun her örneği düzelt.

| Yanlış                      | Doğru                                       |
| --------------------------- | ------------------------------------------- |
| `"Hallettin," dedi;`        | `"Hallettin." dedi`                         |
| `…bir yudum içti:` + replik | `…bir yudum içti. "Acı kahve sever misin?"` |
| `— Replik` (uzun çizgi)     | `"Replik"`                                  |
| Atıftan sonra iki nokta     | Nokta; replik aynı paragrafta devam eder    |

Repliğin **içinde** sıralama için iki nokta serbesttir:
_"İki seçeneğin var. Birincisi: kendin dışarı tırman."_

---

## 4. ŞAPKA — YALNIZCA KARAR GEREKTİRENLER

`sapka.py` mekanik olanları zaten uyguladı. Sana iki grup kalıyor.

### 4.1 Nisbet -î — her geçiş ayrı okunur

Bu bir imlâ değil, **anlam** meselesidir:

| şapkalı | manası     | şapkasız | manası              |
| ------- | ---------- | -------- | ------------------- |
| resmî   | official   | resmi    | onun resmi          |
| tarihî  | historical | tarihi   | onun tarihi         |
| askerî  | military   | askeri   | askeri (nesne hâli) |
| hayalî  | imaginary  | hayali   | onun hayali         |
| madenî  | metallic   | madeni   | madeni (nesne hâli) |
| dinî    | religious  | dini     | onun dini           |
| ilmî    | scientific | ilmi     | onun ilmi           |

> "genelgeçer bir **tarihî** bilgi" — sıfat
> "bin yıllık **tarihi** boyunca" — iyelik, şapkasız kalır

### 4.2 Eşadlılar — bağlama bakılır

`âdet` (görenek) ~ `adet` (sayı) · `âlem` (dünya) ~ `alem` (sancak) ·
`hâlâ` (henüz) ~ `hala` (teyze) · `kâr` (kazanç) ~ `kar` (yağan) ·
`hâle` (hâl+e) ~ `hale` (ayla, nur halkası)

---

## 5. ÇIKTI

İki parça, bu sırayla.

**(1) Düzeltilmiş bölüm.** Tam metin, front matter dâhil.

**(2) Değişiklik dökümü.** Her değişiklik için tek satır:

```
¶14  paragraf  birleştirildi — anlatı + kendi repliği (§2.1)
¶31  paragraf  BİRLEŞTİRİLMEDİ — özne değişiyor (§2.2a)
¶52  noktalama "…içti:" → "…içti." (§3)
¶67  şapka     "resmi üye" → "resmî üye" — sıfat (§4.1)
¶88  ŞÜPHELİ   "tarihi" — iyelik mi sıfat mı, cümle iki türlü okunuyor
```

Döküm **eksiksiz** olmalı. Dökümde olmayan bir değişiklik yapılmışsa bu
geçiş başarısızdır; denetlenemeyen bir düzeltme, düzeltme değildir.

`ŞÜPHELİ` satırları için **metne dokunma**. Karar insanındır.

---

## 6. GÖREV

Sana bir bölüm verilecek. §0'daki kapsamı bir kez daha oku, sonra §5'teki
iki parçayı üret. Bölümü yeniden çevirme, güzelleştirme, kısaltma.

Yapman gereken tek şey: kuralın çiğnendiği yerleri bulmak ve **yalnızca
orayı** düzeltmek.
