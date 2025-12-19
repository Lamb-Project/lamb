# LAMB - Learning Assistants Manager and Builder

**IAn oinarritutako ikaskuntza-laguntzaileak kodea idatzi gabe diseinatzeko, entrenatzeko eta argitaratzeko web plataforma**

---

## Zer da LAMB?

**LAMB** kode irekiko web-plataforma bat da, **IAn oinarritutako ikaskuntza-laguntzaileak diseinatzeko, entrenatzeko eta argitaratzeko** modu bisual eta intuitiboan. "Irakasle-chatbot eraikitzaile" gisa funtzionatzen du, hizkuntza-modeloak (GPT-4, Mistral, tokiko modeloak) zure hezkuntza-materialekin konbinatuz.

**LAMB** Marc Alier eta Juanan Pereira UPCko (Kataluniako Unibertsitate Politeknikoa) eta EHUko (Euskal Herriko Unibertsitatea) irakasle eta ikertzaileek garatutako kode irekiko proiektu bat da.

- **Website:** [http://www.lamb-project.org](http://www.lamb-project.org)
- **GitHub:** [https://github.com/Lamb-Project/lamb](https://github.com/Lamb-Project/lamb)
- **Lizentzia:** GPL v3
- **Manifestua:** [Safe AI Education](https://manifesto.safeaieducation.org)

---

## Ezaugarri Nagusiak

### 🎓 Gai Berezidunen Tutorak
Hautatu duzun gaiari buruz bakarrik erantzuten duten laguntzaileak diseinatu, beti hezkuntza-testuinguru egokian mantenduz.

### 📚 Ezagutza Jasotzea Adimentsua
Kargatu dokumentuak (PDF, Word, Markdown) eta LAMBek automatikoki prozesatzen ditu **datu-eredu malgu** batekin:
- Edukia ateratzen eta egituratzen du testuingurua eta erlazioak mantenduz
- Hezkuntza-bilaketarako optimizatutako embedding semantikoak sortzen ditu
- Dokumentu bakoitzerako metadatu pertsonalizatuak ahalbidetzen ditu
- Formatu eta eduki-egitura desberdinetara egokitzen da
- RAG (Retrieval Augmented Generation) bidez modeloa elikatzen du

### 🔍 Proba eta Arazketa Aurreratuak
"Debug" modua, modelora bidaltzen den promenada osoa erakusten duena, erantzunen optimizazioa erraztuz.

### 🎯 Moodlerekin LTI Integrazioa
Argitaratu laguntzailea kanpoko LTI tresna gisa eta txertatu zure Moodlen klik bi batzuetan.

### 🔒 Pribatutasuna Bermatua
Ikasleek LAMBen barnean elkarreragiten dute; haien datuak ez dira IA modelo hornitzaile kanpokoekin partekatzen.

---

## Norentzat da LAMB?

- **📖 Irakasleak eta trebatzaileak** haien curriculum zehatzean zentratutako laguntzaile birtual bat behar dutenak
- **🏫 Hezkuntza-zentroak** Moodle edo beste LMS batzuk erabiltzen dituztenak eta IA integratu behar dutenak ikasle-datuak agertu gabe
- **💡 Berrikuntza-taldeak** LLM desberdinekin esperimentatzen dutenak eta kudeaketa-panel unifikatu bat behar dutenak

---

## Funtzionalitate Nagusiak

### Laguntzaile Mugagabeak
Bakoitza bere jarraibide, doinua eta limite pertsonalizatuekin.

### Ezagutza-base Malguak
- **Datu-eredu moldagarria**: eduki eta egitura mota desberdinak baimentzen dituen arkitektura malgua
- PDF, DOCX, Markdown euskarria (formato gehiago laster)
- Base publikoak edo pribatuak beharren arabera
- Bilaketa semantikorako embedding bektorialen sistema
- Kanpo-iturrietarako konektoreak garatzen (Google Drive, YouTube, APIs)

### IA Modelo Anitzak
- OpenAI GPT-4o
- Mistral
- Tokiko modeloak
- Klik batean modelo aldaketa

### Aipamen Automatikoak
Laguntzaileak erantzunak ematen ditu erabilitako iturri-dokumentuetako erreferentziarekin.

### Eramangarritasun Osoa
- Laguntzaileak JSON formatuan esportatu/inportatu
- Bertsio-kontrola eta partekatzea erraza

### Interfaze Eleaniztuna
Euskera, gaztelania, ingelesa eta katalana serie gisa.

### Sarbide Kontrol Sendoa
- Gako sekretuak erregistroarentzat
- Base pribatuak erabilera baimenik gabeak saihesteko

### Hazten ari den Ekosistema
- **Arkitektura modular eta hedagarria**: funtzionalitate berriak nukleoa ukitu gabe txertatzeko diseinatua
- Datu-iturri desberdinetarako ingesta-plugin pertsonalizagarriak
- Hirugarrenekin integrazioetarako API irekia
- Etengabeko eguneraketak IA hornitzaile bakar baten menpekotasunik gabe
- Hezkuntza-beharrekin eboluzionatzen duen datu-eredu malgua

---

## Labur esanda

**LAMBek kontrol osoa ematen dizu zure gairako "ChatGPT espezializatu" bat eraikitzeko, zure Moodlera konektatzeko eta zure ikasleen datuak erabat seguru mantentzeko.**

---

## 🎓 Ikerketa eta Oinarri Akademikoa

**LAMB** ikerketa akademiko sendoan eraikita dago eta **[Hezkuntzako IA Seguruko Manifestua](https://manifesto.safeaieducation.org)**ri atxikitzen zaio - IAren hedapen etiko, seguru eta hezkuntza-lerrokatua lortzeko esparru integral bat.

### 📚 Argitalpen Akademikoa

LAMB zure ikerketetan erabiltzen baduzu, mesedez aipatu gure lana:

**"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"**

- **Egileak:** Marc Alier, Juanan Pereira, Francisco José García-Peñalvo, Maria Jose Casañ, Jose Cabré
- **Aldizkaria:** Computer Standards & Interfaces, 92. bolumena, 2025ko martxoa
- **DOI:** [10.1016/j.csi.2024.103940](https://doi.org/10.1016/j.csi.2024.103940)

### 🏛️ Bazkide Akademikoak

- **Euskal Herriko Unibertsitatea (EHU)** - Ikerketa erakundea eta garapen bazkidea
- **Kataluniako Unibertsitate Politeknikoa (UPC)** - Ikerketa erakundea eta garapen bazkidea
  - Bartzelonako Informatika Fakultatea
  - Institut de Ciències de l'Educació - ICE
  - Zerbitzu eta Informazio Sistemen Ingeniaritza Saila (ESSI)

### 🙏 Eskerrak

Esker bereziak **Open WebUI Proiektuari**, **Tsugi Proiektuari** (Dr. Chuck Severance), **TEEM Konferentzia** komunitateari, eta **Tknika** Euskal LHko Ikerketa Aplikatuko Zentroari haien laguntzarengatik eta kolaborazioagatik.

---

*Azken eguneratzea: 2025eko abendua*
