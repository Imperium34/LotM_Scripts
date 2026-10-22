# harita/ — ses haritası araçları

Side_Character_Maps.md ve Side_Character_Notlar.md için kanıt toplama ve ¶ doğrulama. Hepsi `Scripts/` içinden çalışır (`python3 harita/…`).

| Araç | İşi |
|---|---|
| `gruplar.py N [en\|tr] [desen]` | Bölümün hizalama gruplarını ¶ numarasıyla basar; numaralar `bolum.py`'ninkiyle aynıdır. Modül olarak `gruplar(N, "en")` → `{¶: {"ZH": …, "EN": …}}`. |
| `replik.py "<ad regex>" 992,1024-1032 [k] [en\|tr]` | Adı ve “ içeren grupları, ardındaki k replik grubuyla toplar. Atfı elle doğrula. |
| `dogrula.py alintilar.txt [--tr] [--genis]` | `bölüm\|¶\|ZH alt dizgisi` satırlarını kontrol eder; yanlışsa doğru yeri bulur. |

Kurallar:

- Çevrilmemiş bölümler ZH/EN, yayımlanmışlar ZH/TR gruplarıyla numaralanır; aynı bölümde ikisi bir kayabilir.
- Her alıntı haritaya yazılmadan önce `dogrula.py`'den geçer. Toplu çıkarmada alıntılar sık sık bir bölüm kayar.
- Konuşmacıyı sıralamak için İngilizce konuşma etiketleri sayılabilir ("X said / said X"); adı geçme sayısı alt dizgilerle şişer ("Mr. A" → "Mr. Azik").
