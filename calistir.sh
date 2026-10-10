#!/usr/bin/env bash
# ============================================================
#  calistir.sh -- bakim zinciri
#
#  Betiklerin arasinda gercek bagimliliklar var ve sirasi onemli:
#
#     lotm.py          (numaralandirma dogrulamasi -- hepsinin temeli)
#     kapi_denetle.py  Source/LotM_Volumes  ->  Reports/rapor.tsv
#     etiketle.py      rapor.tsv            ->  _data/sozluk.yml
#     yayim_denetle.py sozluk.yml + _chapters -> Reports/denetim.txt
#     lint/sozluk_lint.py  sozluk.yml + kurallar + _chapters -> ekrana
#     bicim_denetle.py _chapters (+ sozluk.yml, taban) -> Reports/bicim.txt
#                      (dizgi: tirnak, italik, atif, para; normdan sapan bolumler)
#     toplu_denetle.py sozluk.yml + words.md + _chapters -> Reports/toplu.txt
#                      (her terimin yayimlanmis karsiliklari tutarli mi)
#
#  lint/sapka.py zincire YALNIZCA KURU calisir. Zincirdeki her adim rapor
#  uretir; --uygula ise duzyazi yazar ve 'hepsi' bilerek hoosgorulu
#  (adimlar "|| devam" ile sarili). O hoosgoru rapor ureten adimlar icin
#  dogru, dosya yazan bir adim icin degil. Ustelik sapka'nin ciktisi
#  GUVENLI/ELLE diye ikiye ayriliyor cunku ikinci yari her seferinde insan
#  ister; otomatik calistirmak diff'in okunmamasi demek.
#
#  Bolum zinciri ayridir: yukaridaki korpus genelinde ve seyrek calisir,
#  asagidaki tek bir bolum icin, ceviri elden gecerken. Sirasi onemli:
#  hizalama_denetle once gelir cunku ceviri_denetle'nin ESLESMEYEN
#  listesine guvenilip guvenilemeyecegini o soyler. kapanis_denetle
#  bilerek hizalamaya hic bagli degildir, en sona konur. Aradaki
#  toplu_denetle yalnizca o bolumde gecen terimleri o bolum icinde tarar.
#  bicim_denetle de hizalamadan bagimsizdir; kapanis_denetle'den hemen once
#  gelir ve yayin oncesi tek sert kapidir (HATA varsa kirmizi uyari).
#
#      ./calistir.sh          tam zincir
#      ./calistir.sh bolum 44 tek bolum denetimi (ceviri elden gecerken)
#      ./calistir.sh bolum    numarasiz: _chapters'taki en son bolum
#      ./calistir.sh test     testleri calistir (bagimlilik yok, hizli)
#      ./calistir.sh kontrol  sadece numaralandirma dogrulamasi
#      ./calistir.sh denetim  sadece yayim denetimi (hizli, gunluk)
#      ./calistir.sh lint     tutarlilik denetimi (bulgu varsa cikis 1)
#      ./calistir.sh bicim    dizgi denetimi, tabandakiler bastirilir (HATA varsa cikis 1)
#      ./calistir.sh bicim-taban  simdiki bicim bulgularini kabul edilmis
#                             gecmis olarak tabana yazar (bilerek, elle calistirilir)
#      ./calistir.sh sapka    sapka taramasi, KURU (yazmak: sapka.py --uygula)
#      ./calistir.sh toplu    terim tutarliligi (sozluk + words.md), tablo
#      ./calistir.sh belgeler ses haritalari + istemler: yazim, orneklerde eski
#                             kelime, yalniz-Klein isaretleri, K/N kimlikleri
#      ./calistir.sh takvim   bolum adlari tekrarlaniyor mu, tarihler carsamba/
#                             cumartesi takvimine uyuyor mu
#      ./calistir.sh tarama   sadece Ingilizce tarama (nadiren gerekir)
#
#  FARK: denetim, lint, bicim, toplu, takvim ve belgeler adimlari tam
#  korpusta calisinca bulgularini Reports/bulgular/'a yazar ve sonunda
#  yalnizca son calistirmadan beri DEGISENI gosterir (fark.py):
#      fark [bicim]: +2 yeni, -1 giden (280 -> 281 bulgu)
#  Bir onceki calistirma Reports/son/'da durur. 'bolum' zinciri kismi
#  tarama yaptigi icin fark yazmaz.
#
#  LOTM_KOK ayarliysa ona uyar; yoksa betigin konumundan turetir.
#  Eskiden yalnizca ikincisi vardi, yani lotm.py LOTM_KOK'a bakarken bu
#  betik bakmiyordu ve ikisi farkli koke isaret edebiliyordu.
# ============================================================

set -euo pipefail

TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOK="${LOTM_KOK:-$(dirname "$TOOLS")}"
export LOTM_KOK="$KOK"

SITE="$KOK/Imperium34.github.io"
KAYNAK="$KOK/Source/LotM_Volumes"
RAPOR="$TOOLS/Reports"
# Bolum acilis sablonlari AYRI bir Reports/ altinda: $KOK/Tools/Reports.
# Ikisi de "Reports" adini tasiyor, biri sozluk yedekleri ve denetim.txt,
# digeri Ch_NN.md. Ayni degiskene baglanirsa sessizce yanlis dosya okunur.
SABLONLAR="${LOTM_SABLONLAR:-$KOK/Tools/Reports}"
SOZLUK="$SITE/_data/sozluk.yml"
# words.md: betik klasorunde varsa o, yoksa veri klasoru ($KOK/Tools, Reports/
# ile ayni yer). lotm.py ayni sirayla bakar; disa aktarilir ki Python betikleri
# de ayni dosyayi okusun.
if [[ -n "${LOTM_KELIMELER:-}" ]]; then
  KELIMELER="$LOTM_KELIMELER"
elif [[ -f "$TOOLS/words.md" ]]; then
  KELIMELER="$TOOLS/words.md"
else KELIMELER="$KOK/Tools/words.md"; fi
export LOTM_KELIMELER="$KELIMELER"
BOLUMLER="$SITE/_chapters"
# bicim_denetle tabani: yayimlanmis bolumlerin KABUL EDILMIS bicim farklari
# (cekirdek, yayimlanmis bolumde bicimin geriye donuk duzeltilmeyecegini
# soyler). Reports/ degil lint/ altinda: bu bir rapor degil bir karar, ve
# lint-kurallari.yml gibi surum denetiminde tutulmali.
BICIM_TABAN="${LOTM_BICIM_TABAN:-$TOOLS/lint/bicim-taban.tsv}"

mkdir -p "$RAPOR"
# fark.py: her tam-korpus adimi bulgularini buraya yazar; Reports/son/ bir
# onceki calistirmanin kopyasidir. Adim sonunda yalnizca FARK gosterilir
# (+ yeni / - giden). 'bolum' zinciri yazmaz: kismi bir tarama "onceki"yi
# bozar ve bir sonraki tam calistirma yuzlerce sahte "giden" gosterirdi.
BULGULAR="$RAPOR/bulgular"
mkdir -p "$BULGULAR"

fark_goster() {
  python3 "$TOOLS/fark.py" "$BULGULAR/$1.tsv" || true
}

kirmizi() { printf '\033[31m%s\033[0m\n' "$*"; }
yesil() { printf '\033[32m%s\033[0m\n' "$*"; }
mavi() { printf '\033[34m%s\033[0m\n' "$*"; }

kontrol() {
  local eksik=0
  [[ -f "$SOZLUK" ]] || {
    kirmizi "YOK: $SOZLUK"
    eksik=1
  }
  [[ -d "$BOLUMLER" ]] || {
    kirmizi "YOK: $BOLUMLER"
    eksik=1
  }
  ((eksik == 0)) || exit 1
}

yedekle() {
  # etiketle.py --yerinde yazacagi icin once yedek. Git zaten gecmisi
  # tutuyor ama commit edilmemis duzenlemeler kaybolabilir.
  local damga
  damga="$(date +%Y%m%d-%H%M%S)"
  cp "$SOZLUK" "$RAPOR/sozluk-$damga.yedek.yml"
  mavi "  yedek: Reports/sozluk-$damga.yedek.yml"
  # 10'dan eskilerini at; yoksa Reports/ suresiz buyur.
  ls -1t "$RAPOR"/sozluk-*.yedek.yml 2>/dev/null | tail -n +11 | xargs -r rm --
}

adim_test() {
  mavi "[T] Testler calistiriliyor..."
  # Testler tmp_path uzerinde sentetik veriyle calisir; gercek depoya
  # dokunmaz, Source/ ya da _chapters/ olmadan da gecer.
  if ! python3 -m pytest --version >/dev/null 2>&1; then
    kirmizi "  ATLANDI: pytest yok.  pip install pytest"
    return 1
  fi
  # Yol ACIKCA verilir. Argumansiz cagrida pytest kok dizini cwd'den
  # YUKARI dogru arar, yani tests/pytest.ini -- cwd'nin ALTINDA oldugu
  # icin -- hic bulunmaz ve icindeki ayarlar sessizce uygulanmaz.
  # Ustelik toplama $KOK'ten basladigi icin Imperium34.github.io da
  # taranir.
  (cd "$TOOLS" && python3 -m pytest tests)
}

adim_kontrol() {
  mavi "[0/8] Bolum numaralandirmasi dogrulaniyor..."
  # Zincirin geri kalani bolum numaralarinin uc kaynakta ayni seyi
  # gostermesine guveniyor. Bir kayma varsa "ceviri hatasi" gibi gorunur;
  # burada gorulmesi cok daha ucuz.
  if ! python3 "$TOOLS/lotm.py" kontrol; then
    kirmizi "  Numaralandirma tutarsiz. Devam etmeden once bakin:"
    kirmizi "    python3 lotm.py ciltler"
    kirmizi "    python3 lotm.py anomali"
    return 1
  fi
  yesil "  numaralandirma tutarli"
}

adim_takvim() {
  # Baslik tekrari ve carsamba/cumartesi takvimi. Ucuz ve yayin oncesi
  # yakalanmasi gereken tek tur hata: tarih yanlissa bolum yanlis gun cikar.
  # "$@": bolum zinciri --bolum N verir (beklenen tarihi yazdirmak icin).
  # Eskiden argumanlar iletilmiyordu; tek bolum kipi hic calismiyordu.
  # Fark yalnizca argumansiz (tam) calismada.
  if (($#)); then
    python3 "$TOOLS/takvim_denetle.py" "$@"
    return
  fi
  local kod=0
  python3 "$TOOLS/takvim_denetle.py" --bulgular "$BULGULAR/takvim.tsv" || kod=$?
  fark_goster takvim
  return "$kod"
}

adim_tarama() {
  mavi "[1/8] Ingilizce ciltler taraniyor (metinde / bolum tespiti)..."
  if [[ ! -d "$KAYNAK" ]]; then
    kirmizi "  ATLANDI: $KAYNAK yok. Ciltler depoda tutulmuyor;"
    kirmizi "           Source/ klasorunu yerel olarak olusturmaniz gerekir."
    return 1
  fi
  python3 "$TOOLS/kapi_denetle.py" \
    --sozluk "$SOZLUK" \
    --kaynak "$KAYNAK" \
    --rapor "$RAPOR/rapor.tsv"
  yesil "  -> Reports/rapor.tsv"
}

adim_etiket() {
  mavi "[2/8] sozluk.yml etiketleniyor (kaynak / mudahale / metinde)..."
  if [[ ! -f "$RAPOR/rapor.tsv" ]]; then
    kirmizi "  ATLANDI: rapor.tsv yok. Once './calistir.sh tarama' calistirin."
    return 1
  fi
  yedekle
  python3 "$TOOLS/etiketle.py" \
    --sozluk "$SOZLUK" \
    --rapor "$RAPOR/rapor.tsv" \
    --yerinde
  yesil "  -> _data/sozluk.yml guncellendi"
  mavi "  DIFF'I OKUYUN: git -C \"$SITE\" diff _data/sozluk.yml"
}

adim_denetim() {
  mavi "[3/8] Bolumler sozluge karsi denetleniyor..."
  # --kurallar: lint'in bagLAMIYLA bildirdigi eskimis bicimler burada tek
  # satira iner. Ayni karar iki dosyada duruyor (sozluk.yml veriyi tutar,
  # lint-kurallari.yml baglami); rapor bir kez okunsun diye.
  local kod=0
  python3 "$TOOLS/yayim_denetle.py" \
    --sozluk "$SOZLUK" \
    --bolumler "$BOLUMLER" \
    --kurallar "$TOOLS/lint/lint-kurallari.yml" \
    --bulgular "$BULGULAR/denetim.tsv" \
    --envanter | tee "$RAPOR/denetim.txt" || kod=$?
  yesil "  -> Reports/denetim.txt"
  fark_goster denetim
  return "$kod"
}

adim_lint() {
  mavi "[4/8] Tutarlilik denetimi (varyant / yasakli / ek-uyumu)..."
  # Cikis 1 = BULGU VAR demek, "calismadi" degil. Kanca ya da CI bunu
  # dogrudan kullanabilir; zincirin icinde uyari olarak gecilir.
  # --kaynak: anakronizm denetimi Cince metne de bakar. Kaynakta karsiligi
  # olan birim (公里, 米, 克 ...) bulgu sayilmaz -- o dunyanin kendi
  # kelimesidir. Cince metin okunamazsa uyarip kaynaksiz calisir.
  local kod=0
  python3 "$TOOLS/lint/sozluk_lint.py" \
    --sozluk "$SOZLUK" \
    --kurallar "$TOOLS/lint/lint-kurallari.yml" \
    --kaynak \
    --bulgular "$BULGULAR/lint.tsv" \
    "$BOLUMLER"/*.md || kod=$?
  fark_goster lint
  return "$kod"
}

bicim_argumanlari() {
  # Ortak argumanlar. Taban yoksa uyarir ama calisir: ilk kurulumda butun
  # gecmis bulgular gorunur, 'bicim-taban' ile kabul edilir.
  BICIM_ARG=(--bolumler "$BOLUMLER")
  [[ -f "$SOZLUK" ]] && BICIM_ARG+=(--sozluk "$SOZLUK")
  if [[ -f "$BICIM_TABAN" ]]; then
    BICIM_ARG+=(--taban "$BICIM_TABAN")
  else
    mavi "  taban yok ($BICIM_TABAN): yayimlanmis bolumlerin eski bulgulari da gorunecek."
    mavi "  kabul etmek icin: ./calistir.sh bicim-taban"
  fi
}

adim_bicim() {
  mavi "[5/8] Bicim denetimi (tirnak / italik / atif / para; normdan sapan bolumler)..."
  # Cikis 1 = tabanda olmayan bir HATA var. Zincirde uyari olarak gecilir;
  # tek bolum zincirinde yayin oncesi kirmizi uyaridir.
  bicim_argumanlari
  local kod=0
  python3 "$TOOLS/bicim_denetle.py" "${BICIM_ARG[@]}" --bulgular "$BULGULAR/bicim.tsv" |
    tee "$RAPOR/bicim.txt" || kod=$?
  yesil "  -> Reports/bicim.txt"
  fark_goster bicim
  # sapka gibi: duzeltme zincirde yalniz KURU onerilir; yazmak elle.
  mavi "  otomatik duzeltme (KURU): python3 bicim_denetle.py --duzelt"
  mavi "  yazmak icin:              python3 bicim_denetle.py <numara> --duzelt --uygula"
  return "$kod"
}

adim_bicim_taban() {
  mavi "Bicim tabani yaziliyor: $BICIM_TABAN"
  # Bilerek ayri bir komut: taban, simdiki her bulguyu "kabul edilmis
  # gecmis" yapar. Uzerinde calisilan bir taslak varken yazilirsa o
  # taslagin hatalari da sessizce kabul edilir. Bu yuzden once soruluyor.
  local son
  son=$(ls "$BOLUMLER" 2>/dev/null | grep -E '^[0-9]+\.md$' | sort -n | tail -1)
  mavi "  en son bolum: ${son:-?} -- bu bolum hala taslaksa once onu bitirin."
  read -r -p "  Devam edilsin mi? [e/H] " cevap
  [[ "$cevap" == "e" || "$cevap" == "E" ]] || {
    mavi "  iptal edildi"
    return 1
  }
  local arg=(--bolumler "$BOLUMLER")
  [[ -f "$SOZLUK" ]] && arg+=(--sozluk "$SOZLUK")
  python3 "$TOOLS/bicim_denetle.py" "${arg[@]}" --taban-yaz "$BICIM_TABAN"
  mavi "  surum denetimine eklemeyi unutmayin: git add \"$BICIM_TABAN\""
}

adim_sapka() {
  mavi "[6/8] Sapka taramasi (KURU -- hicbir dosya degismez)..."
  # --sozluk / --kelimeler: sozlukte (ya da words.md'de) gecen bir kelimenin
  # yazimini sozluk belirler, liste degil ("Ebedi Gece" -> "ebedi" kalir,
  # "Semavî Muazzez" -> "Semavi Muazzez" olur). Yazimi degistirmek icin
  # sozlugu degistirin.
  local kel=()
  [[ -f "$KELIMELER" ]] && kel=(--kelimeler "$KELIMELER")
  python3 "$TOOLS/lint/sapka.py" --sozluk "$SOZLUK" ${kel[@]+"${kel[@]}"} "$BOLUMLER"/*.md
  mavi "  yazmak icin:  python3 lint/sapka.py --sozluk \"$SOZLUK\" ${kel[*]:-} --uygula \"$BOLUMLER\"/*.md"
  mavi "  listeye aday: python3 lint/sapka.py --kesif \"$BOLUMLER\"/*.md"
}

adim_toplu() {
  mavi "[7/8] Terim tutarliligi (sozluk + words.md, yayimlanmis bolumler)..."
  # --kaynak ikisi: Cincesi girilmis terim Cince anahtarla (kesin), girilmemis
  # olan Ingilizceyle taranir; tek tablo. Tablonun basi duzeltme sirasidir.
  local kod=0
  python3 "$TOOLS/toplu_denetle.py" --kaynak ikisi --bulgular "$BULGULAR/toplu.tsv" |
    tee "$RAPOR/toplu.txt" || kod=$?
  yesil "  -> Reports/toplu.txt"
  fark_goster toplu
  mavi "  tek terim:  python3 toplu_denetle.py --kaynak ikisi --ayrinti \"<terim>\""
  return "$kod"
}

adim_belgeler() {
  mavi "[8/8] Ses haritalari ve istemler..."
  # Taslak ureten model bu belgeleri okur ve ORNEKLERI taklit eder; bolumlere
  # uygulanan yazim ve terim kurallari burada da gecerli olmali.
  local belgeler=()
  # nullglob: bos bir klasor duz "*.md" dizesini dosya adi diye vermesin.
  local eski_nullglob
  eski_nullglob=$(shopt -p nullglob || true)
  shopt -s nullglob
  for d in "$KOK/Tools/Voice_Maps" "$KOK/Tools/Prompts"; do
    [[ -d "$d" ]] && belgeler+=("$d"/*.md)
  done
  eval "$eski_nullglob"
  [[ ${#belgeler[@]} -gt 0 ]] || {
    mavi "  belge bulunamadi"
    return 0
  }
  local kel=()
  [[ -f "$KELIMELER" ]] && kel=(--kelimeler "$KELIMELER")
  python3 "$TOOLS/lint/sapka.py" --sozluk "$SOZLUK" ${kel[@]+"${kel[@]}"} "${belgeler[@]}"
  local kod=0
  python3 "$TOOLS/belge_denetle.py" --sozluk "$SOZLUK" --bulgular "$BULGULAR/belgeler.tsv" \
    "${belgeler[@]}" || kod=$?
  fark_goster belgeler
  return "$kod"
}

adim_bolum() {
  local no="$1"
  local sablon="$SABLONLAR/Ch_$no.md"

  mavi "[1/5] Baslik ve yayin tarihi..."
  # Beklenen tarihi de yazar: yeni bolumun on maddesine oradan kopyalayin.
  adim_takvim --bolum "$no" || kirmizi "  BASLIK/TARIH HATASI -- yayinlamadan once duzeltin"

  mavi "[2/5] Hizalama guvenilir mi?"
  # Cikis kodu 1 = kayma VAR demek; zincir durmaz, cunku sonraki adim
  # zaten hizalamadan bagimsiz. Ama ceviri_denetle'yi bu bolumde
  # calistiracaksaniz ESLESMEYEN listesini buna gore okuyun.
  python3 "$TOOLS/hizalama_denetle.py" "$no" || true

  mavi "[3/5] Bu bolumdeki terimler sozlukle tutarli mi?"
  # Yalnizca bu bolum: burada gecen terimler, burada nasil cevrilmis.
  # Rapor adimi; bulgu zinciri durdurmaz. Yayimlanmis metne bakar
  # (_chapters), yani bolum oraya konduktan sonra anlamlidir.
  python3 "$TOOLS/toplu_denetle.py" --kaynak ikisi --bolum "$no" || true

  mavi "[4/5] Bicim: dizgi kurallari ve bolumun oteki bolumlere gore sapmasi..."
  # Tek dosya kipinde bolum, yayimlanmis butun bolumlerle karsilastirilir
  # (NORMDAN SAPAN BOLUMLER). Tabandakiler bastirilir; taslak bolumun kendi
  # hatalari tabanda olmadigi icin hepsi gorunur.
  if [[ -d "$BOLUMLER" ]]; then
    bicim_argumanlari
    python3 "$TOOLS/bicim_denetle.py" "$no" "${BICIM_ARG[@]}" ||
      kirmizi "  BICIM HATASI -- yayinlamadan once duzeltin"
  else
    kirmizi "  ATLANDI: $BOLUMLER yok."
  fi

  mavi "[5/5] Kapanis denetimi (hizalamadan bagimsiz)..."
  if [[ ! -f "$sablon" ]]; then
    kirmizi "  ATLANDI: $sablon yok."
    return 1
  fi
  python3 "$TOOLS/kapanis_denetle.py" "$sablon" --bolum "$no"
}

# 'test' kontrol()'den once gelmeli: testler sozluk.yml ya da _chapters
# olmadan da calisabilmeli.
if [[ "${1:-}" == "test" ]]; then
  adim_test
  yesil "bitti."
  exit 0
fi

# 'bolum' de kontrol()'den once: sozluk.yml ya da _chapters olmadan da
# anlamli calisir, yalnizca ham metinlere ve sablona bakar.
if [[ "${1:-}" == "bolum" ]]; then
  no="${2:-}"
  if [[ -z "$no" ]]; then
    # Numara verilmezse _chapters'taki en son bolum: taslaklar orada
    # yaziliyor, yani bu cogu zaman uzerinde calisilan bolumdur, degilse
    # az once bitirilen.
    son=$(ls "$BOLUMLER" 2>/dev/null | grep -E '^[0-9]+\.md$' | sort -n | tail -1)
    [[ -n "$son" ]] || {
      kirmizi "kullanim: ./calistir.sh bolum [numara]"
      exit 1
    }
    no=$((10#${son%.md}))
    mavi "numara verilmedi -- en son bolum: $no"
  fi
  adim_bolum "$no"
  yesil "bitti."
  exit 0
fi

kontrol
case "${1:-hepsi}" in
kontrol) adim_kontrol ;;
tarama) adim_tarama ;;
etiket) adim_etiket ;;
denetim) adim_denetim ;;
lint) adim_lint ;;
bicim) adim_bicim ;;
bicim-taban) adim_bicim_taban ;;
sapka) adim_sapka ;;
toplu) adim_toplu ;;
takvim) adim_takvim ;;
belgeler) adim_belgeler ;;
hepsi)
  adim_test || mavi "  (testler atlandi, zincire devam)"
  adim_kontrol || kirmizi "  (numaralandirma sorunlu, zincire yine de devam)"
  mavi "  basliklar ve yayin tarihleri..."
  adim_takvim || kirmizi "  (baslik/tarih hatasi var, yukariya bakin)"
  adim_tarama || mavi "  (tarama atlandi, zincire devam)"
  adim_etiket || mavi "  (etiketleme atlandi, zincire devam)"
  # Her adim "|| ..." ile: set -e altinda bulgu bildiren (cikis 1) tek bir
  # adim zincirin GERI KALANINI sessizce keserdi. adim_denetim eskiden
  # boyle cagriliyordu; yayim_denetle bir sey buldugu anda lint, bicim,
  # sapka, toplu ve belgeler hic calismiyordu.
  adim_denetim || kirmizi "  (yayim denetimi bulgu bildirdi, yukariya bakin)"
  adim_lint || mavi "  (lint bulgu bildirdi, yukariya bakin)"
  adim_bicim || kirmizi "  (bicim denetimi tabanda olmayan HATA buldu, yukariya bakin)"
  adim_sapka || mavi "  (sapka taramasi atlandi)"
  adim_toplu || mavi "  (terim tutarliligi atlandi)"
  adim_belgeler || kirmizi "  (belgelerde hata var, yukariya bakin)"
  ;;
*)
  echo "kullanim: ./calistir.sh [hepsi|test|kontrol|takvim|tarama|etiket|denetim|lint|bicim|bicim-taban|sapka|toplu|belgeler]"
  echo "          ./calistir.sh bolum [numara]   (numarasiz: en son bolum)"
  exit 1
  ;;
esac

yesil "bitti."
