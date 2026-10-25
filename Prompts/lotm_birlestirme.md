# Gizemlerin Efendisi — Birleştirme Geçişi (v1)

Bu geçiş yeni bulgu **aramaz**. Dört geçişin (okuma, sadakat, düzeltme, triyaj)
bulgularını tek bir listede birleştirir, her düzeltmeyi sınıflandırır ve
çıktıyı bir betiğin uygulayacağı JSON olarak verir.

Amaç çevirmenin karar yükünü azaltmaktır: kuralı belli olan düzeltme kendiliğinden
uygulanır, gerçekten insan isteyen düzeltme tek bir listede ona gelir, çevirmenin
daha önce verdiği karar bir daha sorulmaz.

---

## 0. GİRDİLER

- `<onceki_kararlar>` (olmayabilir): çevirmenin kalıcı kararları. Her satır
  `kabul` ya da `ret`, bir örüntü adı ve bir örnek taşır.
- `<bolum_sablonu>`: bölüm şablonu. Dondurulmuş ve öngörülmüş satırlar buradadır.
- `<bolum>`: bölümün **şimdiki** Türkçesi. `eski` alanları buradan alınır.
- `<okuma>`, `<sadakat>`, `<duzeltme_fark>`, `<duzeltme_dokum>`, `<triyaj>`:
  geçişlerin çıktıları.

---

## 1. SINIFLAR

Her düzeltme tam olarak bir sınıf alır.

**KESIN**: insan kararı gerektirmeyen düzeltme. Yalnızca şunlar:

1. Sadakat bulgusu, önem derecesi **A** ya da **D**, `(emin değilim)` işareti
   **yok**, satır şablonda dondurulmuş ya da öngörülmüş **değil**, ve bulgunun
   kendi **Düzeltme** satırı var.
2. Okumanın bir `SADAKAT?` sorusunu sadakat geçişi **doğrulamış** ve bir
   düzeltme vermiş (1. maddeyle aynı koşullar).
3. Düzeltme geçişinin farkındaki değişiklikler (`<duzeltme_fark>`), dökümde
   `ŞÜPHELİ` olarak geçmiyorsa. Bunlar kural ihlalidir, üslup değil.
4. Okuma ya da sadakat bulgusu, `<onceki_kararlar>`'daki bir `kabul` satırının
   örüntüsüne **açıkça** uyuyorsa. Uyum tartışmalıysa KARAR'dır.

**KARAR**: çevirmenin vereceği karar. Okuma geçişinin üslup bulgularının
tamamı (1.1–1.11, 1.M), deftere uymadığı sürece. `(emin değilim)` işaretli
her sadakat bulgusu, B ve C bulguları. Aynı cümleye iki geçiş **farklı**
düzeltme önermişse ikisi tek maddede birleşir ve KARAR olur.

**SABLON**: düzeltme şablonda dondurulmuş ya da öngörülmüş bir satıra
dokunuyor. Metin değiştirilmez; bu, şablon için geri bildirimdir.

**Defterdeki ret:** bir bulgu `<onceki_kararlar>`'daki bir `ret` satırının
örüntüsüne açıkça uyuyorsa listeye **hiç konmaz**; `bilgi`'ye tek satır
yazılır: `defter: ret — <örüntü>`.

Şüphede bir alt sınıfa in: KESIN'den emin değilsen KARAR. Yanlışlıkla
uygulanan bir düzeltmenin bedeli, bir kez daha sorulan bir sorudan büyüktür.

---

## 2. ALANLAR

- `eski`: `<bolum>`'den **harfi harfine** kopyalanan en kısa parça; yalnızca
  değişen cümle. Büyük-küçük harf, kesme, şapka, tırnak ve noktalama dâhil
  hiçbir şey normalleştirilmez. Bölümde **tam bir kez** geçecek kadar uzun
  olmalı. Bulgunun `✗` ya da `TR` satırı bölümle birebir uyuşmuyorsa bölümdeki
  hâli esas alınır.
- `yeni`: `eski`'nin yerine geçecek metin, geçişin **Düzeltme** / `✓` satırından
  **harfi harfine**. Sen yeniden yazmazsın, "daha iyi" bir biçim önermezsin.
  Geçişin önerisi bölüme birebir oturmuyorsa ya da onu uyarlaman gerekiyorsa
  madde KESIN olamaz, KARAR'dır; `neden`'e uyarlamayı yaz.
  Bir cümleye iki düzeltme düşüyorsa: ikisi cümlenin ayrı parçalarına
  dokunuyor ve ikisi de olduğu gibi uygulanabiliyorsa tek çiftte birleşir;
  birleştirmek için sözcük eklemen ya da çıkarman gerekiyorsa KARAR.
  Yeni metin okuma geçişinin işaretlediği bir örüntüyü (noktalı virgül zinciri,
  -en X, girişi vb.) yeni baştan **doğurmamalı**; doğuruyorsa KARAR.
- `p`: okuma ¶'si (bölümde front matter hariç boş satırla ayrılan blok numarası).
  Sadakat ¶'si hizalama grubudur ve bundan farklı olabilir; içerikten okuma ¶'sini bul.
- `kaynak`: bulguyu veren geçişler: `okuma`, `sadakat`, `duzeltme`.
- `kural`: kısa, **tekrar kullanılabilir** örüntü adı. Defterle eşleşme bu ada
  dayanır, o yüzden bölüme özgü değil kalıba özgü yaz ve her bölümde aynı
  kalıba aynı adı ver. Okuma bulgularında maddenin numarası ve adı
  (`okuma 1.7 boş "konuştu"`), sadakat bulgularında harf ve konu
  (`sadakat A düşmüş zarf`), düzeltme geçişinde bölüm numarası
  (`düzeltme §2.1 anlatı+replik birleşir`).
- `neden`: tek cümle; KARAR'da çevirmenin karar vermek için bilmesi gereken.

Metin değişikliği önermeyen her şey `bilgi`'ye gider: okumanın `ŞÜPHELİ`
satırları, sadakatin "kaynakla uyumlu" cevapları, triyajın bakılacak
maddeleri ve komutları, düzeltme geçişinin kapsam dışı notları.

---

## 3. ÇIKTI

Yalnızca tek bir JSON bloğu. Öncesinde ya da sonrasında yazı yok.

```json
{
  "duzeltmeler": [
    {"p": 24, "sinif": "KESIN", "kaynak": ["okuma", "sadakat"],
     "kural": "sadakat D kişi eki uyumu",
     "eski": "…bölümden birebir…", "yeni": "…",
     "neden": "Aynı özne iki ayrı kişi eki alıyor; iki geçiş aynı düzeltmeyi verdi."}
  ],
  "bilgi": [
    {"p": 29, "not": "okuma ŞÜPHELİ: \"alçak ve ağır bir sesle\" ¶22'de de geçiyor."},
    {"p": null, "not": "triyaj: python3 bicim_denetle.py 60 --bak"}
  ]
}
```

Düzeltmeler ¶ sırasıyla. Bir bulguyu atlama: her bulgu ya `duzeltmeler`'de ya
`bilgi`'de bir kez yer alır.
