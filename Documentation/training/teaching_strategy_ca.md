# Curs de Formació LAMB -- Estratègia Didàctica

**Versió:** 1.0
**Data:** 15 de febrer de 2026
**Estat:** Esborrany
**Destinataris:** Dissenyadors de cursos, formadors

---

## 1. Identitat del Curs

**Títol:** *Construir Assistents d'Aprenentatge amb IA amb LAMB -- Un Curs Pràctic per a Educadors*

**Format:** Híbrid (curs asíncron a Moodle + sessions sincròniques AMA)

**Durada:** 3-4 setmanes (flexible, contingut publicat progressivament)

**Plataforma:** Moodle amb LAMB integrat via LTI

**Públic objectiu:** Professorat universitari que vol crear assistents d'aprenentatge basats en IA per als seus cursos. No es requereixen coneixements de programació.

---

## 2. Filosofia Pedagògica

### 2.1 Aprendre Fent, No Mirant

Cada peça de contingut té una **crida a l'acció** clara i assolible. Els participants mai es limiten a mirar -- sempre fan alguna cosa concreta amb LAMB immediatament després. L'objectiu és que, en acabar el curs, cada participant tingui almenys un assistent funcional i publicat, fonamentat en els seus propis materials docents.

### 2.2 Menjar del Nostre Propi Plat

El curs mateix està construït sobre LAMB. Els participants experimenten LAMB des del costat de l'estudiant (interactuant amb un assistent del curs, tenint el seu treball avaluat per LAMBA) mentre simultàniament aprenen a ser creadors. Aquesta doble perspectiva és intencionada -- senten el que sentiran els seus estudiants.

### 2.3 Contingut Impulsat per la Comunitat

El fòrum no és un canal de suport -- és un **motor de contingut**. Les preguntes, frustracions i idees dels participants es converteixen en videotutorials, entrades de FAQ i discussions sobre funcionalitats. El curs s'enriqueix amb cada cohort. Als participants se'ls diu explícitament: les vostres preguntes fan que aquest curs sigui millor per a tothom.

### 2.4 Dosificació Progressiva, No Allau d'Informació

El contingut es publica cada 1-2 dies en vídeos curts i enfocats (5-10 minuts com a màxim). Això crea un ritme: mirar, fer, compartir, discutir. Evita la sobrecàrrega i dona temps als formadors per respondre al fòrum abans de la propera publicació.

### 2.5 Alineament amb el Manifest

El curs incorpora els principis del Manifest d'IA Segura en Educació en el seu propi disseny:
- **Supervisió Humana** -- El formador hi és present, respon i condueix la conversa
- **Privadesa** -- Els participants utilitzen una instància de LAMB allotjada institucionalment
- **Integració Didàctica** -- El curs funciona dins de Moodle, el mateix entorn que els participants ja utilitzen
- **Transparència** -- Els participants veuen com funciona l'assistent d'IA per dins (mode de depuració, inspecció de prompts)

---

## 3. Objectius d'Aprenentatge

En acabar el curs, els participants seran capaços de:

### Setmana 1: Experiència i Primer "Uau" (Fonamental)
1. Experimentar els assistents LAMB com a usuari final -- sentir el que sentiran els estudiants
2. Explicar què és LAMB i per què existeix (privadesa, control, principis del manifest)
3. Iniciar sessió a LAMB des de Moodle via LTI Creator i navegar per la Interfície de Creació
4. Crear un primer assistent amb un prompt de sistema i un únic fitxer adjunt (RAG de fitxer únic) -- context instantani sense complexitat de configuració
5. Provar l'assistent i veure com respon preguntes a partir del vostre propi material docent

### Setmana 2: Coneixement Profund i Refinament (Intermedi)
6. Construir una base de coneixement completa a partir de múltiples fonts (fitxers, URL, YouTube)
7. Connectar una base de coneixement a un assistent (configuració RAG, Top K)
8. Entendre la diferència entre el RAG de fitxer únic i les bases de coneixement completes
9. Provar i depurar un assistent utilitzant el mode de depuració
10. Iterar sobre els prompts de sistema per millorar el comportament de l'assistent

### Setmana 3: Publicació, Avaluació i Més Enllà (Avançat)
11. Publicar un assistent com a activitat LTI en un curs Moodle
12. Crear una rúbrica d'avaluació amb Evaluaitor (manualment o generada per IA)
13. Adjuntar una rúbrica a un assistent per a avaluació assistida per IA
14. Entendre el flux d'avaluació de LAMBA (la IA proposa, el professorat decideix)

### Meta-Aprenentatge (Durant Tot el Curs)
13. Experimentar LAMB des de la perspectiva de l'estudiant (interactuant amb l'assistent del curs)
14. Experimentar l'avaluació assistida per IA des de la perspectiva de l'estudiant (LAMBA)
15. Avaluar críticament el paper de la IA en el seu propi context docent

---

## 4. Infraestructura del Curs

### 4.1 Estructura del Curs a Moodle

```
Curs de Formació LAMB (Moodle)
|
+-- Anuncis (canal de missatges del professorat)
|     Canal unidireccional per a actualitzacions del formador, publicació
|     de nous vídeos i respostes a preguntes habituals.
|
+-- Fòrum de Discussió (obert a tothom)
|     El cor del curs. Els participants publiquen preguntes,
|     peticions de funcionalitats, frustracions, idees i èxits.
|     El formador respon amb text o videotutorials curts.
|
+-- Assistents de Demostració (Eina Externa LTI -- Unified LTI)
|     Assistents preconstruïts per a l'experiència d'usuari final de la Setmana 1.
|     Els participants interactuen com a estudiants abans de convertir-se en creadors.
|     Exemples: un tutor d'història, un ajudant de matemàtiques, un coach d'idiomes.
|
+-- Accés a LAMB Creator (Eina Externa LTI -- LTI Creator)
|     Enllaç LTI Creator -- un clic porta els participants
|     directament a la Interfície de Creació de LAMB.
|     No calen credencials separades.
|
+-- Assistent d'IA del Curs (Eina Externa LTI -- Unified LTI)
|     Un assistent LAMB carregat amb totes les transcripcions
|     dels vídeos i la documentació del curs. Els participants
|     poden fer-li preguntes i els redirigeix al vídeo
|     i minut corresponent.
|
+-- Mòduls de Contingut (un per vídeo/tema)
|     +-- Vídeo (incrustat o enllaçat)
|     +-- Resum escrit / transcripció
|     +-- Crida a l'acció (tasca concreta)
|     +-- Opcional: enllaç a documentació rellevant
|
+-- Lliurament Final
|     Enviar un enllaç/descripció del seu assistent publicat.
|     Avaluat via LAMBA amb una rúbrica.
|
+-- Sessions AMA (2-3 videoconferències programades)
      Esdeveniments al calendari amb enllaços de videoconferència.
```

### 4.2 Configuració de LAMB

**LTI Creator:** Els participants són assignats com a usuaris `lti_creator` en una organització de formació dedicada. Accedeixen a LAMB directament des de Moodle sense necessitat d'un inici de sessió separat.

**Assistents de Demostració (Setmana 1):** 2-3 assistents preconstruïts publicats via Unified LTI per a l'experiència d'usuari final durant els primers dies. Han de ser polits, diversos (diferents matèries, diferents tons) i demostrar com es veu i com funciona un assistent ben elaborat. Els participants hi xategen abans de construir el seu -- establint el llistó del que estan treballant per aconseguir.

**Assistent del Curs:** Un assistent LAMB publicat la base de coneixement del qual conté:
- Totes les transcripcions dels vídeos (amb marques de temps i identificadors de vídeo)
- El document resum per a les parts interessades
- Entrades de FAQ generades a partir de les preguntes del fòrum

El prompt de sistema de l'assistent l'instrueix per:
- Respondre preguntes sobre LAMB
- Referenciar vídeos específics i marques de temps quan sigui rellevant (p. ex., "Això es tracta al Vídeo 5 al minut 3:20")
- Redirigir al fòrum per a preguntes que no pot respondre
- Ser transparent sobre el fet de ser un assistent d'IA construït amb el propi LAMB

**Avaluació LAMBA:** El lliurament final (un assistent publicat) s'avalua mitjançant una rúbrica a través de LAMBA. La IA proposa una avaluació; el formador la revisa i finalitza la nota. Els participants experimenten LAMBA des del costat de l'aprenent.

### 4.3 El Bucle de Dogfooding

```
Els participants fan preguntes al fòrum
        |
        v
Les millors preguntes es converteixen en videotutorials de resposta
        |
        v
Les transcripcions dels videotutorials s'ingereixen a la base de coneixement del curs
        |
        v
L'assistent d'IA del curs ara pot respondre aquelles preguntes
        |
        v
Els participants experimenten un assistent millor
        |
        v
Entenen per què les bases de coneixement importa per als SEUS assistents
```

Aquest bucle es fa explícit als participants. Veuen com l'assistent del curs millora en temps real a mesura que s'afegeix nou contingut, demostrant el valor de mantenir i fer créixer una base de coneixement.

---

## 5. Pla de Contingut: La Sèrie de Vídeos

Cada vídeo dura **5-10 minuts**, és enfocat i acaba amb una crida a l'acció concreta.

### Setmana 1: Primer Experimentar, Després Construir

La primera setmana està dissenyada per ser **agradable i immediatament gratificant**. Els participants comencen com a usuaris finals -- experimentant els assistents LAMB de la mateixa manera que ho faran els seus estudiants -- abans de passar al costat de creador. Quan creen, utilitzen el **RAG de fitxer únic**, que els permet adjuntar un document a un assistent sense cap complexitat de configuració. Sense creació de base de coneixement, sense configuració de fragmentació, sense esperes. Pugeu un fitxer, seleccioneu-lo, i l'assistent coneix instantàniament el contingut del vostre curs.

| # | Títol del Vídeo | Contingut Clau | Crida a l'Acció |
|---|----------------|----------------|-----------------|
| 1 | **Coneix el Teu Tutor d'IA** | Comença com a estudiant: interactua amb 2-3 assistents de demostració preconstruïts (un tutor d'història, un ajudant de matemàtiques, un coach d'idiomes). Viu l'experiència. Observa com cadascun té diferent personalitat, abast i coneixement. | Xateja amb cada assistent de demostració. Publica al fòrum: quin t'ha impressionat més i per què? Què voldries per al TEU curs? |
| 2 | **Per Què LAMB? Control, Privadesa i el Manifest** | Ara que ho has experimentat -- per què existeix? Preocupacions de privadesa amb ChatGPT, principis del manifest, control institucional, l'argument a favor d'una IA educativa específica vs. eines d'ús general. | Llegeix el manifest (o fes-ne una ullada). Publica al fòrum: quines preocupacions tens sobre la IA als teus cursos? |
| 3 | **El Teu Primer Inici de Sessió i el Teu Primer Assistent** | Fes clic a l'enllaç LTI Creator a Moodle. Aterra a la Interfície de Creació. Crea un assistent: nom, descripció, tria un model, escriu un prompt de sistema bàsic. Mantén-ho senzill. | Inicia sessió a LAMB des de Moodle. Crea un assistent per al teu curs amb un prompt de sistema senzill (p. ex., "Ets un tutor de [la teva assignatura]. Sigues útil i encoratjador."). |
| 4 | **El Truc de Màgia: Adjunta un Fitxer i Observa** | Presenta el RAG de fitxer únic: selecciona "single_file_rag" com a processador RAG, puja un fitxer (el teu temari, un resum d'un tema, un conjunt de conceptes clau -- només un fitxer .txt o .md), selecciona'l, desa. Ara prova: pregunta a l'assistent sobre el contingut del teu curs. Ho sap. | Puja un document del teu curs i adjunta'l al teu assistent. Fes-li 5 preguntes que requereixin coneixement d'aquell fitxer. Publica al fòrum: quin ha estat el moment "uau"? |
| 5 | **L'Assistent del Curs i Menjar del Nostre Propi Plat** | Demostra l'assistent LAMB del propi curs. Mostra com referencia vídeos específics i marques de temps. Explica el concepte de dogfooding: aquest curs funciona sobre LAMB. Tot el que estàs aprenent a construir, també ho estàs experimentant com a aprenent. | Prova l'assistent del curs. Pregunta-li alguna cosa sobre el que has après aquesta setmana. Compara les seves respostes amb les dels assistents de demostració del Vídeo 1 -- què és diferent en un assistent amb contingut real darrere? |

### Setmana 2: Coneixement Profund i Refinament

Ara que els participants tenen un assistent funcional amb un sol fitxer, la Setmana 2 introdueix el sistema complet de bases de coneixement -- explicant per què podrien necessitar més d'un fitxer, com funciona la cerca semàntica i com afinar el comportament del seu assistent.

| # | Títol del Vídeo | Contingut Clau | Crida a l'Acció |
|---|----------------|----------------|-----------------|
| 6 | **D'un Sol Fitxer a una Base de Coneixement Completa** | La limitació del RAG de fitxer únic (tot el fitxer en context, només un fitxer). Presenta les Bases de Coneixement: crea una col·lecció, puja múltiples documents. Explica la fragmentació i la cerca vectorial -- la IA troba les parts rellevants en lloc de llegir-ho tot. | Crea una base de coneixement. Puja almenys 2-3 documents del teu curs. |
| 7 | **Més Enllà dels Fitxers: URL, Rastrejadors i YouTube** | Ingereix una pàgina web, rastreja un lloc web del curs, importa la transcripció d'una classe de YouTube. Mostra com fonts diverses es converteixen en coneixement cercable. | Afegeix una URL o un vídeo de YouTube a la teva base de coneixement. |
| 8 | **Connectar la Teva Base de Coneixement (RAG)** | Canvia el teu assistent del RAG de fitxer únic a una base de coneixement completa. Configura el Top K. Prova la diferència -- ara cerca fragments rellevants en lloc de bolcar tot el fitxer. Compara els resultats. | Connecta la teva base de coneixement al teu assistent. Fes les mateixes preguntes de la Setmana 1. Ha millorat? Publica la teva comparació al fòrum. |
| 9 | **Mode de Depuració: Veure el que Veu la IA** | Activa el mode de depuració. Llegeix el prompt complet: prompt de sistema + context recuperat + pregunta de l'usuari. Entén què rep realment la IA. Inspecciona les citacions. | Activa el mode de depuració. Fes una captura de pantalla del prompt complet. Publica-la al fòrum amb les teves observacions. |
| 10 | **Enginyeria de Prompts per a Educadors** | Refinar prompts de sistema: establir límits, to, estratègies pedagògiques (mètode socràtic, bastimentada, "no donis la resposta -- guia l'estudiant"). Comparació abans/després. | Reescriu el teu prompt de sistema. Compara el comportament de l'assistent abans i després. Comparteix el teu millor prompt al fòrum. |

### Setmana 3: Publicació, Avaluació i Més Enllà

| # | Títol del Vídeo | Contingut Clau | Crida a l'Acció |
|---|----------------|----------------|-----------------|
| 11 | **Publicar a Moodle** | El flux de publicació, credencials LTI, afegir com a Eina Externa a Moodle, vista de l'estudiant | Publica el teu assistent. Afegeix-lo a un curs Moodle de prova (o al teu curs real). |
| 12 | **Crear Rúbriques d'Avaluació amb Evaluaitor** | Creació manual de rúbriques, rúbriques generades per IA, criteris/nivells/pesos, compartir plantilles | Crea una rúbrica per avaluar el teu assistent (o un treball d'un estudiant). Prova la generació per IA. |
| 13 | **Avaluació Assistida per IA amb LAMBA** | El flux d'avaluació, com la IA proposa (no decideix), revisió del professorat, model de doble qualificació | Experimenta LAMBA com a estudiant enviant el teu lliurament final. Després discuteix al fòrum: com ho faries servir? |
| 14 | **Compartir, Analítiques i Propers Passos** | Compartir assistents amb col·legues, analítiques de xat, l'ecosistema LAMB, què ve a continuació | Comparteix el teu assistent amb un col·lega. Revisa les teves analítiques. Publica les teves reflexions finals al fòrum. |

### Contingut Addicional / Responsiu

| # | Títol del Vídeo | Quan |
|---|----------------|------|
| B1-Bn | **Videotutorials de resposta a preguntes del fòrum** | Segons les necessitats, durant tot el curs |
| B? | **Avançat: Plantilles de Prompts** | Si els participants pregunten sobre prompts reutilitzables |
| B? | **Avançat: Administració d'Organitzacions** | Si hi ha administradors institucionals a la cohort |
| B? | **Avançat: Comparació de Múltiples Models** | Si els participants volen comparar GPT-4o vs. Mistral vs. local |

---

## 6. El Fòrum com a Motor de Contingut

### 6.1 Cultura del Fòrum

El fòrum es posiciona no com a "suport" sinó com una **comunitat professional d'aprenentatge**. El formador estableix el to al Vídeo 1 i a l'anunci de benvinguda:

> *Aquest fòrum és on el curs realment passa. Publiqueu el que sigui: preguntes que no podeu resoldre, funcionalitats que voldríeu que existissin, coses que us han frustrat, coses que us han encantat, idees sobre com faríeu servir LAMB a la vostra docència. No hi ha preguntes dolentes -- i les vostres preguntes literalment faran que aquest curs sigui millor, perquè convertirem les millors en nou contingut.*

### 6.2 Tipus de Publicacions Fomentades

| Tipus | Descripció | Resposta del Formador |
|-------|------------|----------------------|
| **Preguntes** | "Com puc...?", "Per què...?" | Resposta en text o videotutorial si cal veure-ho |
| **Peticions de funcionalitats** | "Estaria bé que LAMB pogués..." | Reconèixer, discutir viabilitat, potencialment derivar a GitHub |
| **Aclariments** | "No he entès la part sobre..." | Videotutorial curt adreçant la confusió |
| **Èxits** | "He aconseguit que el meu assistent funcioni i..." | Celebrar, fer preguntes de seguiment, compartir amb el grup |
| **Frustracions** | "He provat X i no ha funcionat perquè..." | Resoldre el problema, possiblement crear un videotutorial, millorar la documentació |
| **Idees** | "I si féssim servir LAMB per a...?" | Discutir, connectar amb idees d'altres participants |

### 6.3 Pipeline de Videotutorial a Base de Coneixement

Quan el formador crea un videotutorial de resposta:

1. Gravar un videotutorial curt (2-5 min) adreçant la pregunta del fòrum
2. Pujar-lo a una plataforma de vídeo (YouTube no llistat o plataforma institucional)
3. Generar/escriure una transcripció
4. Publicar l'enllaç del videotutorial com a resposta al fil del fòrum
5. **Ingerir la transcripció a la base de coneixement de l'assistent del curs**
6. L'assistent del curs ara pot respondre aquella pregunta i apuntar al videotutorial

Aquest pipeline es documenta i és visible per als participants -- demostra el manteniment de la base de coneixement en temps real.

---

## 7. Sessions AMA (Sincròniques)

### 7.1 Format

2-3 sessions de videoconferència en directe (60-90 minuts cadascuna), programades en moments clau:

| Sessió | Moment | Focus |
|--------|--------|-------|
| **AMA 1** | Final de la Setmana 1 | Primeres impressions, aclariment de conceptes, resolució de problemes amb els primers assistents |
| **AMA 2** | Final de la Setmana 2 | Bases de coneixement, RAG, discussió sobre enginyeria de prompts |
| **AMA 3** | Final de la Setmana 3 | Publicació, avaluació, plans de futur, cloenda del curs |

### 7.2 Estructura

Cada sessió AMA segueix una estructura flexible:

1. **Escalfament (10 min)** -- El formador adreça 2-3 preguntes curades del fòrum (preparades per si els participants són tímids al principi)
2. **Preguntes obertes (40-60 min)** -- Els participants pregunten el que vulguin. Es fomenta compartir pantalla per a resolució de problemes en directe.
3. **Mostra i Explica (10-20 min)** -- Voluntaris mostren els seus assistents. Retroalimentació grupal.

### 7.3 Preguntes Preparades

El formador selecciona 2-3 fils de fòrum interessants abans de cada sessió com a punts de partida per a la conversa. Això assegura que la sessió tingui impuls fins i tot si els participants estan inicialment en silenci. A mesura que el curs avança i es construeix la confiança, la preparació es fa menys necessària.

### 7.4 Enregistrament

Les sessions AMA s'enregistren i es publiquen al curs. Les transcripcions s'ingereixen a la base de coneixement de l'assistent del curs.

---

## 8. Estratègia d'Avaluació

### 8.1 Filosofia

L'avaluació en aquest curs compleix dos propòsits:
1. Assegurar que els participants han assolit els objectius d'aprenentatge fonamentals
2. **Demostrar LAMBA en acció** -- els participants experimenten l'avaluació assistida per IA des de la perspectiva de l'aprenent

### 8.2 Lliurament Final

Cada participant presenta un **assistent LAMB publicat** per al seu propi context docent. El lliurament inclou:

- El nom de l'assistent i una breu descripció del seu propòsit
- El prompt de sistema utilitzat
- Una descripció del contingut de la base de coneixement (què s'ha ingerit i per què)
- El curs Moodle on està publicat (o un pla de publicació)
- Una reflexió breu (300-500 paraules): Què ha funcionat? Què canviaries? Com podrien beneficiar-se els teus estudiants?

### 8.3 Rúbrica d'Avaluació

El lliurament s'avalua mitjançant una rúbrica creada amb Evaluaitor i processada a través de LAMBA:

| Criteri | Pes | Què Busquem |
|---------|-----|-------------|
| **Disseny de l'Assistent** | 25% | Propòsit clar, prompt de sistema ben escrit, elecció de model adequada |
| **Qualitat de la Base de Coneixement** | 25% | Contingut rellevant ingerit, fonts apropiades, abast raonable |
| **Proves i Iteració** | 20% | Evidència de proves, refinament de prompts, ús del mode de depuració |
| **Publicació i Integració** | 15% | Assistent publicat i accessible via LTI en un curs Moodle |
| **Reflexió** | 15% | Anàlisi reflexiva de l'experiència, plans realistes d'ús |

### 8.4 L'Experiència LAMBA

El flux d'avaluació:

1. El participant envia el seu lliurament a través de Moodle (activitat LTI de LAMBA)
2. La IA avalua el lliurament contra la rúbrica i proposa una puntuació amb comentaris escrits
3. **El formador revisa cada proposta de la IA**, edita els comentaris quan cal, ajusta les puntuacions si la IA ha errat en la valoració, i confirma la nota final
4. El participant rep la nota confirmada pel formador i els comentaris a Moodle

Això es fa transparent als participants. Se'ls diu:

> *La IA ha llegit el teu lliurament i ha proposat una avaluació. El teu formador ha revisat després aquella proposta, l'ha editada quan ha calgut, i ha confirmat la nota final. Això és exactament com funciona LAMBA -- la IA assisteix, el professorat decideix. Acabes d'experimentar-ho des del costat de l'estudiant.*

### 8.5 Participació al Fòrum (No Qualificada però Valorada)

La participació al fòrum s'encoratja però no es qualifica formalment. El formador destaca les contribucions valuoses als anuncis i a les sessions AMA. Els participants que comparteixen prompts, ajuden companys o publiquen preguntes reflexives reben reconeixement públic.

---

## 9. Directrius de Producció de Contingut

### 9.1 Producció de Vídeos

| Aspecte | Directriu |
|---------|-----------|
| **Durada** | 5-10 minuts com a màxim. Si és més llarg, dividir en dos. |
| **Format** | Screencast amb veu en off. Càmera facial opcional però recomanada per a intro/conclusió. |
| **Estructura** | Ganxo (què aprendràs) > Demostració (mostra, no expliquis) > Crida a l'acció (què fer ara) |
| **To** | Conversacional, encoratjador, entre iguals. No és una classe magistral -- és mostrar a un col·lega com fer alguna cosa. |
| **Subtítols** | Sempre. Generats automàticament és acceptable, corregits si és possible. |
| **Transcripció** | Sempre produïda. Serveix un doble propòsit: accessibilitat + base de coneixement de l'assistent del curs. |

### 9.2 Videotutorials de Resposta

| Aspecte | Directriu |
|---------|-----------|
| **Durada** | 2-5 minuts. Adreçar una pregunta per videotutorial. |
| **Context** | Començar llegint la pregunta del fòrum en veu alta. |
| **Format** | Gravació de pantalla mostrant la solució. No cal edició. |
| **Publicació** | Respondre al fil del fòrum amb l'enllaç del vídeo. |
| **Ingestió a la Base de Coneixement** | Transcripció afegida a la base de coneixement de l'assistent del curs en 24 hores. |

### 9.3 Contingut Escrit

- El document resum per a les parts interessades serveix com a referència principal
- Cada mòdul de vídeo inclou un breu resum escrit (no una transcripció completa -- un resum de 2-3 paràgrafs)
- Les entrades de FAQ es compilen a partir de les interaccions al fòrum

---

## 10. Calendari i Ritme

### Ritme Setmanal

```
Dilluns:     Publicació de nou vídeo + anunci
Dimarts:     Activitat al fòrum, el formador respon publicacions
Dimecres:    Publicació del segon vídeo (si es segueix cadència de 2 dies)
Dijous:      Activitat al fòrum, videotutorials de resposta si cal
Divendres:   Tercer vídeo o dia de descans + anunci resum setmanal
Cap de setmana: Els participants es posen al dia, el fòrum segueix actiu
```

### Calendari del Curs (Model de 3 Setmanes)

| Dia | Contingut | Activitat |
|-----|-----------|----------|
| **D1** | Vídeo 1: Coneix el Teu Tutor d'IA | Xatejar amb assistents de demostració, presentació al fòrum |
| **D2** | Vídeo 2: Per Què LAMB? | Llegir el manifest, discutir preocupacions sobre IA |
| **D3** | Vídeo 3: Primer Inici de Sessió i Primer Assistent | Iniciar sessió via LTI, crear assistent |
| **D4** | Vídeo 4: El Truc de Màgia (RAG de fitxer únic) | Pujar un fitxer, "uau" instantani |
| **D5** | Vídeo 5: Assistent del Curs i Dogfooding | Provar l'assistent del curs |
| **D5-6** | **Sessió AMA 1** | Primeres impressions, moments "uau", preguntes i respostes |
| **D7** | Descans / posar-se al dia | |
| **D8** | Vídeo 6: D'un Sol Fitxer a una Base de Coneixement Completa | Crear base de coneixement, pujar múltiples documents |
| **D9** | Vídeo 7: URL, Rastrejadors i YouTube | Ingerir contingut web/vídeo |
| **D10** | Vídeo 8: Connectar la Teva Base de Coneixement (RAG) | Canviar de fitxer únic a base de coneixement completa |
| **D11** | Vídeo 9: Mode de Depuració | Inspeccionar prompts i context |
| **D12** | Vídeo 10: Enginyeria de Prompts | Refinar prompts de sistema |
| **D12-13** | **Sessió AMA 2** | Comparació RAG, compartir prompts |
| **D14** | Descans / posar-se al dia | |
| **D15** | Vídeo 11: Publicació | Publicar a Moodle |
| **D16** | Vídeo 12: Rúbriques amb Evaluaitor | Crear rúbriques |
| **D17** | Vídeo 13: LAMBA | Experimentar l'avaluació assistida per IA |
| **D18** | Vídeo 14: Compartir i Analítiques | Funcionalitats de cloenda |
| **D19** | Data límit del lliurament final | Enviar via LAMBA |
| **D20-21** | **Sessió AMA 3** | Mostra i explica, reflexions, cloenda |

---

## 11. Mètriques d'Èxit

### Per als Participants

| Mètrica | Objectiu |
|---------|----------|
| Ha completat almenys un assistent | 90%+ dels participants |
| Ha publicat l'assistent a Moodle | 70%+ dels participants |
| Ha creat una base de coneixement amb contingut real del curs | 80%+ dels participants |
| Ha publicat almenys una vegada al fòrum | 95%+ dels participants |
| Ha enviat el lliurament final | 80%+ dels participants |

### Per al Curs

| Mètrica | Objectiu |
|---------|----------|
| Satisfacció dels participants (enquesta post-curs) | 4.0+ / 5.0 |
| Publicacions al fòrum per participant (mitjana) | 3+ |
| Videotutorials de resposta produïts | 5-10 per cohort |
| Creixement de la base de coneixement de l'assistent del curs | Increment mesurable del D1 al D21 |
| Participants que continuen utilitzant LAMB després del curs | Seguiment als 3 mesos |

### Per a LAMB (Retroalimentació de Producte)

| Mètrica | Resultat |
|---------|----------|
| Peticions de funcionalitats recollides | Triades i derivades a issues de GitHub |
| Errors reportats | Registrats i prioritzats |
| Punts de fricció d'experiència d'usuari identificats | Documentats per a millora del producte |
| Casos d'ús descoberts | Afegits a la documentació / lloc web |

---

## 12. Reutilització i Escalabilitat

### Model de Cohorts

Aquest curs està dissenyat per funcionar en cohorts. Cada cohort:
- Rep una instància de curs Moodle nova (o secció)
- Comparteix la mateixa organització de formació LAMB
- Hereta l'acumulat creixent de contingut de cohorts anteriors
- Es beneficia d'una base de coneixement de l'assistent del curs en millora contínua

### Creixement de l'Acumulat de Contingut

```
Cohort 1:  14 vídeos principals + N videotutorials de resposta
Cohort 2:  14 vídeos principals + N + M videotutorials de resposta (alguns de la Cohort 1 reutilitzats)
Cohort 3:  14 vídeos principals (possiblement refinats) + biblioteca creixent de videotutorials de resposta
   ...
```

L'assistent del curs es torna més capaç amb cada cohort a mesura que creix la seva base de coneixement. Això és en si mateix una demostració de la proposta de valor de LAMB.

### Localització

- Els vídeos principals es poden produir en múltiples idiomes (castellà, anglès, català, basc -- coincidint amb els idiomes de la interfície de LAMB)
- L'assistent del curs es pot configurar per idioma
- Els materials escrits ja existeixen en múltiples idiomes al lloc web del projecte

---

## 13. Riscos i Mitigacions

| Risc | Impacte | Mitigació |
|------|---------|-----------|
| Baixa participació al fòrum | El curs es percep buit, menys videotutorials | Sembrar el fòrum amb preguntes del formador. Convidar directament els participants a respondre a indicacions específiques a les crides a l'acció. |
| Els participants es queden enrere amb els vídeos | Acumulació de contingut no vist, desvinculació | Mantenir els vídeos curts. Anuncis resum setmanals. Sessions AMA com a punts de recuperació. |
| Problemes amb la instància LAMB (caigudes, errors) | Frustració, participants bloquejats | Tenir una instància de reserva funcional. Comunicació transparent sobre els problemes. Convertir els errors en moments d'aprenentatge ("això és codi obert -- reportem-ho"). |
| Els participants no tenen accés d'administrador a Moodle per publicar | No poden completar el pas de publicació | Proporcionar un curs Moodle de prova compartit. Col·laborar amb els administradors institucionals de Moodle. Oferir el pas de publicació com a opcional si l'accés no és possible. |
| L'avaluació assistida per IA (LAMBA) es percep impersonal | Reacció negativa davant la IA proposant notes | Ser extremadament transparent sobre el procés. Mostrar la proposta bruta de la IA vs. la retroalimentació final del formador. Emfatitzar el model on el professorat decideix. |
| Sessions AMA amb poca assistència | Oportunitat perduda per a la construcció de comunitat | Enregistrar i compartir. Oferir dues franges horàries si és possible. Mantenir-les opcionals però valuoses (preguntes i respostes exclusives, mostra i explica). |

---

## 14. Resum: El Curs en Una Pàgina

**Què:** Un curs híbrid de 3 setmanes que ensenya al professorat universitari a construir assistents d'aprenentatge amb IA amb LAMB.

**Com:** Vídeos diaris curts amb tasques pràctiques, un fòrum de discussió actiu i sessions AMA en directe. El curs mateix funciona sobre LAMB (dogfooding).

**El Bucle:**
1. Mirar un vídeo curt (5-10 min)
2. Fer alguna cosa concreta amb LAMB (crida a l'acció)
3. Compartir la teva experiència al fòrum
4. Rebre respostes (text o videotutorial) del formador
5. Aquelles respostes alimenten la base de coneixement de l'assistent del curs
6. L'assistent del curs es torna més intel·ligent -- demostrant el valor del que estàs construint

**Avaluació:** Enviar un assistent publicat. La IA proposa una avaluació via LAMBA. El formador revisa i confirma. Els participants experimenten el cicle complet des dels dos costats.

**Filosofia:** La IA assisteix; el professorat decideix. Sempre.

---

*Aquest document defineix l'estratègia didàctica del curs de formació LAMB. El proper pas és desenvolupar els guions detallats dels vídeos i l'estructura del curs a Moodle.*
