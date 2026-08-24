#!/usr/bin/env bash
# ============================================================
#  calistir.sh -- bakim zinciri
#
#  Betiklerin arasinda gercek bagimliliklar var ve sirasi onemli:
#
#     lotm.py       (numaralandirma dogrulamasi -- hepsinin temeli)
#     searcher.py   Source/LotM_Volumes  ->  Reports/rapor.tsv
#     etiketle.py   rapor.tsv            ->  _data/sozluk.yml
#     denetci2.py   sozluk.yml + _chapters -> Reports/denetim.txt
#
#      ./calistir.sh          tam zincir
#      ./calistir.sh test     testleri calistir (bagimlilik yok, hizli)
#      ./calistir.sh kontrol  sadece numaralandirma dogrulamasi
#      ./calistir.sh denetim  sadece ceviri denetimi (hizli, gunluk)
#      ./calistir.sh tarama   sadece Ingilizce tarama (nadiren gerekir)
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
SOZLUK="$SITE/_data/sozluk.yml"
BOLUMLER="$SITE/_chapters"

mkdir -p "$RAPOR"

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
  (cd "$KOK" && python3 -m pytest)
}

adim_kontrol() {
  mavi "[0/4] Bolum numaralandirmasi dogrulaniyor..."
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

adim_tarama() {
  mavi "[1/4] Ingilizce ciltler taraniyor (metinde / bolum tespiti)..."
  if [[ ! -d "$KAYNAK" ]]; then
    kirmizi "  ATLANDI: $KAYNAK yok. Ciltler depoda tutulmuyor;"
    kirmizi "           Source/ klasorunu yerel olarak olusturmaniz gerekir."
    return 1
  fi
  python3 "$TOOLS/searcher.py" \
    --sozluk "$SOZLUK" \
    --kaynak "$KAYNAK" \
    --rapor "$RAPOR/rapor.tsv"
  yesil "  -> Reports/rapor.tsv"
}

adim_etiket() {
  mavi "[2/4] sozluk.yml etiketleniyor (kaynak / mudahale / metinde)..."
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
  mavi "[3/4] Yayimlanmis bolumler sozluge karsi denetleniyor..."
  python3 "$TOOLS/denetci2.py" \
    --sozluk "$SOZLUK" \
    --bolumler "$BOLUMLER" \
    --envanter | tee "$RAPOR/denetim.txt"
  yesil "  -> Reports/denetim.txt"
}

# 'test' kontrol()'den once gelmeli: testler sozluk.yml ya da _chapters
# olmadan da calisabilmeli.
if [[ "${1:-}" == "test" ]]; then
  adim_test
  yesil "bitti."
  exit 0
fi

kontrol
case "${1:-hepsi}" in
kontrol) adim_kontrol ;;
tarama) adim_tarama ;;
etiket) adim_etiket ;;
denetim) adim_denetim ;;
hepsi)
  adim_test || mavi "  (testler atlandi, zincire devam)"
  adim_kontrol || kirmizi "  (numaralandirma sorunlu, zincire yine de devam)"
  adim_tarama || mavi "  (tarama atlandi, zincire devam)"
  adim_etiket || mavi "  (etiketleme atlandi, zincire devam)"
  adim_denetim
  ;;
*)
  echo "kullanim: ./calistir.sh [hepsi|test|kontrol|tarama|etiket|denetim]"
  exit 1
  ;;
esac

yesil "bitti."
