# MarkItDown Plus - Erabiltzailearen Gida

## Zer da plugin hau?

**MarkItDown Plus** zure dokumentuak (PDFak, Word fitxategiak, PowerPointak, etab.) IA laguntzaileek bilatu eta kontsultatu dezaketen formatu batera bihurtzen dituen tresna bat da. Zure dokumentuak "zatiak" izeneko pieza txikiagotan zatitzen ditu eta ezagutza-base batean gordetzen ditu.

Pentsa ezazu liburu batentzat aurkibide bat sortzen ari zarela bezala: liburu osoa irakurri beharrean informazioa aurkitzeko, IAk azkar bilatu ditzake atal garrantzitsuak.

---

## Pribatutasuna eta Segurtasuna

### 🔒 Zure dokumentuak pribatuak dira lehenespenez

**Garrantzitsua:** Tresna honek zure dokumentuak **gure zerbitzarietan** (lokalean) prozesatzen ditu lehenespenez. Zure edukia EZ da OpenAI bezalako kanpoko zerbitzuetara bidaltzen, zuk zehaztasunez aukeratzen ez baduzu.

| Konfigurazioa | Zer gertatzen da zure datuekin |
|---------------|--------------------------------|
| Irudien deskribapena: **Bat ere ez** (lehenetsia) | ✅ Dena lokala da. Ez da kanpoko zerbitzurik erabiltzen. |
| Irudien deskribapena: **Oinarrizkoa** | ✅ Dena lokala da. Irudiak atera eta gordetzen dira. |
| Irudien deskribapena: **IArekin** | ⚠️ Irudiak OpenAIra bidaltzen dira deskribapenerako. |

**Gomendioa:** Dokumentu konfidentzialetarako, langileen erregistroetarako, finantza-datuetarako edo edozein informazio sentikortarako, beti erabili "Bat ere ez" edo "Oinarrizkoa" modua.

---

## Aukerak Ulertzen

### 1. Irudien Kudeaketa

Zure dokumentuak irudiak dituenean (grafikoak, diagramak, argazkiak), hauen kudeaketa aukeratu dezakezu:

#### Aukera: Bat ere ez (Gomendatua dokumentu sentikorretarako)
- **Zer egiten du:** Dauden irudi-erreferentziak mantentzen ditu baina ez ditu irudiak atera edo prozesatzen
- **Hoberena:** Dokumentu konfidentzialak, prozesamendu azkarragoa
- **Pribatutasuna:** ✅ Guztiz lokala

#### Aukera: Oinarrizkoa
- **Zer egiten du:** Dokumentutik irudiak ateratzen ditu eta fitxategi-izenetan oinarritutako deskribapen sinpleekin gordetzen ditu
- **Hoberena:** Irudiak eskuragarri izan nahi dituzun dokumentuak baina deskribapen zehatzik behar ez duzunean
- **Pribatutasuna:** ✅ Guztiz lokala

#### Aukera: IArekin (LLM)
- **Zer egiten du:** Irudiak OpenAIren IAra bidaltzen ditu deskribapen zehatz eta adimentsuak sortzeko
- **Hoberena:** Hezkuntza-materialak, dokumentu publikoak non irudien testuinguruak garrantzia duen
- **Pribatutasuna:** ⚠️ **Irudiak OpenAIra bidaltzen dira** - EZ erabili dokumentu konfidentzialetarako

---

### 2. Nola Zatitu Zure Dokumentua (Zatiketa Modua)

Zure dokumentua pieza txikiagotan zatitu behar da IAk eraginkortasunez bilatu dezan. Hiru modu daude hau egiteko:

#### Aukera: Estandarra (Lehenetsia)
- **Zer egiten du:** Zure dokumentua gutxi gorabehera tamaina bereko piezatan zatitzen du (karaktereetan neurtuta)
- **Hoberena:** Dokumentu orokorrak, posta elektronikoak, artikuluak, egitura gabeko testua
- **Nola funtzionatzen du:** Zinta luze bat pieza berdinetan moztea bezala

**Modu estandarrerako konfigurazio gehigarriak:**
- **Zatiaren tamaina:** Zein tamaina izan behar duen pieza bakoitzak (lehenetsia: 1000 karaktere, gutxi gorabehera 150-200 hitz)
- **Gainjartzea:** Zenbat testu errepikatzen den piezen artean testuingurua mantentzeko (lehenetsia: 200 karaktere)

*Aholkua: Zati txikiagoak (500-800) hobeto funtzionatzen dute galdera-erantzunetarako. Zati handiagoak (1500-2500) hobeto funtzionatzen dute laburpenetarako.*

#### Aukera: Orrialdeka
- **Zer egiten du:** Orrialde bakoitza pieza bereizi gisa mantentzen du
- **Hoberena:** PDFak, aurkezpenak, orrialde-jauziak esanguratsuak diren dokumentuak
- **Honekin funtzionatzen du:** PDF, Word (.docx), PowerPoint (.pptx) soilik

**Orrialde modurako konfigurazio gehigarriak:**
- **Orrialdeak zatiko:** Zenbat orrialde taldekatu elkarrekin (lehenetsia: 1)

*Adibidea: 10 orrialdeko PDF bat "Orrialdeak zatiko: 2"-rekin 5 zati sortzen ditu, bakoitza 2 orrialderekin.*

#### Aukera: Atalka
- **Zer egiten du:** Zure dokumentuaren goiburuak (tituluak, azpitituluak) erabiltzen ditu zatiketa naturalak sortzeko
- **Hoberena:** Txostenak, eskuliburuak, atal argiak dituzten dokumentu egituratuak
- **Nola funtzionatzen du:** Zure dokumentuaren antolaketa errespetatzen du

**Atal modurako konfigurazio gehigarriak:**
- **Zatitu goiburu-mailan:** Zein goiburu-mailak definitzen du zati bat
  - 1. maila = Titulu nagusiak (# Goiburua)
  - 2. maila = Azpitituluak (## Goiburua) - *gomendatua*
  - 3. maila = Azpi-azpitituluak (### Goiburua)
- **Atalak zatiko:** Zenbat atal taldekatu elkarrekin (lehenetsia: 1)

*Adibidea: Kapituluak eta atalak dituen txosten bat, "2. maila" eta "1 atal zatiko" erabiliz, atal bakoitzeko zati bat sortzen du, kapitulu-tituluak testuingururako gordetuta.*

---

## Adibide Praktikoak

### 1. Adibidea: Enpresako Politiken Dokumentua (Konfidentziala)

**Egoera:** Giza baliabideen politika sentikorrak dituen langile-eskuliburua igotzen ari zara.

**Gomendatutako konfigurazioa:**
- Irudien kudeaketa: **Bat ere ez**
- Zatiketa modua: **Atalka**
- Zatitu mailan: **2** (politika-atal bakoitza harrapatzeko)
- Atalak zatiko: **1**

**Zergatik:** Dena pribatua mantentzen du, dokumentuaren egitura errespetatzen du, politika zehatzak errazago aurkitzeko.

---

### 2. Adibidea: Produktu-Katalogoa Argazkiekin

**Egoera:** Deskribapenak behar dituzten irudi asko dituen produktu-katalogo bat igotzen ari zara.

**Gomendatutako konfigurazioa:**
- Irudien kudeaketa: **Oinarrizkoa** (edo IArekin deskribapenak funtsezkoak badira eta edukia ez bada sentikorra)
- Zatiketa modua: **Orrialdeka**
- Orrialdeak zatiko: **1**

**Zergatik:** Produktu-orrialde bakoitza elkarrekin mantentzen da, irudiak eskuragarri daude.

---

### 3. Adibidea: Ikerketa-Artikulua

**Egoera:** Ikerketa-helburuetarako artikulu akademiko bat igotzen ari zara.

**Gomendatutako konfigurazioa:**
- Irudien kudeaketa: **Oinarrizkoa** (irudiak eta grafikoak ateratzeko)
- Zatiketa modua: **Atalka**
- Zatitu mailan: **2**
- Atalak zatiko: **1**

**Zergatik:** Artikuluaren egitura errespetatzen du (Laburpena, Sarrera, Metodoak, etab.), irudiak eskuragarri mantentzen ditu.

---

### 4. Adibidea: Testu-Dokumentu Luzea

**Egoera:** Egitura argirik gabeko dokumentu luze bat igotzen ari zara (transkripzio edo nobela bat bezala).

**Gomendatutako konfigurazioa:**
- Irudien kudeaketa: **Bat ere ez**
- Zatiketa modua: **Estandarra**
- Zatiaren tamaina: **1000**
- Gainjartzea: **200**

**Zergatik:** Modu estandarrak hobeto funtzionatzen du egitura gabeko testuarentzat, gainjartze​ak testuingurua ez galtzea ziurtatzen du piezen artean.

---

## Ohiko Galderak

### G: Zer gertatzen da "Atalka" aukeratzen badut baina nire dokumentuak goibururik ez baditu?

Sistemak automatikoki "Estandar" modura aldatzen du. Tamaina uniformeko zatiak jasoko dituzu horren ordez.

### G: Nola jakin dezaket zein zati-tamaina erabili?

- **Galdera-erantzunetarako:** Zati txikiagoak (500-1000) hobeto funtzionatzen dute fokatuagoak direlako
- **Laburpenetarako:** Zati handiagoak (1500-2500) testuinguru gehiago ematen dute
- **Zalantzarik izanez gero:** Balio lehenetsia (1000) ondo funtzionatzen du kasu gehienetarako

### G: Zein fitxategi-mota onartzen dira?

PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), HTML, audio fitxategiak (.mp3, .wav), CSV, JSON, XML, ZIP artxiboak eta EPUB liburu elektronikoak.

### G: Nire jatorrizko fitxategia gordeko da?

Bai! Jatorrizko fitxategia gordetzen da, eta Markdown bertsio bat ere sortzen da bistaratzea errazteko.

### G: Zenbat denbora behar du prozesamenduak?

Fitxategiaren tamainaren eta aukeratutako aukeren araberakoa da:
- Dokumentu txikiak (< 10 orrialde): Segundo batzuk
- Dokumentu handiak IAren irudi-deskribapenekin: Minutu batzuk

---

## Laguntza Lortzea

Galderak badituzu edo arazoak aurkitzen badituzu:
1. Egiaztatu zure fitxategia formatu bateragarri batean dagoela
2. Probatu lehenik konfigurazio lehenetsiekin
3. Jarri harremanetan zure sistema-administratzailearekin laguntzarako

---

*Azken eguneratzea: 2026ko urtarrila*

