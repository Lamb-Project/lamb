# LAMB Plataforma -- Eragileentzako Laburpena

**Bertsioa:** 1.0
**Data:** 2026ko otsailaren 15a
**Hartzaileak:** Irakasleak, erakundeetako administratzaileak, sistema-administratzaileak

---

## Aurkibidea

1. [Zer da LAMB?](#1-zer-da-lamb)
2. [Filosofia: AI segurua hezkuntzan](#2-filosofia-ai-segurua-hezkuntzan)
3. [Norentzat da LAMB?](#3-norentzat-da-lamb)
4. [Gaitasun nagusiak](#4-gaitasun-nagusiak)
5. [Nola funtzionatzen du -- Irakasleentzat](#5-nola-funtzionatzen-du--irakasleentzat)
6. [Nola funtzionatzen du -- LTI integrazioa Moodle-rekin](#6-nola-funtzionatzen-du--lti-integrazioa-moodle-rekin)
7. [Nola funtzionatzen du -- Erakundeetako administratzaileentzat](#7-nola-funtzionatzen-du--erakundeetako-administratzaileentzat)
8. [Nola funtzionatzen du -- Sistema-administratzaileentzat](#8-nola-funtzionatzen-du--sistema-administratzaileentzat)
9. [AIren bidezko ebaluazioa: Evaluaitor eta LAMBA](#9-airen-bidezko-ebaluazioa-evaluaitor-eta-lamba)
10. [Arkitekturaren ikuspegi orokorra](#10-arkitekturaren-ikuspegi-orokorra)
11. [Pribatutasuna eta datuen subiranotasuna](#11-pribatutasuna-eta-datuen-subiranotasuna)
12. [Glosarioa](#12-glosarioa)

---

## 1. Zer da LAMB?

**LAMB** (Learning Assistants Manager and Builder) kode irekiko plataforma bat da, irakasleei ahalmena ematen diena AI bidezko ikaskuntza-laguntzaileak sortzeko, kudeatzeko eta Ikaskuntza Kudeaketa Sistemetan (Moodle bezalakoetan) zabaltzeko -- **koderik idatzi beharrik gabe**.

LAMB **"irakaskuntza-chatbot eraikitzaile"** gisa ikus daiteke: irakasleei aukera ematen die hizkuntza-eredu handiak (GPT-4, Mistral, lokalki ostatatutako ereduak, etab.) beren ikastaroko materialekin konbinatzeko, ikasleek Moodle-tik zuzenean atzi ditzaketen AI tutore espezializatuak sortzeko.

### Esaldi bakarreko proposamena

> **LAMB-ek irakasleei kontrol osoa ematen die beren irakasgairako "ChatGPT espezializatu" bat eraikitzeko, Moodle-ra konektatzeko eta ikasleen datuak guztiz seguru mantentzeko.**

### Balio-proposamen nagusia

| Norentzat... | LAMB-ek eskaintzen du... |
|--------------|--------------------------|
| **Irakasleak** | Koderik gabeko eraikitzaile bat ikastaroko materialetan oinarritutako AI tutoreak sortzeko |
| **Erakundeak** | AI hedapena datuen subiranotasuna eta pribatutasuna mantenduz |
| **Ikasleak** | Testuingurua kontuan hartzen duen AI laguntza espezifikoa, ohiko LMS-aren barruan |

### Oinarri akademikoa

LAMB ez da produktu komertzial bat. Unibertsitateko ikertzaileek garatua da eta parekoen ebaluazioa jasan du:

> *"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"*
> Marc Alier, Juanan Pereira, Francisco Jose Garcia-Penalvo, Maria Jose Casan, Jose Cabre
> *Computer Standards & Interfaces*, 92. bolumena, 2025eko martxoa

Proiektua **Marc Alier**-ek (Universitat Politecnica de Catalunya, Bartzelona) eta **Juanan Pereira**-k (Universidad del Pais Vasco / Euskal Herriko Unibertsitatea) zuzentzen dute, Universidad de Salamanca-ko (Grial Ikerketa Taldea) eta Tknika-ko (Euskal Autonomia Erkidegoko Lanbide Heziketako Ikerketa Aplikatuko Zentroa) lankidetzarekin.

---

## 2. Filosofia: AI segurua hezkuntzan

LAMB **Safe AI in Education Manifesto**-aren (https://manifesto.safeaieducation.org) printzipioetan oinarrituta dago, mundu osoko 87 akademikok baino gehiagok sinatutako esparru bat, Dr. Charles Severance (Michigango Unibertsitatea, Coursera-ren sortzailea) barne.

Manifestuaren oinarrizko sinesmena: **"AIak beti pertsonen zerbitzura egon behar du, giza gaitasunak indartuz, ez ordezkatuz."**

### Zazpi printzipioak

| # | Printzipioa | Zer esan nahi du hezkuntzarako | Nola inplementatzen du LAMB-ek |
|---|-------------|-------------------------------|-------------------------------|
| 1 | **Giza gainbegiratzea** | Erabaki guztiak gizakien gainbegirapenean geratzen dira. AIak ezin du ikasleen hezkuntza bere gain hartu. | Irakasleek laguntzaile guztiak sortzen, kontrolatzen eta kudeatzen dituzte. Laguntzaile bakoitzaren portaera irakasleak definitzen du. |
| 2 | **Pribatutasunaren babesa** | Ikasleen datuak babestu egin behar dira. Ikasleek datu pertsonalen gaineko kontrol osoa mantentzen dute. | Norberak ostatatutako azpiegitura. Ikasleen daturik ez da erakundetik kanpora irteten. EIIrik ez da kanpoko LLM hornitzaileetara bidaltzen erakundeak esplizituki konfiguratu ezean. |
| 3 | **Hezkuntza-lerrokatzea** | AIak erakundearen hezkuntza-estrategiak lagundu behar ditu, ez ahuldu. | Laguntzaileak ikastaroko material eta ikaskuntza-helburu zehatzetan oinarrituta daude. Irakasleak definitutako esparruaren barruan bakarrik erantzuten dute. |
| 4 | **Integrazio didaktikoa** | AIak lehendik dauden irakaskuntza-lanfluxuetan era naturalean txertatu behar du. | LTI integrazioak laguntzaileak zuzenean Moodle ikastaroetan txertatzen ditu. Ez da saio-hasierarik edo plataforma berezirik behar ikasleentzat. |
| 5 | **Zehaztasuna eta azalgarritasuna** | AI erantzunak zehatzak eta trazagarriak izan behar dira. | RAG-ek (Retrieval-Augmented Generation) automatikoki jatorriko aipamenak eskaintzen ditu. Arazketa-moduak irakasleei AIak "ikusten" duena zehatz-mehatz ikusteko aukera ematen die. |
| 6 | **Interfaze gardenak** | Interfazeek argi komunikatu behar dituzte AIaren mugak. | AIak sortutako erantzunak direla argi adierazten da. Erreferentziatutako iturri-dokumentuak aipatzen dira. |
| 7 | **Prestakuntza etikoa** | AI ereduak etikoki prestatuta egon behar dira, datuen iturriei buruzko gardentasunarekin. | Kode irekiko plataforma. Irakasleek aukeratzen dute LLM hornitzailea. Erabiltzen diren ereduei buruzko gardentasun osoa. |

### Zergatik ez erabili zuzenean ChatGPT edo Google Gemini?

Manifestuak eta LAMB-ek kezka erreal bati erantzuten diote: irakasleek AI plataforma komertzialak zuzenean erabiltzen dituztenean:

- **Beren ezagutza entregatzen dute** -- galderak eta materialak hornitzailearen entrenamendu-datu bihurtzen dira
- **Ikasleen datuak agerian uzten dituzte** -- ikasleen identitateak, galderak eta portaera hirugarrenek prozesatzen dituzte
- **Ez dute gardentasunik** -- ereduak nola jokatzen duen, zer datu gordetzen dituen eta nola eboluzionatzen duen opakuak dira
- **Ezin dute portaera pertsonalizatu** -- ez dago erantzunak ikastaroko materialetara mugatzeko edo ikuspegi pedagogikoak ezartzeko modurik
- **Saltzailearekiko menpekotasun-arriskua** -- hornitzailea aldatzeak dena berreraikitzea esan nahi du

LAMB-ek arazo horiek guztiak konpontzen ditu, erakundeari pila osoaren gaineko kontrol osoa emanez.

---

## 3. Norentzat da LAMB?

### Irakasleak (sortzaile-erabiltzaileak)

Irakasleak LAMB-en erabiltzaile nagusiak dira. **Sortzaile Interfazea** erabiltzen dute -- web-oinarritutako ingurune bat, koderik gabekoa -- honako hauetarako:

- Beren ikastaroetarako AI laguntzaile espezializatuak sortzea
- Ezagutza-baseak eraikitzea iturri aniztuetatik: fitxategi-igoerak (PDF, Word, PowerPoint, kalkulu-orriak, Markdown), web URLak eta arakatutako webguneak, eta YouTube bideoen transkripzioak
- AIaren portaera konfiguratzea (sistema-galderak, eredu-hautaketa, RAG ezarpenak)
- Ebaluazio-errubrikak sortzea eta laguntzaileetara eranstea AIren bidezko ebaluaziorako (Evaluaitor)
- Kalifikazio-jarduerak konfiguratzea, non ikasleek lanak aurkezten dituzten, AIak errubrika baten arabera ebaluazio-proposamena egiten duen, eta irakasleak azken nota berrikusten eta erabakitzen duen (LAMBA)
- Laguntzaileak ikasleei argitaratu aurretik probatzea
- Laguntzaileak LTI jarduera gisa Moodle-n argitaratzea
- Ikasleek laguntzaileak nola erabiltzen dituzten analitikak ikustea

**Ez da programazio-gaitasunik behar.** AIak ez du inoiz modu autonomoan kalifikatzen -- irakasleak laguntzen du ebaluazioak proposatuz, baina irakasleak beti berrikusten, editatzen eta azken nota berresten du. Irakasle batek bere lehen laguntzailea gutxi gorabehera 15 minututan sor eta argitara dezake.

### Erakundeetako administratzaileak (antolakuntza-administratzaileak)

Antolakuntza-administratzaileek beren saila edo erakundea kudeatzen dute LAMB-en barruan:

- Beren erakundeko erabiltzaileak kudeatzea (sortu, gaitu/desgaitu)
- AI hornitzaileak konfiguratzea (API gakoak, eredu erabilgarriak)
- Erregistro-politikak ezartzea (erregistro irekia edo gonbidapenez bakarrik)
- Laguntzaileen partekatzea bezalako funtzioak gaitu/desgaitzea
- Beren erakundeko LTI Sortzaile sarbidea kudeatzea

### Sistema-administratzaileak

Sistema-administratzaileek LAMB hedapena bera kudeatzen dute:

- LAMB azpiegitura hedatu eta mantentzea
- Erakundeak sortu eta kudeatzea (erabiltzaile anitzeko arkitektura)
- LLM hornitzaile eta API gako globalak konfiguratzea
- Sistema-mailako erabiltzaileak eta rolak kudeatzea
- LTI kredentzialak konfiguratzea
- Sistemaren osasuna eta errendimendua monitorizatzea

---

## 4. Gaitasun nagusiak

### Irakaskuntzarako

| Gaitasuna | Deskribapena |
|-----------|-------------|
| **Laguntzaile mugagabeak** | Behar adina AI laguntzaile sortu, bakoitza portaera bereziduna |
| **Irakasgai-tutore espezializatuak** | Irakasleak definitutako ikastaroko testuinguruan bakarrik erantzuten duten laguntzaileak |
| **Ezagutza-basea (RAG)** | Fitxategietatik (PDF, Word, PowerPoint, kalkulu-orriak), web URLetatik, webgune-arakatzeetatik eta YouTube bideoen transkripzioetatik edukia xurgatu -- AIak hauek bere "testu-liburu" gisa erabiltzen ditu |
| **Aipamen automatikoak** | AIak igotako materialak erreferentziatzen dituenean, iturria aipatzen du |
| **AI eredu anitzak** | GPT-4o, Mistral, Llama eta beste eredu batzuen artean aldatu klik bakar batez |
| **Arazketa-modua** | AIari bidalitako galdera osoa ikusi, doikuntza fina ahalbidetuz |
| **LTI argitalpena** | Laguntzaileak Moodle jarduera gisa argitaratu klik gutxirekin |
| **Laguntzaileen partekatzea** | Laguntzaileak lankideekin partekatu erakunde berean |
| **Errubriketan oinarritutako ebaluatzaileak** | Ebaluazio-errubrika egituratuak sortu (eskuz edo AIak sortuta) eta laguntzaileetara erantsi AIren bidezko ebaluazio koherenterako |
| **AIren bidezko ebaluazioa (LAMBA)** | Ikasleek lanak aurkezten dituzte LTI bidez; AIak errubrikaren araberako ebaluazioa proposatzen du; irakasleak berrikusten, editatzen eta azken nota erabakitzen du; puntuazioak Moodle-ra sinkronizatzen dira |
| **Txat-analitikak** | Ikasleek zure laguntzaileekin nola elkarreragiten duten ikusi |
| **Eleaniztuna** | Interfazea ingelesez, gaztelaniaz, katalanez eta euskaraz eskuragarri |

### Administraziorako

| Gaitasuna | Deskribapena |
|-----------|-------------|
| **Erabiltzaile anitzeko arkitektura** | Erakunde isolatuak konfigurazio independentearekin |
| **Erabiltzaileen kudeaketa** | Erabiltzaile-kontuak sortu, gaitu/desgaitu eta kudeatu |
| **Roletan oinarritutako sarbidea** | Sistema-administratzaile, erakunde-administratzaile, sortzaile eta azken erabiltzaile rolak |
| **LLM hornitzaile-malgutasuna** | OpenAI, Anthropic, Ollama edo beste hornitzaileak konfiguratu erakundeko |
| **Erregistro-gakoak** | Erakundeko erregistro espezifikoa gako sekretu batekin |
| **LTI Sortzaile sarbidea** | Irakasleek LAMB zuzenean Moodle-tik atzi dezakete LTI bidez |

### Azpiegiturarako

| Gaitasuna | Deskribapena |
|-----------|-------------|
| **Norberak ostatatua** | Zure zerbitzarietan hedatu -- datuen subiranotasun osoa |
| **Docker hedapena** | Komandu bakarreko hedapena Docker Compose-rekin |
| **OpenAI-rekin bateragarria den APIa** | `/v1/chat/completions` amaiera-puntu estandarra integraziorako |
| **Plugin arkitektura** | LLM hornitzaile berrietarako konektore hedagarriak |
| **SQLite datu-basea** | Datu-base sinple bat fitxategietan oinarritua (ez da DB zerbitzari bereizik behar) |

---

## 5. Nola funtzionatzen du -- Irakasleentzat

### Irakaslearen lan-fluxua (15 minutu lehen laguntzailerako)

#### 1. urratsa: Saioa hasi
Hasi saioa LAMB Sortzaile Interfazean zure erakundeko kredentzialekin (edo LTI bidez Moodle-tik).

#### 2. urratsa: Laguntzaile bat sortu
Eman izena eta deskribapena zure laguntzaileari. Aukeratu AI eredu bat (adib., GPT-4o-mini erantzun azkarretarako, GPT-4o arrazonamendu konplexurako).

#### 3. urratsa: Portaera definitu
Idatzi **sistema-galdera** bat AIari nola jokatu behar duen esateko. Adibidez:

> *"Informatikaren Sarrerako tutore bat zara. Algoritmoekin, datu-egiturekin eta programazioaren oinarriekin lotutako galderak bakarrik erantzun. Ikasleek ikastaroaz kanpoko gaiei buruz galdetzen dutenean, modu atseginez berbideratu. Beti animatu ikasleak arazoak pentsatzera erantzun zuzena eman aurretik."*

#### 4. urratsa: Ezagutza-base bat eraiki (aukerakoa baina gomendatua)
Gehitu zure ikastaroko materialak iturri aniztuetatik:
- **Fitxategiak igo** -- apunteak, testu-liburuko kapituluak, ariketa-multzoak (PDF, Word, PowerPoint, kalkulu-orriak, Markdown, eta gehiago)
- **URLetatik xurgatu** -- web-orri batera apuntatu edo arakatzaileari gune bateko estekak jarraitzen utzi
- **YouTube bideoak inportatu** -- automatikoki atera eta indexatu bideoen transkripzioak

LAMB-ek eduki guztia prozesatzen eta indexatzen du, AIak galderak erantzutean erreferentzia egin dezan.

#### 5. urratsa: RAG konfiguratu
Konektatu zure ezagutza-basea laguntzailearekin. Konfiguratu zenbat testuinguru-zati berreskuratu (Top K). AIak orain zure ikastaroko material errealetan oinarrituko ditu erantzunak eta iturriak aipatuko ditu.

#### 6. urratsa: Probatu
Erabili barneratutako txat-interfazea zure laguntzailea probatzeko. Egin zure ikasleek egin litzaketen galderak. Erabili **arazketa-modua** AIak jasotzen duen galdera eta testuingurua zehatz-mehatz ikusteko.

#### 7. urratsa: Moodle-n argitaratu
Klikatu "Argitaratu." LAMB-ek LTI kredentzialak sortzen ditu (Tresnaren URLa, Kontsumitzaile Gakoa, Sekretua). Gehitu hauek Moodle-n Kanpoko Tresna jarduera gisa. Ikasleek orain laguntzailera zuzenean atzi dezakete beren ikastaroko orritik.

### Bi modu LAMB-era irakasle gisa sartzeko

1. **Zuzeneko saioa** -- Nabigatu LAMB URLra eta hasi saioa helbide elektronikoarekin/pasahitzarekin
2. **LTI Sortzaile abiaraztea** -- Klikatu LTI esteka bat Moodle-n eta zuzenean Sortzaile Interfazean aterako zara (ez da pasahitz bereizik behar). Hau zure erakundeko administratzaileak konfiguratzen du.

---

## 6. Nola funtzionatzen du -- LTI integrazioa Moodle-rekin

LTI (Learning Tools Interoperability) LAMB Moodle-ra konektatzen duen protokolo estandarra da. LAMB-ek hiru LTI integrazio modu onartzen ditu:

### 6.1 LTI Bateratua (gomendatua hedapen berrietarako)

**LTI Bateratua** ikuspegiak LTI tresna bakarra erabiltzen du LAMB instantzia osorako. Aukera malguena eta funtzio gehien dituena da.

**Nola funtzionatzen du:**

1. Sistema-administratzaileak **LTI kredentzialen multzo global bakarra** konfiguratzen du LAMB instantzia osorako
2. Moodle administratzaile batek LAMB Kanpoko Tresna gisa gehitzen du kredentzialen global hauekin
3. Irakasleek LAMB jarduerak gehitzen dituzte beren ikastaroetan Moodle-n
4. **Lehen aldiko konfigurazioa:** Irakasle batek jardueran lehen aldiz klik egitean, konfigurazio-orri bat ikusten du non argitaratutako laguntzaileetatik zeintzuk egongo diren eskuragarri hautatzen duen
5. **Konfigurazioaren ondoren:** Jardueran klik egiten duten ikasleek hautatutako laguntzaileak ikusten dituzte eta txateatzen has daitezke
6. **Irakaslearen panela:** Irakasleek erabilera-estatistikak, ikasleen sarbide-erregistroak eta (gaituz gero) anonimizatutako txat-transkripzioen berrikuspena erakusten duen panel bat dute

**Ezaugarri nagusiak:**
- Jarduera bakoitzeko laguntzaile anitz (ikasleek aukera dezakete)
- Irakaslearen panela erabilera-estatistikekin
- Txaten ikusgaitasun aukerakoa (transkripzio anonimizatuak berrikuspen pedagogikorako)
- Ikasleen baimena txaten ikusgaitasuna gaituta dagoenean
- LTI kredentzialen multzo bakarra instantzia osorako

**Ikaslearen esperientzia:**
1. Klikatu jarduera-esteka Moodle-n
2. (Txaten ikusgaitasuna gaituta badago eta lehen sarbidea bada) Onartu adostasun-oharra
3. Eskuragarri dauden laguntzaileak ikusi eta txateatzen hasi
4. Dena Moodle-ren barruan gertatzen da -- ez da saio-hasiera bereizik behar

### 6.2 LTI Zaharra (laguntzaile bakarra jarduera bakoitzeko)

Argitaratutako laguntzaile bakoitzak bere LTI kredentzialak dituen ikuspegi zaharragoa. Oraindik onartzen da, baina malguagoa da.

**Nola funtzionatzen du:**
1. Irakasleak laguntzaile bat argitaratzen du LAMB-en
2. LAMB-ek LTI kontsumitzaile-gako eta sekretu bakarrak sortzen ditu laguntzaile horretarako
3. Irakasleak hauek Kanpoko Tresna gisa gehitzen ditu Moodle-n
4. Ikasleek estekan klik egiten dute eta zuzenean laguntzaile horretara joaten dira

### 6.3 LTI Sortzailea (irakasleen sarbidea LAMB-era Moodle-tik)

Modu honek irakasleei LAMB Sortzaile Interfazea bera atzitzeko aukera ematen die Moodle-tik, LAMB saio-hasiera kredentzial bereizien beharra ezabatuz.

**Nola funtzionatzen du:**
1. Erakundeko administratzaileak LTI Sortzaile kredentzialak konfiguratzen ditu
2. Moodle administratzaileak LAMB Sortzailea Kanpoko Tresna gisa gehitzen du
3. Irakasle batek estekan klik egitean, zuzenean LAMB Sortzaile Interfazean ateratzen da
4. Bere identitatea LMS kontuan lotuta dago -- ez da pasahitz bereizik behar
5. Laguntzaileak ohiko moduan sor eta kudea ditzake

---

## 7. Nola funtzionatzen du -- Erakundeetako administratzaileentzat

### Erakundearen kudeaketa

LAMB-ek **erabiltzaile anitzeko** eredu bat erabiltzen du, non erakunde, sail edo talde bakoitza **antolakuntza** bat den. Antolakuntzek isolamendu osoa eskaintzen dute:

- Antolakuntza bakoitzak bere erabiltzaileak, laguntzaileak eta ezagutza-baseak ditu
- Antolakuntza bakoitzak bere AI hornitzaileak eta API gakoak konfiguratzen ditu
- Antolakuntza bateko erabiltzaileek ezin dituzte beste baten baliabideak ikusi

### Ardura nagusiak

#### Erabiltzaileen kudeaketa
- Kontuak sortu irakasleentzat (sortzaile-erabiltzaileak) eta azken erabiltzaileentzat
- Erabiltzaile-kontuak gaitu/desgaitu
- Antolakuntza barruko erabiltzaile-rolak ezarri (administratzailea, kidea)
- Moodle-tik sartzen diren LTI Sortzaile erabiltzaileak kudeatu

#### AI hornitzaileen konfigurazioa
- Zein AI hornitzaile dauden eskuragarri konfiguratu (OpenAI, Anthropic, Ollama, etab.)
- Hornitzaile bakoitzerako API gakoak ezarri
- Eredu lehenetsiak definitu
- Irakasleek zein eredu erabil ditzaketen kontrolatu

#### Sarbide-politikak
- Erakundearen erregistro irekia gaitu/desgaitu
- Autoerregistrorako erregistro-gako bat ezarri
- Irakasleen arteko laguntzaileen partekatzea gaitu/desgaitu
- LTI Sortzaile sarbide-kredentzialak konfiguratu

#### Erabiltzaile motak

| Erabiltzaile mota | Sarbidea | Helburua |
|-------------------|---------|----------|
| **Sortzailea** | Sortzaile Interfazea (laguntzaile-eraikitzailea) | Laguntzaileak sortzen eta kudeatzen dituzten irakasleak |
| **Azken erabiltzailea** | Txat-interfazea soilik (Open WebUI) | Argitaratutako laguntzaileekin bakarrik elkarreragin behar duten erabiltzaileak |
| **LTI Sortzailea** | Sortzaile Interfazea (Moodle LTI bidez) | LAMB LMS bidez atzitzen duten irakasleak |

---

## 8. Nola funtzionatzen du -- Sistema-administratzaileentzat

### Hedapena

LAMB **norberak ostatatutako hedapenerako** diseinatuta dago Docker Compose erabiliz. Pilan honako hauek daude:

| Zerbitzua | Portua | Helburua |
|-----------|--------|----------|
| **Backend** (FastAPI) | 9099 | API nagusia, autentifikazioa, osatzeen kanalizazioa |
| **Frontend** (Svelte) | 5173 (gar.) | Sortzaile Interfaze web-aplikazioa |
| **Open WebUI** | 8080 | Txat-interfazea ikasleentzat eta azken erabiltzaileentzat |
| **KB Zerbitzaria** | 9090 | Ezagutza-baseetako dokumentuen prozesatzea eta bilaketa bektoriala |

### Hasiera azkarra
```bash
git clone https://github.com/Lamb-Project/lamb.git
cd lamb
./scripts/setup.sh
docker-compose up -d
```

### Konfigurazio nagusia

| Aldagaia | Helburua |
|----------|----------|
| `LAMB_DB_PATH` | LAMB datu-basearen direktorioaren bidea |
| `OWI_DATA_PATH` | Open WebUI datuen direktorioaren bidea |
| `LAMB_BEARER_TOKEN` | Osatzeen amaiera-punturako API gakoa (**aldatu balio lehenetsia!**) |
| `LAMB_JWT_SECRET` | JWT tokenak sinatzeko sekretua (**ezarri balio seguru bat!**) |
| `OPENAI_API_KEY` | OpenAI API gako lehenetsia (erakundeko gainditu daiteke) |
| `LTI_GLOBAL_CONSUMER_KEY` | LTI Baturako LTI kontsumitzaile-gako globala |
| `LTI_GLOBAL_SECRET` | LTI sekretu partekatua globala |
| `OWI_BASE_URL` | Open WebUI-rako barneko URLa |
| `OWI_PUBLIC_BASE_URL` | Open WebUI-rako publikotik ikusgai den URLa |

### Sistemaren administrazio-zereginak

- **Erakundeak sortu** -- Sail edo erakundeentzako maizter isolatuak konfiguratu
- **Erabiltzaile globalak kudeatu** -- Sistema-administratzaile kontuak sortu, erabiltzaile guztiak kudeatu
- **LTI konfiguratu** -- LTI Baturako LTI kredentzialen globalak konfiguratu
- **Osasuna monitorizatu** -- `GET /status` amaiera-puntua osasun-egiaztapenetarako
- **Datu-baseen babeskopiak** -- SQLite datu-base fitxategien babeskopiak aldizka egin
- **SSL/TLS** -- HTTPS konfiguratu Caddy edo alderantzizko proxy bidez
- **LLM hornitzaileen kudeaketa** -- Sistema-mailako lehenespenak konfiguratu, API erabilera monitorizatu

### Produkziorako egiaztapen-zerrenda

- [ ] Aldatu `LAMB_BEARER_TOKEN` balio lehenetsitik
- [ ] Ezarri `LAMB_JWT_SECRET` ausazko balio seguru batera
- [ ] SSL/TLS konfiguratu (Caddy gomendatua)
- [ ] Datu-baseen babeskopia erregularra konfiguratu
- [ ] Erakundeko LLM API gakoak konfiguratu
- [ ] Erregistro-maila ezarri (`GLOBAL_LOG_LEVEL=WARNING` produkziorako)
- [ ] Sistemaren monitorizazioa konfiguratu
- [ ] LTI integrazioa hasieratik amaierara probatu

### Erabiltzaile anitzeko arkitektura

```
Sistema Erakundea (beti existitzen da, ezin da ezabatu)
    |
    +-- A Saila (slug: "engineering")
    |   +-- Erabiltzaileak (rolekin: jabea, administratzailea, kidea)
    |   +-- Laguntzaileak
    |   +-- Ezagutza-baseak
    |   +-- LLM hornitzaile konfigurazio independentea
    |
    +-- B Saila (slug: "physics")
    |   +-- Erabiltzaileak
    |   +-- Laguntzaileak
    |   +-- Ezagutza-baseak
    |   +-- LLM hornitzaile konfigurazio independentea
    |
    +-- Bazkide Erakundea (slug: "partner-univ")
        +-- ...
```

---

## 9. AIren bidezko ebaluazioa: Evaluaitor eta LAMBA

LAMB-ek barneratutako **Evaluaitor** sistema du errubriketan oinarritutako ebaluaziorako, eta **LAMBA** (Learning Activities & Machine-Based Assessment) aplikazioa plataforman integratzen ari da AIren bidezko ebaluazio-kanalizazio oso bat eskaintzeko. Ezinbestekoa da adieraztea **AIak ez duela inoiz modu autonomoan kalifikatzen** -- irakasleak berrikusi, behar izanez gero editatu eta esplizituki onartu beharreko ebaluazioak proposatzen ditu, nota ikasleari iritsi aurretik. Hau Manifestuaren 1. Printzipioaren (Giza gainbegiratzea) aplikazio zuzena da.

### 9.1 Evaluaitor: errubriketan oinarritutako ebaluazioa

Evaluaitor LAMB-en errubrika-kudeaketa sistema da. Irakasleei ebaluazio-errubrika egituratuak sortzeko eta laguntzaileetara eransteko aukera ematen die, edozein laguntzaile AI ebaluatzaile koherente bihurtuz.

#### Errubrikak sortzea

Irakasleek errubrikak hiru modutan sor ditzakete:

1. **Eskuzko sorrera** -- Irizpideak, errendimendu-mailak, pisuak eta puntuazioak hutsetik definitu
2. **AI bidezko sorrera** -- Deskribatu zer ebaluatu nahi duzun hizkuntza naturalean eta AIak errubrika osoa sortzen du (ingelesa, gaztelania, katalana eta euskara onartzen ditu)
3. **Txantiloietatik** -- Lankideek partekatutako edo administratzaileek erakusketa-txantiloi gisa sustatutako errubrika publiko bat bikoiztu

#### Errubrikaren egitura

Errubrika bakoitzak honako hauek ditu:
- **Izenburua eta deskribapena** -- Zer ebaluatzen den
- **Irizpideak** -- Ebaluazioaren dimentsioak (adib., "Edukiaren Kalitatea", "Pentsamendu Kritikoa"), bakoitza pisu batekin
- **Errendimendu-mailak** -- Kalitate-maila bakoitzaren deskribapenak (adib., Bikaina / Gaitua / Garatzen / Hasiberria) puntuazioekin
- **Puntuazio mota** -- Puntuak, ehunekoa, holistikoa, puntu bakarrekoa, edo egiaztapen-zerrenda
- **Metadatuak** -- Irakasgai-arloa, maila

#### Errubrikak laguntzaileekin erabiltzea

Errubrika bat laguntzaile bati eransten zaionean, LAMB-en osatzeen kanalizazioak automatikoki errubrika txertatzen du AIaren testuinguruan ebaluaziorako optimizatutako formatuarekin -- puntuazio-argibideak, pisuen kalkuluak eta espero den irteerako formatua barne. Horrek esan nahi du AIak errubrikaren irizpide zehatzen araberako ebaluazio-proposamen koherenteak sortzen dituela, irakasleak gero berrikusten eta amaitzen dituenak.

#### Partekatzea eta txantiloiak

- Errubrikak **pribatuak** (sortzaileak bakarrik ikusten ditu) edo **publikoak** (erakundeko kide guztien eskura) izan daitezke
- Administratzaileek errubrikak plataforma osoan eskuragarri dauden **erakusketa-txantiloi** gisa sustatu ditzakete
- Errubrikak JSON formatuan **esportatu/inportatu** daitezke erakundeen artean partekatzeko

### 9.2 LAMBA: kalifikazio-kanalizazioa (integratzen)

LAMBA LTI aplikazio bereizi gisa hasi zen eta orain zuzenean LAMB-en integratzen ari da. Ebaluazioaren bizi-ziklo osoa eskaintzen du Moodle bidez:

#### Ebaluazio lan-fluxua

1. **Irakasleek ebaluazio-jarduerak sortzen dituzte** Moodle-n LTI bidez eta errubriketan oinarritutako ebaluatzaile-laguntzaile bat esleitzen dute
2. **Ikasleek dokumentuak igotzen dituzte** (PDF, Word, TXT, iturburu-kodea) Moodle interfazearen bidez
3. **AIak ebaluazioak proposatzen ditu** -- laguntzaileak aurkezpen bakoitza errubrikaren arabera aztertzen du eta iradokitako puntuazioa eta idatzizko iritzia sortzen ditu
4. **Irakasleek AIaren proposamenak berrikusten dituzte** -- ikasle bakoitzeko iradokitako puntuazioa eta iritzia onartu, editatu edo guztiz gainidatzi dezakete
5. **Irakasleek azken nota berresten dute** -- irakasleak onartutako nota bakarrik da benetako nota
6. **Azken notak Moodle-ko kalifikazio-liburura sinkronizatzen dira** LTI bidez

#### Ezaugarri nagusiak

| Ezaugarria | Deskribapena |
|------------|-------------|
| **Errubrikak gidatutako proposamenak** | AIak errubrika egituratuen araberako ebaluazioak proposatzen ditu, irakasleari hasiera-puntu koherente bat emanez |
| **Irakasleak du azken hitza** | AIaren iradokizuna eta benetako nota eremu bereiziak dira -- irakasleak esplizituki proposatutako ebaluazioa azken notara eraman behar du, behar izanez gero editatuz |
| **Talde-aurkezpenak** | Talde-lanak onartzen ditu aurkezpen-kode partekatuekin |
| **Moodle nota-sinkronizazioa** | Irakasleak berrestutako azken notak bakarrik bidaltzen dira Moodle-ko kalifikazio-liburura |
| **Prozesatze masiboa** | Aurkezpen guztietarako AI proposamenak eskatu aldi berean, denbora errealean aurrerapena jarraituz |
| **Giza gainbegiratzea** | AIak laguntzen du; irakasleak erabakitzen du -- Manifestuaren 1. Printzipioarekin koherentea |

#### Helburua

Irakasleen ebaluazio-lan karga **%50** murriztea ohiko ebaluazioetan, proposatutako iritzia minututan eman egunetan beharrean. AIak errubriketan oinarritutako hasiera-puntu koherente bat eskaintzen du, baina **irakasleak beti mantentzen du azken notaren gaineko aginte osoa**.

---

## 10. Arkitekturaren ikuspegi orokorra

```
+------------------------------------------------------------------+
|                         LAMB Plataforma                          |
|                                                                  |
|   +----------------+    +----------------+    +----------------+ |
|   |   Sortzaile    |    |   Backend      |    |   Open WebUI   | |
|   |   Interfazea   |<-->|   (FastAPI)     |<-->|   (Txat UI)    | |
|   |   (Svelte)     |    |   9099 portua  |    |   8080 portua  | |
|   +----------------+    +-------+--------+    +----------------+ |
|          |                      |                      |         |
|    Irakasleek hau          Oinarrizko           Ikasleek hau     |
|    erabiltzen dute         logika                erabiltzen dute  |
|    laguntzaileak           eta APIa              txateatzeko      |
|    eraikitzeko                   |                                |
|                          +------+-------+                        |
|                          |  KB          |                        |
|                          |  Zerbitzaria |                        |
|                          |  9090 portua |                        |
|                          +--------------+                        |
|                                 |                                |
|                          +------+-------+                        |
|                          | LLM          |                        |
|                          | Hornitzailea |                        |
|                          | OpenAI/Ollama|                        |
|                          +--------------+                        |
+------------------------------------------------------------------+
         |                                           |
    LTI Sortzailea                              LTI Ikaslea
    (Irakasleek LAMB                            (Ikasleek
     atzitzen dute                               laguntzaileak
     Moodle-tik)                                 atzitzen dituzte
         |                                       Moodle-tik)
         |                                           |
+------------------------------------------------------------------+
|                     Moodle (LMS)                                 |
+------------------------------------------------------------------+
```

### Nola erantzuten zaio ikasle baten galderari

1. Ikasleak galdera bat idazten du txat-interfazean (Open WebUI, LTI bidez abiarazita)
2. Galdera LAMB-en osatzeen APIra doa
3. LAMB-ek laguntzailearen konfigurazioa kargatzen du (sistema-galdera, eredua, RAG ezarpenak)
4. **RAG Prozesadoreak** ezagutza-basea kontsultatzen du igotako dokumentuetatik eduki garrantzitsua bilatzeko
5. **Galdera Prozesadoreak** sistema-galdera, berreskuratutako testuingurua eta ikaslearen galdera konbinatzen ditu
6. **Konektoreak** dena konfiguratutako LLMra bidaltzen du (adib., OpenAI GPT-4o)
7. LLMaren erantzuna iturri-aipamenekin ikaslearengana itzultzen da

---

## 11. Pribatutasuna eta datuen subiranotasuna

### Non daude datuak

| Datuak | Kokalekua | Nork kontrolatzen du |
|--------|-----------|---------------------|
| Erabiltzaile-kontuak | LAMB datu-basea (erakundearen zerbitzarian) | Erakundeak |
| Laguntzaileen konfigurazioak | LAMB datu-basea | Irakasleak + erakundeak |
| Ikastaroko materialak (EBak) | ChromaDB erakundearen zerbitzarian | Irakasleak + erakundeak |
| Txat-historia | Open WebUI datu-basea erakundearen zerbitzarian | Erakundeak |
| Ikasleen elkarrekintzak | Erakundearen zerbitzaria | Erakundeak |

### Zer EZ da erakundetik irteten

- Ikasleen identitateak eta datu pertsonalak
- Txat-elkarrizketak eta elkarrekintza-historia
- Igotako ikastaroko materialak eta ezagutza-baseak
- Erabilera-analitikak eta ebaluazio-datuak

### Zer bidaltzen da kanpoko zerbitzuetara (konfiguragarria)

- **Galderen testua eta testuingurua soilik** bidaltzen dira konfiguratutako LLM hornitzailera (OpenAI, etab.)
- Hau **guztiz ezabatu** daiteke lokalki ostatatutako ereduak erabiliz (Ollama Llama, Mistral, etab.-ekin)
- Erakundeak aukeratzen du zein LLM hornitzaile erabili eta edozein unetan alda dezake

### GDPR eta FERPA lerrokatzea

- Norberak ostatatua: datuen egoitzari buruzko eskakizunekin erabateko betetzea
- Ez da nahitaezko hirugarrenen erregistrorik ikasleentzat
- Ikasleek laguntzaileetara beren lehendik dagoen LMS bidez sartzen dira -- ez dira kontu berriak behar
- Datuen atxikipena argia erakundearen kontrolpean
- Txaten ikusgaitasun aukerakoek ikasleen adostasun esplizitua behar dute

---

## 12. Glosarioa

| Terminoa | Definizioa |
|----------|-----------|
| **Laguntzailea** | Irakasle batek portaera, ezagutza eta eredu-ezarpen zehatzekin konfiguratutako AI bidezko chatbot bat |
| **Sortzaile Interfazea** | Irakasleek laguntzaileak eraikitzen eta kudeatzen dituzten web-oinarritutako erabiltzaile-interfazea |
| **Ezagutza-basea (EB)** | AIak galderak erantzutean erreferentzia egin dezakeen igotako dokumentuen bilduma |
| **RAG** | Retrieval-Augmented Generation (Berreskuratze bidez Indartutako Sorrera) -- dokumentu-zati garrantzitsuak berreskuratu eta AI galderetan txertatzeko teknika |
| **LTI** | Learning Tools Interoperability (Ikaskuntza Tresnen Elkarreragingarritasuna) -- kanpoko tresnak LMS batera konektatzeko protokolo estandarra |
| **LMS** | Learning Management System (Ikaskuntza Kudeaketa Sistema) (adib., Moodle, Canvas) |
| **Antolakuntza** | LAMB-en maizter isolatu bat (saila, erakundea edo taldea) bere erabiltzaile eta konfigurazioarekin |
| **Open WebUI (OWI)** | Ikasleek argitaratutako laguntzaileekin elkarreragiten duten txat-interfazearen osagaia |
| **Sistema-galdera** | AI laguntzaile baten portaera definitzen duten argibideak (pertsonaia, arauak, mugak) |
| **Konektorea** | LAMB LLM hornitzaile zehatz batera konektatzen duen plugina (OpenAI, Ollama, Anthropic) |
| **LTI Bateratua** | Tresna bakarrak jarduera bakoitzeko laguntzaile anitz zerbitzatzen dituen gomendatutako LTI modua |
| **LTI Sortzailea** | Irakasleei Moodle-tik Sortzaile Interfazea atzitzeko aukera ematen dien LTI modua |
| **Evaluaitor** | LAMB-en barneratutako errubrika-kudeaketa sistema, ebaluazio-irizpide egituratuak sortzeko |
| **Errubrika** | Ikasleen lana modu koherentean ebaluatzeko erabiltzen den irizpide-multzo egituratua, errendimendu-mailekin eta pisuekin |
| **LAMBA** | Learning Activities & Machine-Based Assessment (Ikaskuntza Jarduerak eta Makinan Oinarritutako Ebaluazioa) -- AIren bidezko ebaluazio-kanalizazioa (LAMB-en integratzen). AIak ebaluazioak proposatzen ditu; irakasleak azken nota erabakitzen du. |
| **Manifestua** | Safe AI in Education Manifesto -- LAMB-en diseinua gidatzen duen esparru etikoa |

---

## Esteka nagusiak

| Baliabidea | URLa |
|------------|------|
| LAMB GitHub biltegia | https://github.com/Lamb-Project/lamb |
| LAMB Proiektuaren webgunea | https://lamb-project.org |
| LAMBA (Kalifikazio-hedapena) | https://github.com/Lamb-Project/LAMBA |
| Safe AI in Education Manifesto | https://manifesto.safeaieducation.org |
| Manifestuaren egiaztapen-zerrenda | https://manifesto.safeaieducation.org/checklist |
| Ikerketa-artikulua (DOI) | https://doi.org/10.1016/j.csi.2024.103940 |

---

*Dokumentu hau LAMB proiekturako eragileentzako prestakuntza-material gisa prestatu zen.*
*Azken eguneratzea: 2026ko otsailaren 15a*
