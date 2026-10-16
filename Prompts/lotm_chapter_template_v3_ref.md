# Çıktı Şartnamesi — Bölüm Açılış Şablonu

Bu dosya, üretilecek şablonun **birebir yapısıdır**. Başlıklar, sıralama ve boş-durum talimatları burada bağlayıcıdır. SKILL.md yöntemi anlatır; bu dosya biçimi dikte eder.

Şablonun iskeleti aşağıda, ikinci `---` çizgisinden sonra başlar. Hemen altındaki **Makine sözleşmesi** şablona kopyalanmaz; iskeletteki A.1, A.2, A.3 ve B hücrelerinin nasıl doldurulacağını bağlar.

---

## Makine sözleşmesi (şablona kopyalanmaz)

Şablonun iki okuru var: çevirmen ve `kapanis_denetle.py`. Betik bitmiş bölümü A.1, A.2, A.3 ve B'ye karşı otomatik denetler. Bu kurallar, onun okuyabildiği biçimi tanımlar. Kurala uymayan bir hücre hata vermez, sessizce yanlış aranır: ya her bölümde yanlış alarm verir ya da hiç denetlenmez. İlke tektir: **Türkçe hücresi makine içindir, çevirmene yazılan her açıklama Not sütununa gider.**

**Dosya ve başlıklar**

- Dosya adı `Ch_<N>.md`, sıfır doldurmasız: `Ch_47.md`, `Ch_5.md`. Bakım zinciri şablonu bu adla arar.
- A.1, A.2, A.3 ve B başlıkları iskeletteki metinle aynen yazılır. Makine bölümü başlığın başından tanır: "A.1", "A.2", "A.3", "B. DONDURULAN".
- Bu dört bölümün içinde `##` ya da `###` ile başlayan satır açılmaz; bölümü orada keser ve kalan tablo kaybolur. Alt başlık gerekiyorsa kalın satır kullanılır (A.3'teki **Örtük kalanlar** gibi).
- Her bölümde tek tablo. İlk satır başlık sayılır; ikinci bir tablonun başlık satırı veri diye okunur.
- Hiçbir hücrede `|` ya da `<br>` kullanılmaz. `|` sütunları kaydırır; `<br>` hücreyi kalıp tarifine çevirir. Birden fazla dize gerekiyorsa her biri ayrı satırdır.

**A.1 ve A.2: Türkçe hücresi**

- Yalnızca metinde aranacak biçimi taşır. ¶ atfı, açıklama ve etiketler (`[BURADA DONUYOR]`, `[YENİ]`, `[TEREDDÜT]`) Not ya da Etiket sütununa gider; Türkçe hücresine yazılan etiket aranacak dizenin parçası olur.
- Terimin bu bölümde birden fazla biçimi geçiyorsa biçimler `/` ile ayrılır: `İhtiyar Neil / Bay Neil`. Makine her biçimin bölümde geçtiğini **ayrı ayrı** doğrular. Yani `/` "ya da" değil "hepsi" demektir; bölümde geçmeyecek bir biçim hücreye yazılmaz.
- Terim bölümde fiilen geçmelidir: makine her A.1 ve A.2 satırının metinde bulunduğunu sınar. Yalnızca yasaklamak ya da açıklamak için satır açılmaz; yasak A.3'ün, açıklama E'nin işidir.
- Fiil mastarla değil, gövde ve tireyle yazılır: `havale et-`, `rol yap-`. Mastar biçimi, metindeki çekimli geçişlerle eşleşmez.
- Parantez içini makine siler. Kısa bir niteleme için kullanılabilir (`Kilise (tekil)`), ama aranacak bir biçim paranteze konmaz.
- Türkçe hücresinde çift tırnak ve boşluklu uzun çizgi ( — ) kullanılmaz. Tırnak varsa makine yalnızca tırnak içini arar; uzun çizgiden sonrasını not sayıp atar.
- Kesme işareti düz yazılır: `O'na`. Kıvrık kesme (’) tırnak sanılır.
- `[TEREDDÜT]` sözcüğü yalnızca A.2'nin Etiket sütununda geçer; bir notta geçerse satır denetimden düşer. TEREDDÜT satırları makinece hiç denetlenmez, çünkü karar insanındır. Denetlenmesi gereken bir karar TEREDDÜT olarak bırakılmaz.

**A.1 ve A.2: İngilizce hücresi**

- Makine bu hücreyi çeviriye sızıp sızmadığını görmek için arar. Tek bir İngilizce ifade ya da `/` ile ayrılmış biçimler yazılır; ¶ atfı ve açıklama parantez içinde kalabilir.
- İngilizce ifade aynı zamanda bir Türkçe kelimeyse (sofa, bar, fan) tanımlıkla yazılır: `the sofa`. Yoksa Türkçe metindeki kelime sızıntı diye raporlanır.

**A.3: makine yasağı**

- **Kalın blok + içinde "yasak" ya da "yazılmaz" = bölüm genelinde makine yasağı.** Bloğun içindeki her çift tırnaklı dize yasaklanır: `**"tarikat" yasak.**`. Başka fiil (yok, kullanılmaz, girmez, sokulmaz) kullanılmaz; makine bunları ya hiç tanımaz ya da yasağı okuyup istisnasını okumaz.
- Makine yasak dizenin **başını** arar, sonunu Türkçe ekler için açık bırakır; sert ünsüzü yumuşamış biçimi de arar (ekip/ekibi). Bu yüzden "hafi" yasağı "hafif"i de yakalar. Yasak, bölümde meşru geçen bir kelimenin başıysa makine yasağı olarak yazılmaz; düz cümleyle yazılır ve elle denetlenir.
- Küçük harfle başlayan yasak harf duyarsız, büyük harfle başlayan harf duyarlı aranır. "Aptal" yasağı Soytarı'nın eşanlamlısını yakalar, sıradan "aptal" sıfatını yakalamaz.
- Yalnızca bir ¶'a ait yasak ve bağlama bağlı her kısıt kalın yazılmaz. Örnek: ¶33'te Basiret yanlış, ¶69'da doğru terimse, bu kısıt düz cümleyle yazılır; kalın yazılırsa ¶69'da yanlış alarm verir.
- İzinli bir terim yasak dizeyi içeriyorsa (yasak "silindir", izinli "silindir şapka"), izinli biçim aynı maddede, kalın bloğun **dışında**, çift tırnakla yazılır; makine yasağı aramadan önce onu metinden maskeler. Bu yüzden makine yasağı taşıyan bir maddede, istisna olmayan hiçbir şey çift tırnakla yazılmaz. Kelimelere değinmek için düz tek tırnak kullanılır: 'gizli teşkilat'.
- A.1 ve A.2'deki izinli karşılıklar zaten maskelenir: "Tarikat-ı Hafiyye" A.1'deyse "tarikat" yasağı onu yakalamaz.
- **Örtük kalanlar** kısmında kalın + yasak fiili kullanılmaz; oradaki kısıtlar bağlama bağlıdır.

**B: dondurulan satırlar**

- Sütunlar sırasıyla: İngilizce, Türkçe (dondurulmuş), geçiş sayısı, Not. Sayı hücresi bir tamsayıyla başlar; ¶ listesi ardından gelebilir: `3 (¶17, ¶19, ¶20)`.
- Sayı, dizenin bölümün tamamında **harfi harfine ve büyük/küçük harf dâhil** kaç kez geçtiğidir. Başka bir satırın ya da alıntının içindeki geçişler de sayılır; bu yüzden bir dize hem tek başına hem daha uzun bir dondurulmuş satırın parçası olarak dondurulmaz.
- Geçişlerden biri cümle başına düşebiliyorsa kalıp, büyük harf alabilecek ilk kelimeden değil bir sonrakinden başlar (`küsur yıl`, `Kızıl Ay şeklini çiz-`). Ya da cümle başındaki geçişlere ayrı satır açılır.
- Türkçe hücresinde yalnızca aranacak dize durur; ¶ atfı ve karara bağlanmış tam cümle Not'a gider. Hücrede çift tırnak varsa makine yalnızca tırnak içini arar.
- Fiil gövdesi tireyle biter (`dokun-`): bütün çekimleri eşler.
- Üç nokta (... ya da …) ya da ok (→) taşıyan hücre kalıp tarifi sayılır. Dondurulmuş satırın kendisi üç nokta içeriyorsa üç noktanın iki yanı ayrı çift tırnaklı parçalar olarak yazılır: `"Hım" … "peki"`. Makine parçaları sırayla ve arada en fazla 60 karakterle arar. Tek parçalı ya da tırnaksız bir tarif makinece denetlenemez, elle denetlenir.
- Jest satırı düzyazı tarifi değil, metinde geçecek çekirdek dizedir: `dört kez dokun-`.

**Teslimden önce**

Son iş olarak A.1, A.2, A.3 ve B bu sözleşmeye karşı bir kez okunur. Her Türkçe hücre metinde aynen aranabilir mi? Her kalın yasak, bölümde meşru geçen bir kelimeyi de yakalar mı? Her B sayısı, büyük/küçük harfiyle birlikte doğru mu?

---

# Gizemlerin Efendisi — Bölüm Açılış Şablonu

**Bölüm [N] — [Türkçe Başlık] ([English Title])**

Bu şablon, Sabit Çekirdek'in altına eklenir ve o bölüm için **tek ek kaynaktır**. Burada bulunmayan hiçbir bilgiye ihtiyaç duyulmamalıdır.

Şablonun tamamı **Latin harfleriyle** yazılır. Kaynak metindeki Çince ifadeler şablona kopyalanmaz; ¶ numarası ve Türkçe anlamıyla anılır. Bu, biçimsel bir tercih değil: şablon çevirmenin önündeki son belgedir ve içindeki her yazı sistemi çıktıya sızma ihtimali taşır.

---

## A. TERİMLER VE ÖZEL ADLAR

### A.1 Yerleşik terimler (değiştirilemez)

Karşılığı **daha önce karara bağlanmış** ve bu bölümde fiilen geçen terimler; kaynağı sözlük, ses haritası, önceki bir bölüm şablonu veya yayımlanmış bir bölüm olabilir. Bu karşılıklar **aynen** kullanılır.

Bu tablo aynı zamanda **denetim yüzeyidir**: sondaki liste yalnızca burada yazan terimi denetleyebilir. Türkçesi apaçık olsa bile birden fazla tabii eşanlamlısı bulunan ve bölüm içinde tekrarlanan terimler (toplantı, formül, mahzen) tabloya girer.

| İngilizce | Türkçe     | Kullanım notu                       |
| --------- | ---------- | ----------------------------------- |
| [Terim]   | [Karşılık] | [¶ numarasına bağlı kısıt; yoksa —] |

Romanda **ilk kez bu bölümde** geçen bir terim `[BURADA DONUYOR]` ile işaretlenir: çevirmen hangi satırı uyguladığını değil, hangisini kurduğunu bilmelidir.

### A.2 Bu bölümde karara bağlanan özel adlar

Karşılığı daha önce karara bağlanmamış, bu bölümde geçen adlar. Karşılıklar burada verilmiştir; çevirmen yenisini üretmez.

| İngilizce | Türkçe     | Etiket                     | Not                  |
| --------- | ---------- | -------------------------- | -------------------- |
| [Ad]      | [Karşılık] | `[YENİ]` veya `[TEREDDÜT]` | [gerekçe, tek cümle] |

### A.3 Metne eklenmeyecek

**Örtük kalanlar**
[Bölümün kasten adlandırmadığı, çevirmenin refleksle dolduracağı kurum/kişi/kavram. Yoksa "yok" yaz.]

**Komşu terim çarpışmaları**
[Bu bölümdeki sıradan bir kelimenin, mıknatıs gibi çekeceği rezerve terim. Yanlış terim açıkça adlandırılır ve yasaklanır. Makinenin denetleyeceği yasak Makine sözleşmesindeki biçimle yazılır; ¶'a bağlı yasak düz cümleyle. Yoksa "yok" yaz.]

---

## B. DONDURULAN SATIRLAR

Bu satırlar bölüm içinde ve sonraki ciltlerde tekrarlanır. **Her geçişte birebir aynı** yazılır; eşanlamlı çeşitleme yasaktır.

| İngilizce | Türkçe (dondurulmuş) | Bölümdeki geçiş sayısı | Not                                                   |
| --------- | -------------------- | ---------------------- | ----------------------------------------------------- |
| [Satır]   | [Türkçe]             | [n (¶…)]               | [neyin kaymayacağı: sözcük sırası, noktalama, tırnak] |

Yüzlerce bölüm tekrarlanacak **fiziksel bir jest veya ayin edimi** de dondurulan satırdır; düzyazı olması bunu değiştirmez.

[Dondurulacak satır yoksa: "Bu bölümde tekrarlanan sabit satır yok." yaz ve tabloyu düşür.]

---

## C. AKTİF SES HARİTALARI

**Pürüzsüz-Yüzey Ayrımı (zorunlu).** Bu bölümde pürüzsüz, yüksek sicilli bir tam-performans maskesi aktifse, o maskenin steady-state ayırt edici çizgisini ilgili "Ses Kuralları" bloğuna **açıkça** yaz — bölümde başka bir pürüzsüz maske bulunmasa dahi. Karşılaştırma hedefi sahnedeki bir karakter değil, başka ciltteki bir maskedir. **Hiçbir maske aktif değilse bunu açıkça belirt ve uyarıyı ters kur:** bu bölümde hangi seslerin yüksek sicile kaymaması gerektiğini yaz.

**Sahnede hakiki bir üst sınıf muhatap varsa** ayrımın yükseklikle taşınamayacağını da yaz: ikisi de aynı dönem dağarcığını kullanır, maskeyi ele veren şey kusursuzluğudur. Hangi karakterin tökezlemesine izin verildiğini adıyla belirt.

**Maske çatlıyorsa** çatlamanın hangi kadranda başladığını söyle: önce nezaket formülleri ve nominal fiiller mi düşüyor, yoksa cümle boyu mu kısalıyor.

[Bölümde konuşan veya iç sesi duyulan her karakter için:]

---

### [Karakter Adı]

**Mevcut Aşama / Maske:** [Aşama numarası + **tek cümlelik tarifi**. Çevirmen aşama numarasının ne anlama geldiğini bilmiyor; numara tek başına yazılmaz.]

**Basınç okuması:** [Sahne şu üçünden hangisinde: *henüz-olmamış / olmakta / çoktan-olmuş*. Buradan motorun aldığı işlev çıkar: kalkan · kaldıraç · silah · çelik · durma. Basınç yoksa "basınç yok" yaz — motor yine de tam ses seviyesindedir.]

**Bu Bölümdeki Psikolojik Durum:**
[Tek paragraf. Geçiş yaşanıyorsa veya maske beklenmedik bir anda çatlıyorsa belirt.]

**Kalibrasyon çizgisi (illüstratif — metne eklenmez):**
_"[Tonu tek cümlede duyuran Türkçe örnek replik.]"_

**Sicil kadranları:** (dört taşıyıcı zorunlu, karaktere özgü olanlar altına eklenir)

- **Fiil kaydı:** [yalın / nominal birleşik]
- **Kiplik:** [gündelik rivayet / hedgelenmiş resmiyet]
- **Ünlem ve kendini bölme:** [var / yok]
- **Nezaket formülü:** [var / yok]
- **Karaktere özgü:** [yalnızca o sesi tanımlayan gramer kısıtı. Yoksa "yok" yaz.]

Değer bir koşula bağlıysa koşul yazılır ("muhataba göre: X'e karşı nominal, Y'ye karşı yalın"); örnek sözcük yazılmaz.

**Ses Kuralları (yalnızca bu bölüm için aktif olanlar):**

- **İç ses:** [maddeler; kural adı değil, kuralın kendisi, ¶ numarasına bağlı]
- **Diyalog:** [maddeler]
- **Osmanlı çıpası:** [açık / kapalı / yalnızca şu bağlamda açık]
- **Dikkat:** [bölüm olaylarına özgü uyarılar]

**Kapalı siciller (bu bölümde yasak):**

- [Karakterin genel profilinde bulunan ama burada işlemeyen tik, sözcük alanı veya davranış. Her madde kısa bir sebep taşır.]
- **Cırcır kontrolü:** [tik tik: hangisi canlı, hangisinin kapısı kapandı, hangisi canlı ama bu bölümde tetiklenmiyor. Kapısı kapanmış tik bir gönderme değil, süreklilik hatasıdır; tetiklenmemiş tik ise aşamayı ispatlamak için metne sokulmaz. **Cırcır yalnızca bu karakterin tikini yönetir**; kaba dil dâhil hiçbir kısıt sahneye toptan uygulanmaz, her ses için ayrı belirtilir.]

**Dayanak:** [Bu bloktaki kuralların ne kadarı ses haritasından geliyor, ne kadarı çıkarım? Haritanın ince olduğu aşamalarda açıkça yaz: "aşama tarifi iki satır; kalibrasyonun büyük kısmı tik envanterinden türetildi." Bu, haritanın nerelerinin yazılması gerektiğini zamanla kendiliğinden gösterir.]

---

### Sahnede olan ama konuşmayan

[İsimler + ses haritalarının etkin olmadığı beyanı: bu karakterlere replik veya iç ses uydurulmaz. Yoksa "yok" yaz.]

---

## D. HİTAP TABLOSU

Bu bölümde geçerli hitap biçimleri. Sabit Çekirdek'in genel hitap kurallarının bu bölüme uygulanmış hâlidir; çevirmen samimiyet seviyesini yeniden hesaplamaz.

| Konuşan | Muhatap | Hitap               | Not                    |
| ------- | ------- | ------------------- | ---------------------- |
| [Kişi]  | [Kişi]  | [Biçim + *sen/siz*] | [değişim varsa sebebi] |

Anlatıcının her karakteri nasıl andığı da tabloya girer. Kasıtlı uyuşmazlık (sesli _siz_, içten _sen_) bir karardır; düzeltilmez, not edilir.

---

## E. BÖLÜME ÖZEL NOTLAR

Her madde, çevirmenin metinde karşılaşacağı somut bir kararla bağlantılı olmalıdır; genel edebi tavsiye yazma.

- **Kaynak metin uyuşmazlıkları:** [ZH/EN ayrışmaları; hizalama kayması varsa başladığı ¶ ve İngilizce haritasının nereden itibaren geçersiz olduğu]
- **Halk ağzı / sınıf sesleri:** [seyyar satıcı, denizci, hizmetli gibi sesler varsa belirt: bunlar nötr-modern Türkçe değil, kendi kaydı olan bir sicildir.]
- **Yankı Defteri kontrolü:** [kurulum / ödeme / tekrar / erken harcanmaması gereken yay]
- **Gotik sözcük tahsisi:** [gotik dağarcığın harcanacağı ¶ aralıkları ve **aç bırakılacak** bölge. Dönem dağarcığı kotasızdır, tahsise girmez. Bölümün duygusal doruğu varsa, oranın **sade** kalması gerektiğini ayrıca yaz.]
- **Algı fiili yığılması:** [bölüm baştan sona görme/sezme/fark etme üzerine kuruluysa belirt ve stratejiyi ver: edimi düşürme, algıyı bedene kaydırma.]
- **Chengyu ve kalıp ifadeler:** [bölümde geçen dört karakterli deyimler ve karara bağlanmış Türkçe çözümleri]
- **Sürtünme noktaları:** [Kaynağın yapısı yüzünden kırılması beklenen üç ila beş cümle. Her biri için uyarı değil, **karara bağlanmış Türkçe cümle** yazılır. Tipik iki sınıf: "mesele şuydu ki" kabilinden menteşe cümleleri ve Türkçede ağdalı ama yanlış bir yakın karşılığı bulunan soyut isimler. Geri dönen bir müsveddede fiilen kırılmış cümle varsa, o cümlenin karşılığı zorunludur.]
- **Sıcak noktalar:** [Türkçe sözdiziminde kırılacağı öngörülen cümleler ¶ numarasıyla verilir ve **karara bağlanmış Türkçe karşılığı** yazılır. Bu bölüm için dondurulmuş satır hükmündedir. Yoksa "yok" yaz.]
- **İç ses sınırı:** [Kaynakta serbest dolaylı anlatımla yazılmış, yani iç ses gibi görünen ama üçüncü şahıs anlatı olan paragraflar ¶ numarasıyla listelenir ve **italik değildir** diye açıkça yazılır. Bu bölümde italiğe girecek ¶'lar da ayrıca sayılır. Ölçüt tektir ve şablonda yazılır: cümlenin başına "Ben" konabiliyorsa iç sestir; cümle düşünen kişinin adını yahut "kendisi" sözünü taşıyorsa anlatıdır. Persona adlarının tırnaklı mı tırnaksız mı yazıldığı da bu maddede tek satırla beyan edilir.]
- **Yapısal ritim, lore düşüşleri, psikolojik kaymalar**

---

## DENETİM LİSTESİ

Çeviri bittikten sonra, **ayrı bir geçişte** işletilir. Bu bir üslup turu değildir; hiçbir maddesi düzyazıyı yeniden yazmayı gerektirmez. Yaratıcı geçişle aynı anda yapılırsa ikisi de zayıflar.

1. **Latin harfi.** Çıktıda Latin harfi dışında tek bir karakter kalmadığını doğrula.
2. **İtalik.** E bölümündeki iki listeyle karşılaştır. İtaliğe alınmış her cümlenin başına "Ben" koyup oku; olmuyorsa italik kalkar.
3. **Dondurulan satırlar.** B bölümündeki satırları metinde bul ve harfi harfine karşılaştır.
4. **Terimler.** A.1 ve A.2'deki karşılıkların her geçişte aynı olduğunu doğrula. Tabloda olmayan bir terim bu maddeyle denetlenemez; bölüm boyunca birden fazla geçen her terimin satırı bulunmalıdır. [Bu bölümde kaymaya en müsait olanlar adıyla sayılır.]
5. **Tırnak.** Persona adlarının tutarlı yazıldığını doğrula.

---

**[ÇIKTI SONU]**

Bölüm metnini yazma. Denetim listesinden sonra üretimi durdur.
