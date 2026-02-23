# LAMB Prestakuntza Ikastaroa -- Irakaskuntza Estrategia

**Bertsioa:** 1.0
**Data:** 2026ko otsailaren 15a
**Egoera:** Zirriborroa
**Hartzaileak:** Ikastaro diseinatzaileak, irakasleak

---

## 1. Ikastaroaren Nortasuna

**Izenburua:** *Ikaskuntza Laguntzaile Adimentsuak LAMB-ekin Eraikitzen -- Irakasleentzako Ikastaro Praktikoa*

**Formatua:** Hibridoa (Moodle ikastaro asinkronoa + AMA saio sinkronoak)

**Iraupena:** 3-4 aste (malgua, edukia pixkanaka banatua)

**Plataforma:** Moodle, LAMB LTI bidez integratuta

**Xede-publikoa:** Unibertsitateko irakasleak eta katedradunak, beren ikastaroetarako AA bidezko ikaskuntza-laguntzaileak sortu nahi dutenak. Ez da programazio trebetasunik behar.

---

## 2. Filosofia Pedagogikoa

### 2.1 Eginez Ikasi, ez Begira Egonez

Eduki guztiek ekintza-dei argi eta lorgarri bat dute. Partaideek ez dute inoiz begira egoten soilik -- beti egiten dute zerbait zehatza LAMB-ekin edukia ikusi ondoren. Helburua da ikastaroaren amaieran partaide guztiek gutxienez laguntzaile funtzional bat izan dezatela, argitaratua eta beren ikastaroko materialetan oinarritua.

### 2.2 Gure Produktua Bera Erabili

Ikastaroa bera LAMB-en gainean eraikita dago. Partaideek LAMB ikaslearen aldetik esperimentatzen dute (ikastaroko laguntzaile batekin elkarreraginez, LAMBA-k ebaluatzen dituela) eta, aldi berean, sortzaile izaten ikasten dute. Perspektiba bikoitz hau nahita da -- sentitzen dute beren ikasleek sentituko dutena.

### 2.3 Komunitateak Bultzatutako Edukia

Foroa ez da laguntza-kanal bat -- **eduki-motor** bat da. Partaideen galderek, frustrazioak eta ideiek bideo-grabazio, FAQ sarrera eta eztabaida bihurtzen dira. Ikastaroa aberatsago bihurtzen da kohorte bakoitzarekin. Partaideei esplizituki esaten zaie: zure galderek ikastaro hau hobea bihurtzen dute guztiontzat.

### 2.4 Pixkanaka, ez Uholde Moduan

Edukia 1-2 egunean behin argitaratzen da bideo labur eta zehatzetan (5-10 minutu gehienez). Honek erritmo bat sortzen du: ikusi, egin, partekatu, eztabaidatu. Gainezka egitea saihesten du eta irakasleei denbora ematen die foroan erantzuteko hurrengo argitalpena baino lehen.

### 2.5 Manifestuarekin Lerrokatzea

Ikastaroak Hezkuntzan AA Segurua Manifestuaren printzipioak gauzatzen ditu bere diseinuan:
- **Giza Gainbegiratzea** -- Irakaslea presente dago, erantzule da eta elkarrizketa gidatzen du
- **Pribatutasuna** -- Partaideek instituzionalki ostatatutako LAMB instantzia bat erabiltzen dute
- **Integrazio Didaktikoa** -- Ikastaroa Moodle-n barruan dabil, partaideek dagoeneko erabiltzen duten ingurune berean
- **Gardentasuna** -- Partaideek ikusten dute AA laguntzaileak nola funtzionatzen duen barrutik (arazketa modua, prompt ikuskapena)

---

## 3. Ikaskuntza Helburuak

Ikastaroaren amaieran, partaideek honako hau egin ahal izango dute:

### 1. Astea: Esperientzia eta Lehen "Uau" (Oinarrizkoa)
1. LAMB laguntzaileak azken erabiltzaile gisa esperimentatu -- sentitu ikasleek sentituko dutena
2. Azaldu zer den LAMB eta zergatik existitzen den (pribatutasuna, kontrola, manifestuaren printzipioak)
3. LAMB-en saioa hasi Moodle-tik LTI Creator bidez eta Sortzaile Interfazean nabigatu
4. Lehen laguntzailea sortu sistema-prompt batekin eta erantsitako fitxategi bakarrarekin (fitxategi bakarreko RAG) -- berehalako testuingurua konfigurazio konplexutasunik gabe
5. Laguntzailea probatu eta ikusi zure ikastaroko materialetako galderei nola erantzuten dien

### 2. Astea: Ezagutza Sakona eta Fintzea (Tartekoa)
6. Ezagutza-base osoa eraiki iturri anitzetatik (fitxategiak, URLak, YouTube)
7. Ezagutza-base bat laguntzaile bati konektatu (RAG konfigurazioa, Top K)
8. Fitxategi bakarreko RAG eta ezagutza-base osoen arteko aldea ulertu
9. Laguntzaile bat probatu eta arazketa modua erabiliz arazketa egin
10. Sistema-promptak iteratu laguntzailearen portaera hobetzeko

### 3. Astea: Argitaratzea, Ebaluazioa eta Haratago (Aurreratua)
11. Laguntzaile bat Moodle ikastaro batean LTI jarduera gisa argitaratu
12. Ebaluazio-errubrika bat sortu Evaluaitor erabiliz (eskuz edo AAk sortua)
13. Errubrika bat laguntzaile bati erantsi AA bidezko ebaluaziorako
14. LAMBA ebaluazio-lana ulertu (AAk proposatzen du, irakasleak erabakitzen du)

### Meta-Ikaskuntza (Ikastaro Osoan Zehar)
13. LAMB ikaslearen ikuspegitik esperimentatu (ikastaroko laguntzailearekin elkarreraginez)
14. AA bidezko ebaluazioa ikaslearen ikuspegitik esperimentatu (LAMBA)
15. AAren rola beren irakaskuntza-testuinguruan kritikoki ebaluatu

---

## 4. Ikastaroko Azpiegitura

### 4.1 Moodle Ikastaroaren Egitura

```
LAMB Prestakuntza Ikastaroa (Moodle)
|
+-- Iragarpenak (irakaslearen mezuen kanala)
|     Irakaslearen eguneraketetarako, bideo berrien argitalpenetarako
|     eta ohiko galderen erantzunetarako norabide bakarreko kanala.
|
+-- Eztabaida Foroa (guztientzat irekia)
|     Ikastaroaren bihotza. Partaideek galderak, funtzionalitate
|     eskaerak, frustrazioak, ideiak eta lorpenak argitaratzen dituzte.
|     Irakasleak testuz edo bideo-grabazio laburretan erantzuten du.
|
+-- Demo Laguntzaileak (LTI Kanpo Tresna -- Unified LTI)
|     1. asterako aurrez eraikitako laguntzaileak, azken erabiltzaile
|     esperientziarako. Partaideek ikasle gisa elkarreragiten dute
|     sortzaile bihurtu aurretik.
|     Adibideak: historia tutorea, matematika laguntzailea, hizkuntza entrenatzailea.
|
+-- LAMB Sortzaile Sarbidea (LTI Kanpo Tresna -- LTI Creator)
|     LTI Creator esteka -- klik batek partaideak zuzenean
|     LAMB Sortzaile Interfazera eramaten ditu.
|     Ez dira kredentzial berezirik behar.
|
+-- Ikastaroko AA Laguntzailea (LTI Kanpo Tresna -- Unified LTI)
|     LAMB laguntzaile bat, bideo transkripzio guztiekin
|     eta ikastaroko dokumentazioarekin kargatua. Partaideek
|     galderak egin diezazkiokete eta bideo eta denbora-marka
|     egokira birbideratzen ditu.
|
+-- Eduki Moduluak (bideo/gai bakoitzeko bat)
|     +-- Bideoa (txertatua edo estekatua)
|     +-- Idatzizko laburpena / transkripzioa
|     +-- Ekintza-deia (zeregin zehatza)
|     +-- Aukerazkoa: dokumentazio garrantzitsurako esteka
|
+-- Azken Entregagarria
|     Argitaratutako laguntzailearen esteka/deskribapena bidali.
|     LAMBA-k errubrika baten bidez ebaluatua.
|
+-- AMA Saioak (2-3 programatutako bideo-konferentzia)
      Bideo-konferentzia estekekin egutegi-gertaerak.
```

### 4.2 LAMB Konfigurazioa

**LTI Creator:** Partaideak `lti_creator` erabiltzaile gisa hornitzen dira prestakuntza-erakunde dedikatu batean. LAMB-era zuzenean Moodle-tik sartzen dira, saio-hasiera berezirik gabe.

**Demo Laguntzaileak (1. Astea):** 2-3 aurrez eraikitako laguntzaile, Unified LTI bidez argitaratuak, lehen egunetako azken erabiltzaile esperientziarako. Hauek txukunak, askotarikoak (gai desberdinak, tonu desberdinak) izan behar dute, eta ondo landutako laguntzaile batek nolakoa den eta nola sentitzen den erakutsi. Partaideek hauekin hitz egiten dute berea eraiki aurretik -- helburuaren barra ezartzen dute.

**Ikastaroko Laguntzailea:** LAMB laguntzaile argitaratu bat, honako hauek dituen ezagutza-base batekin:
- Bideo transkripzio guztiak (denbora-markekin eta bideo identifikatzaileekin)
- Interesdunen laburpen-dokumentua
- Foroko galderetik sortutako FAQ sarrerak

Laguntzailearen sistema-promptak honako hauek egiteko agintzen dio:
- LAMB-i buruzko galderei erantzun
- Bideo eta denbora-marka zehatzak aipatu garrantzitsua denean (adib., "Hori 5. Bideoan azaltzen da, 3:20-an")
- Erantzun ezin dituen galderetarako forora birbideratu
- Gardena izan LAMB-ekin berarekin eraikitako AA laguntzaile bat izateari buruz

**LAMBA Ebaluazioa:** Azken entregagarria (argitaratutako laguntzaile bat) errubrika baten bidez ebaluatzen da LAMBA-ren bitartez. AAk ebaluazioa proposatzen du; irakasleak berrikusi eta kalifikazioa finkatzen du. Partaideek LAMBA ikaslearen aldetik esperimentatzen dute.

### 4.3 Dogfooding Begizta

```
Partaideek foroan galderak egiten dituzte
        |
        v
Galdera onenak bideo-grabazio erantzun bihurtzen dira
        |
        v
Bideo-grabazio transkripzioak ikastaroko EB-an irensten dira
        |
        v
Ikastaroko AA laguntzaileak orain galdera horiei erantzun diezaieke
        |
        v
Partaideek laguntzaile hobea esperimentatzen dute
        |
        v
Ulertzen dute zergatik diren garrantzitsuak ezagutza-baseak BEREN laguntzaileentzat
```

Begizta hau esplizituki azaltzen zaie partaideei. Ikusten dute ikastaroko laguntzailea denbora errealean hobetzen dela eduki berria gehitzen den heinean, ezagutza-base bat mantendu eta haztearen balioa erakutsiz.

---

## 5. Eduki Plana: Bideo Seriea

Bideo bakoitza **5-10 minutukoa** da, zehatza, eta ekintza-dei konkretu batekin amaitzen da.

### 1. Astea: Lehenik Esperientzia, Gero Eraikitzea

Lehen astea **gozagarria eta berehala saritzailea** izateko diseinatuta dago. Partaideek azken erabiltzaile gisa hasten dute -- LAMB laguntzaileak beren ikasleek bezala esperimentatuz -- sortzaile aldera aldatu aurretik. Sortzea hasterakoan, **fitxategi bakarreko RAG** erabiltzen dute, eta horrek dokumentu bat laguntzaile bati eranstea ahalbidetzen du konfigurazio konplexutasunik gabe. Ez ezagutza-base sortzerik, ez zatiketa konfiguraziorik, ez itxaroterik. Fitxategi bat igo, hautatu, eta laguntzaileak berehala ezagutzen du zure ikastaroko edukia.

| # | Bideoaren Izenburua | Eduki Nagusia | Ekintza-Deia |
|---|------------|-------------|----------------|
| 1 | **Ezagutu Zure AA Tutorea** | Ikasle gisa hasi: elkarreragin 2-3 aurrez eraikitako demo laguntzailerekin (historia tutorea, matematika laguntzailea, hizkuntza entrenatzailea). Sentitu esperientzia. Ohartu bakoitzak nortasun, irismen eta ezagutza desberdina duela. | Txateatu demo laguntzaile bakoitzarekin. Argitaratu foroan: zeinek harritu zintuen gehien eta zergatik? Zer nahiko zenuke ZURE ikastarorako? |
| 2 | **Zergatik LAMB? Kontrola, Pribatutasuna eta Manifestua** | Orain sentitu duzunean -- zergatik existitzen da hau? ChatGPT-rekin pribatutasun kezkak, manifestuaren printzipioak, kontrol instituzionala, hezkuntza-helburuko AA vs. helburu orokorreko tresnak. | Irakurri manifestua (edo gainbegiratu). Argitaratu foroan: zer kezka dituzu AAri buruz zure ikastaroetan? |
| 3 | **Zure Lehen Saioa eta Zure Lehen Laguntzailea** | Egin klik LTI Creator estekan Moodle-n. Sartu Sortzaile Interfazean. Sortu laguntzaile bat: izena, deskribapena, aukeratu eredu bat, idatzi oinarrizko sistema-prompt bat. Sinplea izan. | Hasi saioa LAMB-en Moodle-tik. Sortu laguntzaile bat zure ikastarorako sistema-prompt sinple batekin (adib., "Zu [zure gaia]-ko tutore bat zara. Izan laguntzailea eta adoretsua."). |
| 4 | **Magia Trikimailua: Erantsi Fitxategi bat eta Behatu** | Aurkeztu fitxategi bakarreko RAG: hautatu "single_file_rag" RAG prozesadore gisa, igo fitxategi bat (zure programazioa, kapitulu laburpen bat, kontzeptu gakoen multzo bat -- .txt edo .md fitxategi bat besterik ez), hautatu, gorde. Orain probatu: galdetu laguntzaileari zure ikastaroko edukiari buruz. Badaki. | Igo dokumentu bat zure ikastarotik eta erantsi zure laguntzaileari. Egin 5 galdera fitxategi horretako ezagutza behar dutenak. Argitaratu foroan: zein izan zen "uau" momentua? |
| 5 | **Ikastaroko Laguntzailea eta Gure Produktua Bera Erabiltzea** | Erakutsi ikastaroaren LAMB laguntzailea. Erakutsi nola erreferentziatzen dituen bideo eta denbora-marka zehatzak. Azaldu dogfooding kontzeptua: ikastaro hau LAMB-en gainean dabil. Eraikitzen ikasten ari zaren guztia, ikasle gisa ere esperimentatzen ari zara. | Probatu ikastaroko laguntzailea. Galdetu aste honetan ikasitakoari buruz. Konparatu bere erantzunak 1. Bideoko demo laguntzaileekin -- zer da desberdina benetako edukia duen laguntzaile batean? |

### 2. Astea: Ezagutza Sakona eta Fintzea

Orain partaideek fitxategi bakarreko laguntzaile bat dutela, 2. asteak ezagutza-base sistema osoa aurkezten du -- azalduz zergatik behar duten fitxategi bat baino gehiago, bilaketa semantikoak nola funtzionatzen duen, eta laguntzailearen portaera nola fintzen den.

| # | Bideoaren Izenburua | Eduki Nagusia | Ekintza-Deia |
|---|------------|-------------|----------------|
| 6 | **Fitxategi Batetik Ezagutza-Base Osora** | Fitxategi bakarreko RAG-en mugak (fitxategi osoa testuinguruan, fitxategi bakarra). Aurkeztu Ezagutza-Baseak: sortu bilduma bat, igo dokumentu anitz. Azaldu zatiketa eta bilaketa bektoriala -- AAk zati garrantzitsuak aurkitzen ditu dena irakurri beharrean. | Sortu ezagutza-base bat. Igo gutxienez 2-3 dokumentu zure ikastarotik. |
| 7 | **Fitxategietatik Haratago: URLak, Arakatzaileak eta YouTube** | Irentsi web orri bat, arakatu ikastaro webgune bat, inportatu YouTube hitzaldi transkripzio bat. Erakutsi iturri askotarikoak nola bihurtzen diren bilatu daitekeen ezagutza. | Gehitu URL bat edo YouTube bideo bat zure EB-ra. |
| 8 | **Zure Ezagutza-Basea Konektatzea (RAG)** | Aldatu zure laguntzailea fitxategi bakarreko RAG-etik EB osora. Konfiguratu Top K. Probatu aldea -- orain zati garrantzitsuak bilatzen ditu fitxategi osoa isurtzen beharrean. Konparatu emaitzak. | Konektatu zure EB-a zure laguntzaileari. Egin 1. Asteko galdera berak. Hobea al da? Argitaratu zure konparazioa foroan. |
| 9 | **Arazketa Modua: AAk Ikusten Duena Ikustea** | Gaitu arazketa modua. Irakurri prompt osoa: sistema-prompta + berreskuratutako testuingurua + erabiltzailearen galdera. Ulertu AAk benetan zer jasotzen duen. Ikuskatu aipamenak. | Gaitu arazketa modua. Egin prompt osoaren pantaila-argazki bat. Argitaratu foroan zure behaketeekin. |
| 10 | **Prompt Ingeniaritza Irakasleentzat** | Sistema-promptak fintzen: mugak ezartzea, tonua, estrategia pedagogikoak (metodo sokratikoa, aldamiatzea, "ez eman erantzuna -- gidatu ikaslea"). Aurretik/ondorengo konparazioa. | Berridatzi zure sistema-prompta. Konparatu laguntzailearen portaera aurretik eta ondoren. Partekatu zure prompt onena foroan. |

### 3. Astea: Argitaratzea, Ebaluazioa eta Haratago

| # | Bideoaren Izenburua | Eduki Nagusia | Ekintza-Deia |
|---|------------|-------------|----------------|
| 11 | **Moodle-n Argitaratzea** | Argitaratze-lana, LTI kredentzialak, Kanpo Tresna gisa Moodle-n gehitzea, ikaslearen ikuspegia | Argitaratu zure laguntzailea. Gehitu proba Moodle ikastaro batera (edo zure benetako ikastarora). |
| 12 | **Ebaluazio Errubrikak Evaluaitor-ekin Sortzea** | Eskuzko errubrika sorrera, AAk sortutako errubrikak, irizpideak/mailak/pisuak, txantiloiak partekatzea | Sortu errubrika bat zure laguntzailea ebaluatzeko (edo ikasleen zeregin baterako). Probatu AAren sorkuntza. |
| 13 | **AA Bidezko Ebaluazioa LAMBA-rekin** | Ebaluazio-lana, nola proposatzen duen AAk (ez erabakitzen), irakaslearen berrikuspena, kalifikazio bikoitzeko eredua | Esperimentatu LAMBA ikasle gisa zure azken entregagarria bidaliz. Gero eztabaidatu foroan: nola erabiliko zenuke hau? |
| 14 | **Partekatzea, Analitika eta Hurrengo Urratsak** | Laguntzaileen partekatzea lankideekin, txat analitika, LAMB ekosistema, zer dator hurrena | Partekatu zure laguntzailea lankide batekin. Berrikusi zure analitikak. Argitaratu zure azken gogoetak foroan. |

### Osagarria / Eduki Erantzunkorra

| # | Bideoaren Izenburua | Noiz |
|---|------------|------|
| B1-Bn | **Foroko galderen bideo-grabazio erantzunak** | Behar denean, ikastaro osoan zehar |
| B? | **Aurreratua: Prompt Txantiloiak** | Partaideek berrerabilgarri diren prompt-ei buruz galdetzen badute |
| B? | **Aurreratua: Erakunde Administrazioa** | Erakunde administratzaileak kohortean badaude |
| B? | **Aurreratua: Eredu Anitz Konparatuta** | Partaideek GPT-4o vs. Mistral vs. lokala konparatu nahi badute |

---

## 6. Foroa Eduki-Motor Gisa

### 6.1 Foro Kultura

Foroa ez da "laguntza" gisa aurkezten, baizik eta **ikaskuntza-komunitate profesional** gisa. Irakasleak tonua ezartzen du 1. Bideoan eta ongi etorri iragarkian:

> *Foro honetan gertatzen da ikastaroa benetan. Argitaratu edozer: asmatzen ez dituzun galderak, existitzea gustatuko litzaizukeen funtzioak, frustratu zintuzten gauzak, poztu zintuzten gauzak, LAMB zure irakaskuntzan nola erabiliko zenukeen ideiak. Ez dago galdera tokirik -- eta zure galderek literalki hobetuko dute ikastaro hau, onenetik eduki berriak sortuko ditugulako.*

### 6.2 Bultzatutako Argitalpen Motak

| Mota | Deskribapena | Irakaslearen Erantzuna |
|------|-------------|-------------------|
| **Galderak** | "Nola egin dezaket...?", "Zergatik...?" | Testuzko erantzuna edo bideo-grabazioa bisualak behar baditu |
| **Funtzio eskaerak** | "Oso ona litzateke LAMB-ek... egin ahal balu" | Onartu, bideragarritasuna eztabaidatu, GitHub-era bideratu liteke |
| **Argibideak** | "Ez nuen ulertu ...ri buruzko atala" | Bideo-grabazio laburra nahasmena argituz |
| **Lorpenak** | "Nire laguntzailea funtzionatzen jarri dut eta..." | Ospatu, jarraipena galdetu, taldearekin partekatu |
| **Frustrazioak** | "X probatu nuen eta ez zuen funtzionatu..." | Arazoa konpondu, agian bideo-grabazio bat sortu, dokumentazioa hobetu |
| **Ideiak** | "Zer gertatuko litzateke LAMB ... erabiliko bagenu?" | Eztabaidatu, beste partaide batzuen ideekin lotu |

### 6.3 Bideo-Grabaziotik EB-rako Kanalizazioa

Irakasleak bideo-grabazio erantzun bat sortzen duenean:

1. Bideo-grabazio laburra grabatu (2-5 min) foroko galdera bati erantzunez
2. Bideo-ostalaritzara igo (YouTube zerrendatu gabea edo erakunde plataforma)
3. Transkripzioa sortu/idatzi
4. Bideo-grabazioaren esteka foroan erantzun gisa argitaratu
5. **Transkripzioa ikastaroko laguntzailearen ezagutza-basean irentsi**
6. Ikastaroko laguntzaileak orain galdera horri erantzun diezaioke eta bideo-grabaziora zuzendu

Kanalizazio hau dokumentatuta eta ikusgai dago partaideentzat -- denbora errealeko EB mantentze-lana erakusten du.

---

## 7. AMA Saioak (Sinkronoak)

### 7.1 Formatua

2-3 zuzeneko bideo-konferentzia saio (60-90 minutu bakoitza), une garrantzitsuetan programatuak:

| Saioa | Denbora | Ardatza |
|---------|--------|-------|
| **AMA 1** | 1. Astearen amaieran | Lehen inpresioak, kontzeptuak argitzea, lehen laguntzaileetako arazoak konpontzea |
| **AMA 2** | 2. Astearen amaieran | Ezagutza-baseak, RAG, prompt ingeniaritza eztabaida |
| **AMA 3** | 3. Astearen amaieran | Argitaratzea, ebaluazioa, etorkizuneko planak, ikastaroaren itxiera |

### 7.2 Egitura

AMA saio bakoitzak egitura malgu bat jarraitzen du:

1. **Beroketa (10 min)** -- Irakasleak 2-3 foroko galdera hautaturi erantzuten die (prestatuak, partaideak hasieran lotsatiak badira ere)
2. **Galdera-Erantzun Irekia (40-60 min)** -- Partaideek edozer galdetzen dute. Pantaila partekatzea gomendatua zuzeneko arazoak konpontzeko.
3. **Erakutsi eta Kontatu (10-20 min)** -- Boluntarioek beren laguntzaileak erakusten dituzte. Taldeko feedbacka.

### 7.3 Prestatutako Galderak

Irakasleak 2-3 foroko hari interesgarri hautatzen ditu saio bakoitzaren aurretik, elkarrizketa-abiatzaile gisa. Honek bermatzen du saioak bulkada duela partaideak hasieran isilak badira ere. Ikastaroa aurrera egin ahala eta konfiantza sendotu ahala, prestatzea gero eta gutxiago beharrezkoa da.

### 7.4 Grabaketa

AMA saioak grabatzen dira eta ikastaroan argitaratzen. Transkripzioak ikastaroko laguntzailearen EB-an irensten dira.

---

## 8. Ebaluazio Estrategia

### 8.1 Filosofia

Ikastaro honetako ebaluazioak bi helburu ditu:
1. Ziurtatu partaideek oinarrizko ikaskuntza-helburuak lortu dituztela
2. **LAMBA ekintzan erakutsi** -- partaideek AA bidezko ebaluazioa ikaslearen ikuspegitik esperimentatzen dute

### 8.2 Azken Entregagarria

Partaide bakoitzak bere irakaskuntza-testuingururako **argitaratutako LAMB laguntzaile** bat aurkezten du. Bidalketa honako hauek barne hartzen ditu:

- Laguntzailearen izena eta bere helburuaren deskribapen laburra
- Erabilitako sistema-prompta
- Ezagutza-basearen edukien deskribapena (zer irentsi zen eta zergatik)
- Argitaratuta dagoen Moodle ikastaroa (edo argitaratzeko plan bat)
- Gogoeta labur bat (300-500 hitz): Zer funtzionatu zuen? Zer aldatuko zenuke? Nola izan daitezke zure ikasleak onuradunak?

### 8.3 Ebaluazio Errubrika

Entregagarria Evaluaitor-en sortutako errubrika baten bidez ebaluatzen da eta LAMBA-ren bidez prozesatzen:

| Irizpidea | Pisua | Zer Bilatzen Dugun |
|-----------|--------|------------------|
| **Laguntzailearen Diseinua** | %25 | Helburu argia, ondo idatzitako sistema-prompta, eredu-hautaketa egokia |
| **Ezagutza-Basearen Kalitatea** | %25 | Eduki garrantzitsua irentsita, iturri egokiak, irismen arrazoizkoa |
| **Probaketa eta Iterazioa** | %20 | Probaketa ebidentzia, prompt fintzea, arazketa moduaren erabilera |
| **Argitarapena eta Integrazioa** | %15 | Laguntzailea argitaratua eta LTI bidez Moodle ikastaro batean eskuragarria |
| **Gogoeta** | %15 | Esperientziaren analisi gogoetatsu bat, erabilpenerako plan errealistak |

### 8.4 LAMBA Esperientzia

Ebaluazio-lana:

1. Partaideak bere entregagarria Moodle-tik bidaltzen du (LAMBA LTI jarduera)
2. AAk bidalketa errubrikaren arabera ebaluatzen du eta puntuazioa proposatzen du idatzizko feedbackarekin
3. **Irakasleak AA proposamen guztiak berrikusten ditu**, feedbacka behar den tokian editatzen du, puntuazioak doitzen ditu AAk gaizki ebaluatu badu, eta azken kalifikazioa berresten du
4. Partaideak irakaslearen berretsitako kalifikazioa eta feedbacka jasotzen ditu Moodle-n

Hau gardena egiten zaie partaideei. Honako hau esaten zaie:

> *AAk zure bidalketa irakurri du eta ebaluazio bat proposatu du. Zure irakasleak proposamen hori berrikusi du, behar zen tokian editatu du, eta azken kalifikazioa berretsi du. Hau da hain zuzen LAMBA nola funtzionatzen duen -- AAk laguntzen du, irakasleak erabakitzen du. Ikaslearen aldetik esperimentatu berri duzu.*

### 8.5 Foroko Parte-Hartzea (Kalifikatu Gabea baina Baloratua)

Foroko parte-hartzea bultzatzen da baina ez da formalki kalifikatzen. Irakasleak ekarpenen balioa nabarmentzen du iragarkietan eta AMA saioetan. Promptak partekatzen dituzten, kideei laguntzen dieten edo galdera pentsatuak argitaratzen dituzten partaideak publikoki aitortzen dira.

---

## 9. Edukien Ekoizpen Gidalerroak

### 9.1 Bideo Ekoizpena

| Alderdia | Gidalerroa |
|--------|-----------|
| **Iraupena** | 5-10 minutu gehienez. Luzeagoa bada, zatitu bitan. |
| **Formatua** | Pantaila-grabazioa ahots-iruzkinekin. Aurpegi-kamera aukerazkoa baina gomendatua sarrera/irteerarako. |
| **Egitura** | Kakoa (zer ikasiko duzun) > Erakusketa (erakutsi, ez kontatu) > Ekintza-deia (zer egin orain) |
| **Tonua** | Elkarrizketakoa, adoretsua, parekideen artekoa. Ez hitzaldia eman -- lankide bati zerbait nola egiten den erakutsi. |
| **Azpitituluak** | Beti. Automatikoki sortuak ondo daude, zuzenduak ahal bada. |
| **Transkripzioa** | Beti ekoizten da. Helburu bikoitza du: irisgarritasuna + ikastaroko laguntzailearen EB. |

### 9.2 Bideo-Grabazio Erantzunak

| Alderdia | Gidalerroa |
|--------|-----------|
| **Iraupena** | 2-5 minutu. Galdera bat bideo-grabazio bakoitzeko. |
| **Testuingurua** | Foroko galdera ozenean irakurriz hasi. |
| **Formatua** | Pantaila-grabaketa soluzioa erakutsiz. Ez da editatzerik behar. |
| **Argitaratzea** | Foroko hariari bideo estekarekin erantzun. |
| **EB Irenstea** | Transkripzioa ikastaroko laguntzailearen EB-ra gehitua 24 orduren barruan. |

### 9.3 Idatzizko Edukia

- Interesdunen laburpen-dokumentua erreferentzia nagusi gisa balio du
- Bideo modulu bakoitzak idatzizko laburpen labur bat du (ez transkripzio oso bat -- 2-3 paragrafoko laburpena)
- FAQ sarrerak foroko elkarrekintzatik biltzen dira

---

## 10. Kronograma eta Erritmoa

### Asteko Erritmoa

```
Astelehena:    Bideo berria argitaratua + iragarpena
Asteartea:     Foroko jarduera, irakasleak argitalpenei erantzuten die
Asteazkena:    Bigarren bideoa argitaratua (2 eguneko kadentzia bada)
Osteguna:      Foroko jarduera, bideo-grabazio erantzunak behar izanez gero
Ostirala:      Hirugarren bideoa edo atseden-eguna + asteko laburpen iragarpena
Asteburua:     Partaideek eguneratzen dute, foroa aktibo jarraitzen du
```

### Ikastaroko Egutegia (3 Asteko Eredua)

| Eguna | Edukia | Jarduera |
|-----|---------|----------|
| **E1** | 1. Bideoa: Ezagutu Zure AA Tutorea | Demo laguntzaileekin txateatu, foro sarrera |
| **E2** | 2. Bideoa: Zergatik LAMB? | Manifestua irakurri, AA kezkak eztabaidatu |
| **E3** | 3. Bideoa: Lehen Saioa eta Lehen Laguntzailea | LTI bidez saioa hasi, laguntzailea sortu |
| **E4** | 4. Bideoa: Magia Trikimailua (fitxategi bakarreko RAG) | Fitxategi bat igo, berehalako "uau" |
| **E5** | 5. Bideoa: Ikastaroko Laguntzailea eta Dogfooding | Ikastaroko laguntzailea probatu |
| **E5-6** | **AMA 1. Saioa** | Lehen inpresioak, uau momentuak, galdera-erantzunak |
| **E7** | Atsedena / eguneratzea | |
| **E8** | 6. Bideoa: Fitxategi Batetik EB Osora | EB sortu, dokumentu anitz igo |
| **E9** | 7. Bideoa: URLak, Arakatzaileak eta YouTube | Web/bideo edukia irentsi |
| **E10** | 8. Bideoa: Zure EB Konektatzea (RAG) | Fitxategi bakarretik EB osora aldatu |
| **E11** | 9. Bideoa: Arazketa Modua | Promptak eta testuingurua ikuskatu |
| **E12** | 10. Bideoa: Prompt Ingeniaritza | Sistema-promptak fintzen |
| **E12-13** | **AMA 2. Saioa** | RAG konparazioa, prompt partekatzea |
| **E14** | Atsedena / eguneratzea | |
| **E15** | 11. Bideoa: Argitaratzea | Moodle-n argitaratu |
| **E16** | 12. Bideoa: Evaluaitor Errubrikak | Errubrikak sortu |
| **E17** | 13. Bideoa: LAMBA | AA bidezko ebaluazioa esperimentatu |
| **E18** | 14. Bideoa: Partekatzea eta Analitika | Ixteko funtzioak |
| **E19** | Azken entregagarriaren epemuga | LAMBA bidez bidali |
| **E20-21** | **AMA 3. Saioa** | Erakutsi eta kontatu, gogoetak, itxiera |

---

## 11. Arrakasta Adierazleak

### Partaideentzat

| Adierazlea | Helburua |
|--------|--------|
| Gutxienez laguntzaile bat osatu | Partaideen %90+ |
| Laguntzailea Moodle-n argitaratu | Partaideen %70+ |
| Benetako ikastaroko edukiarekin ezagutza-base bat sortu | Partaideen %80+ |
| Foroan gutxienez behin argitaratu | Partaideen %95+ |
| Azken entregagarria bidali | Partaideen %80+ |

### Ikastarorako

| Adierazlea | Helburua |
|--------|--------|
| Partaideen gogobetetasuna (ikastaro osteko inkesta) | 4.0+ / 5.0 |
| Foroko argitalpenak partaideko (batez bestekoa) | 3+ |
| Ekoiztutako bideo-grabazio erantzunak | 5-10 kohorteko |
| Ikastaroko laguntzailearen EB hazkundea | E1-etik E21-era neurgarri |
| Ikastaroa ondoren LAMB erabiltzen jarraitzen duten partaideak | 3 hilabetera jarraitu |

### LAMB-erako (Produktu Feedbacka)

| Adierazlea | Emaitza |
|--------|---------|
| Bildutako funtzio eskaerak | Triatuta eta GitHub issue-etara bideratuta |
| Jakinarazitako erroreak | Erregistratuta eta lehentasunez antolatuta |
| Identifikatutako EE (erabiltzaile-esperientzia) marruskadura-puntuak | Produktuaren hobekuntzarako dokumentatuta |
| Aurkitutako erabilera-kasuak | Dokumentaziora / webgunera gehituta |

---

## 12. Berrerabilgarritasuna eta Eskalatzea

### Kohorte Eredua

Ikastaro hau kohortetan exekutatzeko diseinatuta dago. Kohorte bakoitzak:
- Moodle ikastaro instantzia (edo atal) berri bat jasotzen du
- LAMB prestakuntza-erakunde bera partekatzen du
- Aurreko kohorteetatik hazten den eduki-atzerako lana jasotzen du
- Gero eta hobea den ikastaroko laguntzailearen EB-aren onura jasotzen du

### Eduki Atzerapenaren Hazkundea

```
1. Kohortea:  14 oinarrizko bideo + N bideo-grabazio erantzun
2. Kohortea:  14 oinarrizko bideo + N + M bideo-grabazio erantzun (batzuk 1. Kohortetik berrerabiliak)
3. Kohortea:  14 oinarrizko bideo (agian finduak) + bideo-grabazio erantzunen liburutegi hazten dena
   ...
```

Ikastaroko laguntzailea gaiagoa bihurtzen da kohorte bakoitzarekin bere EB hazten den heinean. Hau bera LAMB-en balio-proposamenaren erakusketa da.

### Lokalizazioa

- Oinarrizko bideoak hizkuntza anitzetan ekoitzi daitezke (gaztelania, ingelesa, katalana, euskara -- LAMB-en interfaze-hizkuntzekin bat etorriz)
- Ikastaroko laguntzailea hizkuntzaka konfigura daiteke
- Idatzizko materialak dagoeneko hizkuntza anitzetan daude proiektuaren webgunean

---

## 13. Arriskuak eta Arintzeak

| Arriskua | Eragina | Arintzea |
|------|--------|------------|
| Foroko parte-hartze txikia | Ikastaroa hutsik sentitzen da, bideo-grabazio gutxiago | Foroa irakaslearen galdera prestaturekin hazi. Partaideei zuzenean gonbidatu ekintza-deietan prompt zehatzei erantzutera. |
| Partaideek bideoetan atzean geratzen dira | Ikusi gabeko edukiaren pilaketa, deskonexioa | Bideoak laburrak mantendu. Asteko laburpen iragarpenak. AMA saioak eguneratze-puntu gisa. |
| LAMB instantzia arazoak (geldialdiak, erroreak) | Frustrazioa, blokeatutako partaideak | Babeskopia instantzia ezagun bat eduki. Arazoei buruzko komunikazio gardena. Erroreak ikaskuntza-momentu bihurtu ("hau kode irekia da -- erregistra dezagun"). |
| Partaideek ez dute Moodle admin sarbiderik argitaratzeko | Ezin dute argitaratze-urratsa osatu | Partekatutako proba Moodle ikastaroa eskaini. Erakundeko Moodle administratzaileekin elkarlanean aritu. Argitaratze-urratsa aukerazko gisa eskaini sarbiderik ez badago. |
| AA bidezko ebaluazioa (LAMBA) pertsonalgabea sentitzen da | Erantzun negatiboa AAk kalifikazioak proposatzen dituenean | Prozesuari buruz erabat gardena izan. AA proposamen gordina vs. irakaslearen azken feedbacka erakutsi. Irakasleak erabakitzen duen eredua azpimarratu. |
| AMA saioetara parte-hartze txikia | Galdutako aukera komunitatea eraikitzeko | Grabatu eta partekatu. Bi ordutegi-aukera eskaini ahal izanez gero. Aukerazko baina baliotsu mantendu (galdera-erantzun esklusiboa, erakutsi eta kontatu). |

---

## 14. Laburpena: Ikastaroa Orri Batean

**Zer:** 3 asteko ikastaro hibrido bat, unibertsitateko irakasleei LAMB-ekin AA ikaskuntza-laguntzaileak eraikitzen irakasten diena.

**Nola:** Eguneroko bideo laburrak zeregin praktikoekin, eztabaida foro aktibo bat eta zuzeneko AMA saioak. Ikastaroa bera LAMB-en gainean dabil (dogfooding).

**Begizta:**
1. Ikusi bideo labur bat (5-10 min)
2. Egin zerbait zehatza LAMB-ekin (ekintza-deia)
3. Partekatu zure esperientzia foroan
4. Jaso erantzunak (testua edo bideo-grabazioa) irakaslearen eskutik
5. Erantzun horiek ikastaroko laguntzailearen ezagutza-basea elikatzen dute
6. Ikastaroko laguntzailea adimentsuago bihurtzen da -- eraikitzen ari zarenaren balioa frogatuz

**Ebaluazioa:** Bidali argitaratutako laguntzaile bat. AAk ebaluazio bat proposatzen du LAMBA bidez. Irakasleak berrikusten eta berresten du. Partaideek ziklo osoa bi aldetik esperimentatzen dute.

**Filosofia:** AAk laguntzen du; irakasleak erabakitzen du. Beti.

---

*Dokumentu honek LAMB prestakuntza-ikastaroko irakaskuntza-estrategia definitzen du. Hurrengo urratsa bideo-gidoi zehatzak eta Moodle ikastaroaren egitura garatzea da.*
