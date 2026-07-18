#!/usr/bin/env bash
# ============================================================
#  calistir.sh -- bakim zinciri
#
#  Uc betigin arasinda gercek bagimliliklar var ve sirasi onemli:
#
#     searcher.py   Source/LotM_Volumes  ->  Reports/rapor.tsv
#     etiketle.py   rapor.tsv            ->  _data/sozluk.yml
#     denetci2.py   sozluk.yml + _chapters -> Reports/denetim.txt
#
#  Bu betik Tools/ icinden calistirilmali.
#      ./calistir.sh          tam zincir
#      ./calistir.sh denetim  sadece ceviri denetimi (hizli, gunluk)
#      ./calistir.sh tarama   sadece Ingilizce tarama (nadiren gerekir)
# ============================================================

set -euo pipefail

TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOK="$(dirname "$TOOLS")"
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
}

adim_tarama() {
  mavi "[1/3] Ingilizce ciltler taraniyor (metinde / bolum tespiti)..."
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
  mavi "[2/3] sozluk.yml etiketleniyor (kaynak / mudahale / metinde)..."
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
  mavi "[3/3] Yayimlanmis bolumler sozluge karsi denetleniyor..."
  python3 "$TOOLS/denetci2.py" \
    --sozluk "$SOZLUK" \
    --bolumler "$BOLUMLER" \
    --envanter | tee "$RAPOR/denetim.txt"
  yesil "  -> Reports/denetim.txt"
}

kontrol
case "${1:-hepsi}" in
tarama) adim_tarama ;;
etiket) adim_etiket ;;
denetim) adim_denetim ;;
hepsi)
  adim_tarama || mavi "  (tarama atlandi, zincire devam)"
  adim_etiket || mavi "  (etiketleme atlandi, zincire devam)"
  adim_denetim
  ;;
*)
  echo "kullanim: ./calistir.sh [hepsi|tarama|etiket|denetim]"
  exit 1
  ;;
esac

yesil "bitti."
