# Plataforma LAMB -- Resum per a parts interessades

**Versió:** 1.0
**Data:** 15 de febrer de 2026
**Audiència:** Professorat, Administradors d'Institució, Administradors de Sistemes

---

## Taula de continguts

1. [Què és LAMB?](#1-què-és-lamb)
2. [La filosofia: IA segura en l'educació](#2-la-filosofia-ia-segura-en-leducació)
3. [A qui va dirigit LAMB?](#3-a-qui-va-dirigit-lamb)
4. [Capacitats clau](#4-capacitats-clau)
5. [Com funciona -- Per al professorat](#5-com-funciona--per-al-professorat)
6. [Com funciona -- Integració LTI amb Moodle](#6-com-funciona--integració-lti-amb-moodle)
7. [Com funciona -- Per als administradors d'institució](#7-com-funciona--per-als-administradors-dinstitució)
8. [Com funciona -- Per als administradors de sistemes](#8-com-funciona--per-als-administradors-de-sistemes)
9. [Avaluació assistida per IA: Evaluaitor i LAMBA](#9-avaluació-assistida-per-ia-evaluaitor-i-lamba)
10. [Arquitectura general](#10-arquitectura-general)
11. [Privacitat i sobirania de dades](#11-privacitat-i-sobirania-de-dades)
12. [Glossari](#12-glossari)

---

## 1. Què és LAMB?

**LAMB** (Learning Assistants Manager and Builder) és una plataforma de codi obert que permet als educadors crear, gestionar i desplegar assistents d'aprenentatge basats en IA directament en sistemes de gestió de l'aprenentatge (com Moodle) -- **sense escriure cap línia de codi**.

Penseu en LAMB com un **"constructor de xatbots educatius"**: permet als educadors combinar models de llenguatge grans (GPT-4, Mistral, models allotjats localment, etc.) amb els seus propis materials de curs per crear tutors d'IA especialitzats als quals els estudiants poden accedir directament des de Moodle.

### La proposta en una frase

> **LAMB dona als educadors el control total per construir un "ChatGPT especialitzat" per a la seva assignatura, connectar-lo a Moodle i mantenir les dades dels estudiants completament segures.**

### Proposta de valor principal

| Per a... | LAMB proporciona... |
|----------|---------------------|
| **Professorat** | Un constructor sense codi per crear tutors d'IA fonamentats en materials de curs |
| **Institucions** | Desplegament d'IA mantenint la sobirania de dades i la privacitat |
| **Estudiants** | Assistència d'IA contextualitzada i específica per assignatura dins del seu SGA habitual |

### Fonament acadèmic

LAMB no és un producte comercial d'una startup. Està desenvolupat per investigadors universitaris i ha estat revisat per parells:

> *"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"*
> Marc Alier, Juanan Pereira, Francisco Jose Garcia-Penalvo, Maria Jose Casan, Jose Cabre
> *Computer Standards & Interfaces*, Volume 92, March 2025

El projecte està liderat per **Marc Alier** (Universitat Politècnica de Catalunya, Barcelona) i **Juanan Pereira** (Universidad del País Vasco / Euskal Herriko Unibertsitatea, País Basc), amb la col·laboració de la Universidad de Salamanca (Grup de Recerca Grial) i Tknika (Centre Basc de Recerca Aplicada en Formació Professional).

---

## 2. La filosofia: IA segura en l'educació

LAMB està construït sobre els principis del **Manifest d'IA Segura en l'Educació** (https://manifesto.safeaieducation.org), un marc signat per més de 87 acadèmics d'arreu del món, incloent-hi el Dr. Charles Severance (Universitat de Michigan, creador de Coursera).

La creença central del manifest: **"La IA sempre ha d'estar al servei de les persones, millorant les capacitats humanes en lloc de substituir-les."**

### Els set principis

| # | Principi | Què significa per a l'educació | Com ho implementa LAMB |
|---|----------|-------------------------------|----------------------|
| 1 | **Supervisió humana** | Totes les decisions romanen sota supervisió humana. La IA no pot ser responsable d'educar els estudiants. | Els educadors creen, controlen i gestionen tots els assistents. El comportament de cada assistent el defineix l'educador. |
| 2 | **Protecció de la privacitat** | Les dades dels estudiants s'han de protegir. Els estudiants mantenen el control total sobre les seves dades personals. | Infraestructura autoallotjada. Cap dada d'estudiant surt de la institució. No s'envia informació personal identificable a proveïdors externs de LLM sense configuració explícita de la institució. |
| 3 | **Alineació educativa** | La IA ha de donar suport a les estratègies educatives institucionals, no minar-les. | Els assistents es fonamenten en materials de curs específics i objectius d'aprenentatge. Només responen dins l'àmbit definit per l'educador. |
| 4 | **Integració didàctica** | La IA ha d'encaixar sense fricció en els fluxos de treball docents existents. | La integració LTI incorpora els assistents directament als cursos de Moodle. Sense inicis de sessió ni plataformes separades per als estudiants. |
| 5 | **Precisió i explicabilitat** | Les respostes de la IA han de ser precises i traçables. | El RAG (generació augmentada per recuperació) proporciona citacions automàtiques de les fonts. El mode de depuració permet als educadors inspeccionar exactament què "veu" la IA. |
| 6 | **Interfícies transparents** | Les interfícies han de comunicar clarament les limitacions de la IA. | Comunicació clara que les respostes són generades per IA. Els documents font es citen quan es fan servir com a referència. |
| 7 | **Entrenament ètic** | Els models d'IA han de ser entrenats èticament amb transparència sobre les fonts de dades. | Plataforma de codi obert. Els educadors trien el seu proveïdor de LLM. Transparència total sobre quins models s'utilitzen. |

### Per què no fer servir directament ChatGPT o Google Gemini?

El manifest i LAMB aborden una preocupació real: quan els educadors utilitzen plataformes d'IA comercials directament:

- **Cedeixen el seu coneixement** -- els prompts i materials es converteixen en dades d'entrenament per al proveïdor
- **Exposen dades dels estudiants** -- les identitats, preguntes i comportament dels estudiants són processats per tercers
- **No tenen transparència** -- com es comporta el model, quines dades conserva i com evoluciona són aspectes opacs
- **No poden personalitzar el comportament** -- no hi ha manera de restringir les respostes als materials del curs ni d'imposar enfocaments pedagògics
- **Risc de dependència del proveïdor** -- canviar de proveïdor implica reconstruir-ho tot

LAMB resol tots aquests problemes donant a la institució el control total sobre tota la pila tecnològica.

---

## 3. A qui va dirigit LAMB?

### Professorat (Usuaris Creadors)

El professorat és l'usuari principal de LAMB. Utilitzen la **Interfície de Creació** -- un entorn web sense codi -- per:

- Crear assistents d'IA especialitzats per als seus cursos
- Construir bases de coneixement a partir de múltiples fonts: càrrega de fitxers (PDF, Word, PowerPoint, fulls de càlcul, Markdown), URLs web i llocs web rastrejats, i transcripcions de vídeos de YouTube
- Configurar com es comporta la IA (prompts de sistema, selecció de model, configuració de RAG)
- Crear rúbriques d'avaluació estructurades i adjuntar-les a assistents per a l'avaluació assistida per IA (Evaluaitor)
- Configurar activitats de qualificació on els estudiants entreguen treballs, la IA proposa una avaluació basada en una rúbrica i el professor revisa i decideix la nota final (LAMBA)
- Provar els assistents abans de publicar-los per als estudiants
- Publicar assistents com a activitats LTI a Moodle
- Consultar analítiques sobre com els estudiants utilitzen els seus assistents

**No calen habilitats de programació.** La IA mai no qualifica de manera autònoma -- ajuda el professor proposant avaluacions, però el professor sempre revisa, edita i confirma la nota final. Un professor pot crear i publicar el seu primer assistent en uns 15 minuts.

### Administradors d'Institució (Administradors d'Organització)

Els administradors d'organització gestionen el seu departament o institució dins de LAMB:

- Gestionar els usuaris de la seva organització (crear, activar/desactivar)
- Configurar proveïdors d'IA (claus d'API, models disponibles)
- Establir polítiques de registre (registre obert vs. només per invitació)
- Activar/desactivar funcionalitats com la compartició d'assistents
- Gestionar l'accés LTI Creator per a la seva organització

### Administradors de Sistemes

Els administradors de sistemes gestionen el desplegament de LAMB:

- Desplegar i mantenir la infraestructura de LAMB
- Crear i gestionar organitzacions (multi-tenència)
- Configurar proveïdors de LLM globals i claus d'API
- Gestionar usuaris i rols a nivell de tot el sistema
- Configurar credencials LTI
- Monitorar l'estat i el rendiment del sistema

---

## 4. Capacitats clau

### Per a la docència

| Capacitat | Descripció |
|-----------|------------|
| **Assistents il·limitats** | Creeu tants assistents d'IA com necessiteu, cadascun amb un comportament únic |
| **Tutors especialitzats per assignatura** | Assistents que només responen dins del context del curs definit per l'educador |
| **Base de coneixement (RAG)** | Ingesteu contingut des de fitxers (PDF, Word, PowerPoint, fulls de càlcul), URLs web, rastreig de llocs web i transcripcions de vídeos de YouTube -- la IA els utilitza com el seu "llibre de text" |
| **Citacions automàtiques** | Quan la IA fa referència a materials pujats, en cita la font |
| **Múltiples models d'IA** | Canvieu entre GPT-4o, Mistral, Llama i altres models amb un sol clic |
| **Mode de depuració** | Veieu el prompt complet enviat a la IA, permetent l'ajust fi |
| **Publicació LTI** | Publiqueu assistents com a activitats de Moodle amb uns pocs clics |
| **Compartició d'assistents** | Compartiu assistents amb col·legues de la mateixa organització |
| **Avaluadors basats en rúbriques** | Creeu rúbriques d'avaluació estructurades (manualment o generades per IA) i adjunteu-les a assistents per a una avaluació consistent assistida per IA |
| **Avaluació assistida per IA (LAMBA)** | Els estudiants entreguen treballs via LTI; la IA proposa una avaluació segons les rúbriques; el professor revisa, edita i decideix la nota final; les qualificacions se sincronitzen amb Moodle |
| **Analítiques de xat** | Consulteu com els estudiants interactuen amb els vostres assistents |
| **Multilingüe** | Interfície disponible en anglès, castellà, català i basc |

### Per a l'administració

| Capacitat | Descripció |
|-----------|------------|
| **Multi-tenència** | Organitzacions aïllades amb configuració independent |
| **Gestió d'usuaris** | Creació, activació/desactivació i gestió de comptes d'usuari |
| **Accés basat en rols** | Rols d'administrador de sistema, administrador d'organització, creador i usuari final |
| **Flexibilitat de proveïdors de LLM** | Configureu OpenAI, Anthropic, Ollama o altres proveïdors per organització |
| **Claus de registre** | Registre específic per organització amb claus secretes |
| **Accés LTI Creator** | Els educadors poden accedir a LAMB directament des de Moodle via LTI |

### Per a la infraestructura

| Capacitat | Descripció |
|-----------|------------|
| **Autoallotjat** | Desplegueu als vostres propis servidors -- sobirania total de dades |
| **Desplegament amb Docker** | Desplegament amb una sola comanda amb Docker Compose |
| **API compatible amb OpenAI** | Punt d'accés estàndard `/v1/chat/completions` per a la integració |
| **Arquitectura de connectors** | Connectors extensibles per a nous proveïdors de LLM |
| **Base de dades SQLite** | Base de dades simple basada en fitxers (no cal un servidor de BD separat) |

---

## 5. Com funciona -- Per al professorat

### El flux de treball del professorat (15 minuts fins al primer assistent)

#### Pas 1: Iniciar sessió
Accediu a la Interfície de Creació de LAMB amb les vostres credencials institucionals (o via LTI des de Moodle).

#### Pas 2: Crear un assistent
Doneu un nom i una descripció al vostre assistent. Trieu un model d'IA (p. ex., GPT-4o-mini per a respostes ràpides, GPT-4o per a raonament complex).

#### Pas 3: Definir el comportament
Escriviu un **prompt de sistema** que indiqui a la IA com ha de comportar-se. Per exemple:

> *"Ets un tutor d'Introducció a la Informàtica. Respon només preguntes relacionades amb algorismes, estructures de dades i fonaments de programació. Quan els estudiants preguntin sobre temes fora del curs, redirigeix-los educadament. Sempre anima els estudiants a pensar els problemes abans de donar respostes directes."*

#### Pas 4: Construir una base de coneixement (Opcional però recomanat)
Afegiu els vostres materials de curs des de múltiples fonts:
- **Pujar fitxers** -- apunts de classe, capítols de llibres de text, conjunts de problemes (PDF, Word, PowerPoint, fulls de càlcul, Markdown i més)
- **Ingerir des d'URLs** -- apunteu a una pàgina web o deixeu que el rastrejador segueixi els enllaços d'un lloc
- **Importar vídeos de YouTube** -- extracció i indexació automàtica de transcripcions de vídeo

LAMB processa i indexa tot el contingut perquè la IA pugui fer-hi referència en respondre preguntes.

#### Pas 5: Configurar RAG
Connecteu la vostra base de coneixement a l'assistent. Configureu quants fragments de context es recuperen (Top K). Ara la IA fonamentarà les seves respostes en els vostres materials reals de curs i en citarà les fonts.

#### Pas 6: Provar
Utilitzeu la interfície de xat integrada per provar el vostre assistent. Feu-li preguntes que els vostres estudiants podrien fer. Utilitzeu el **mode de depuració** per veure exactament quin prompt i context rep la IA.

#### Pas 7: Publicar a Moodle
Feu clic a "Publicar". LAMB genera les credencials LTI (URL de l'eina, clau del consumidor, secret). Afegiu-les a Moodle com una activitat d'eina externa. Els estudiants ja poden accedir a l'assistent directament des de la pàgina del seu curs.

### Dues maneres d'accedir a LAMB com a professor

1. **Inici de sessió directe** -- Navegueu a l'URL de LAMB i inicieu sessió amb correu electrònic i contrasenya
2. **Llançament LTI Creator** -- Feu clic a un enllaç LTI a Moodle i accediu directament a la Interfície de Creació (sense necessitat de contrasenya separada). Això ho configura l'administrador de la vostra organització.

---

## 6. Com funciona -- Integració LTI amb Moodle

LTI (Learning Tools Interoperability, Interoperabilitat d'Eines d'Aprenentatge) és el protocol estàndard que connecta LAMB amb Moodle. LAMB admet tres modes d'integració LTI:

### 6.1 LTI Unificat (Recomanat per a nous desplegaments)

L'enfocament **LTI Unificat** utilitza una sola eina LTI per a tota la instància de LAMB. És l'opció més flexible i completa.

**Com funciona:**

1. L'administrador de sistemes configura **un únic conjunt de credencials LTI globals** per a tota la instància de LAMB
2. Un administrador de Moodle afegeix LAMB com a eina externa utilitzant aquestes credencials globals
3. El professorat afegeix activitats LAMB als seus cursos a Moodle
4. **Primera configuració:** Quan un professor fa clic a l'activitat per primera vegada, veu una pàgina de configuració on selecciona quins assistents publicats vol fer disponibles
5. **Després de la configuració:** Els estudiants que fan clic a l'activitat veuen els assistents seleccionats i poden començar a xatejar
6. **Tauler de l'instructor:** El professorat disposa d'un tauler que mostra estadístiques d'ús, registres d'accés dels estudiants i (si està activat) revisió anonimitzada de transcripcions de xat

**Característiques clau:**
- Múltiples assistents per activitat (els estudiants poden triar)
- Tauler de l'instructor amb estadístiques d'ús
- Visibilitat opcional del xat (transcripcions anonimitzades per a la revisió pedagògica)
- Flux de consentiment de l'estudiant quan la visibilitat del xat està activada
- Un sol conjunt de credencials LTI per a tota la instància

**Experiència de l'estudiant:**
1. Fer clic a l'enllaç de l'activitat a Moodle
2. (Si la visibilitat del xat està activada i és el primer accés) Acceptar un avís de consentiment
3. Veure els assistents disponibles i començar a xatejar
4. Tot passa dins de Moodle -- no cal cap inici de sessió separat

### 6.2 LTI Legacy (Un assistent per activitat)

L'enfocament anterior on cada assistent publicat té les seves pròpies credencials LTI. Encara funciona però és menys flexible.

**Com funciona:**
1. El professor publica un assistent a LAMB
2. LAMB genera una clau de consumidor i un secret LTI únics per a aquell assistent
3. El professor els afegeix com a eina externa a Moodle
4. Els estudiants fan clic a l'enllaç i accedeixen directament a aquell assistent

### 6.3 LTI Creator (Accés del professorat a LAMB des de Moodle)

Aquest mode permet al professorat accedir a la mateixa Interfície de Creació de LAMB a través de Moodle, eliminant la necessitat de credencials d'inici de sessió separades per a LAMB.

**Com funciona:**
1. L'administrador d'organització configura les credencials de LTI Creator
2. L'administrador de Moodle afegeix LAMB Creator com a eina externa
3. Quan un professor fa clic a l'enllaç, accedeix directament a la Interfície de Creació de LAMB
4. La seva identitat queda vinculada al seu compte del SGA -- no cal contrasenya separada
5. Pot crear i gestionar assistents com de costum

---

## 7. Com funciona -- Per als administradors d'institució

### Gestió d'organitzacions

LAMB utilitza un model **multi-tenant** on cada institució, departament o equip és una **organització**. Les organitzacions proporcionen un aïllament complet:

- Cada organització té els seus propis usuaris, assistents i bases de coneixement
- Cada organització configura els seus propis proveïdors d'IA i claus d'API
- Els usuaris d'una organització no poden veure els recursos d'una altra

### Responsabilitats clau

#### Gestió d'usuaris
- Crear comptes per al professorat (usuaris creadors) i usuaris finals
- Activar/desactivar comptes d'usuari
- Establir rols d'usuari dins de l'organització (administrador, membre)
- Gestionar els usuaris de LTI Creator que accedeixen via Moodle

#### Configuració de proveïdors d'IA
- Configurar quins proveïdors d'IA estan disponibles (OpenAI, Anthropic, Ollama, etc.)
- Establir claus d'API per a cada proveïdor
- Definir models per defecte
- Controlar quins models pot utilitzar el professorat

#### Polítiques d'accés
- Activar/desactivar el registre obert per a l'organització
- Establir una clau de registre per a l'autoregistre
- Activar/desactivar la compartició d'assistents entre professorat
- Configurar les credencials d'accés de LTI Creator

#### Tipus d'usuaris

| Tipus d'usuari | Accés | Propòsit |
|----------------|-------|----------|
| **Creador** | Interfície de Creació (constructor d'assistents) | Professorat que crea i gestiona assistents |
| **Usuari final** | Només interfície de xat (Open WebUI) | Usuaris que només necessiten interactuar amb assistents publicats |
| **LTI Creator** | Interfície de Creació (via LTI de Moodle) | Professorat que accedeix a LAMB a través del seu SGA |

---

## 8. Com funciona -- Per als administradors de sistemes

### Desplegament

LAMB està dissenyat per a un **desplegament autoallotjat** amb Docker Compose. La pila inclou:

| Servei | Port | Propòsit |
|--------|------|----------|
| **Backend** (FastAPI) | 9099 | API central, autenticació, pipeline de completions |
| **Frontend** (Svelte) | 5173 (dev) | Aplicació web de la Interfície de Creació |
| **Open WebUI** | 8080 | Interfície de xat per a estudiants i usuaris finals |
| **KB Server** | 9090 | Processament de documents de la base de coneixement i cerca vectorial |

### Inici ràpid
```bash
git clone https://github.com/Lamb-Project/lamb.git
cd lamb
./scripts/setup.sh
docker-compose up -d
```

### Configuració clau

| Variable | Propòsit |
|----------|----------|
| `LAMB_DB_PATH` | Ruta al directori de la base de dades de LAMB |
| `OWI_DATA_PATH` | Ruta al directori de dades d'Open WebUI |
| `LAMB_BEARER_TOKEN` | Clau d'API per al punt d'accés de completions (**canvieu el valor per defecte!**) |
| `LAMB_JWT_SECRET` | Secret per signar tokens JWT (**establiu un valor segur!**) |
| `OPENAI_API_KEY` | Clau d'API d'OpenAI per defecte (es pot sobreescriure per organització) |
| `LTI_GLOBAL_CONSUMER_KEY` | Clau de consumidor LTI global per al LTI Unificat |
| `LTI_GLOBAL_SECRET` | Secret compartit LTI global |
| `OWI_BASE_URL` | URL interna d'Open WebUI |
| `OWI_PUBLIC_BASE_URL` | URL pública d'Open WebUI |

### Tasques d'administració de sistemes

- **Crear organitzacions** -- Configurar tenants aïllats per a departaments o institucions
- **Gestionar usuaris globals** -- Crear comptes d'administrador de sistema, gestionar tots els usuaris
- **Configurar LTI** -- Establir les credencials LTI globals per al LTI Unificat
- **Monitorar l'estat** -- Punt d'accés `GET /status` per a comprovacions d'estat
- **Còpies de seguretat de la base de dades** -- Fer còpies de seguretat regulars dels fitxers de la base de dades SQLite
- **SSL/TLS** -- Configurar HTTPS via Caddy o proxy invers
- **Gestió de proveïdors de LLM** -- Configurar valors per defecte a nivell de sistema, monitorar l'ús de les API

### Llista de verificació per a producció

- [ ] Canviar `LAMB_BEARER_TOKEN` del valor per defecte
- [ ] Establir `LAMB_JWT_SECRET` amb un valor aleatori segur
- [ ] Configurar SSL/TLS (es recomana Caddy)
- [ ] Configurar còpies de seguretat regulars de la base de dades
- [ ] Configurar claus d'API de LLM específiques per organització
- [ ] Establir el nivell de registre (`GLOBAL_LOG_LEVEL=WARNING` per a producció)
- [ ] Configurar la monitorització del sistema
- [ ] Provar la integració LTI de punta a punta

### Arquitectura multi-tenant

```
Organització del Sistema (sempre existeix, no es pot eliminar)
    |
    +-- Departament A (slug: "engineering")
    |   +-- Usuaris (amb rols: propietari, administrador, membre)
    |   +-- Assistents
    |   +-- Bases de coneixement
    |   +-- Configuració independent de proveïdors de LLM
    |
    +-- Departament B (slug: "physics")
    |   +-- Usuaris
    |   +-- Assistents
    |   +-- Bases de coneixement
    |   +-- Configuració independent de proveïdors de LLM
    |
    +-- Institució associada (slug: "partner-univ")
        +-- ...
```

---

## 9. Avaluació assistida per IA: Evaluaitor i LAMBA

LAMB inclou un sistema integrat d'**Evaluaitor** per a l'avaluació basada en rúbriques, i l'aplicació **LAMBA** (Learning Activities & Machine-Based Assessment, Activitats d'Aprenentatge i Avaluació Basada en Màquines) s'està integrant a la plataforma per proporcionar un pipeline complet d'avaluació assistida per IA. De manera fonamental, **la IA mai no qualifica de manera autònoma** -- proposa avaluacions que el professor ha de revisar, editar si cal i aprovar explícitament abans que cap nota arribi a l'estudiant. Aquesta és una aplicació directa del Principi 1 del Manifest (Supervisió Humana).

### 9.1 Evaluaitor: Avaluació basada en rúbriques

L'Evaluaitor és el sistema de gestió de rúbriques de LAMB. Permet al professorat crear rúbriques d'avaluació estructurades i adjuntar-les a assistents, convertint qualsevol assistent en un avaluador d'IA consistent.

#### Creació de rúbriques

El professorat pot crear rúbriques de tres maneres:

1. **Creació manual** -- Definiu criteris, nivells de rendiment, pesos i puntuació des de zero
2. **Generació amb IA** -- Descriviu en llenguatge natural què voleu avaluar i la IA genera una rúbrica completa (compatible amb anglès, castellà, català i basc)
3. **A partir de plantilles** -- Dupliqueu una rúbrica pública compartida per col·legues o promoguda pels administradors com a plantilla de mostra

#### Estructura de la rúbrica

Cada rúbrica conté:
- **Títol i descripció** -- Què s'avalua
- **Criteris** -- Les dimensions de l'avaluació (p. ex., "Qualitat del contingut", "Pensament crític"), cadascuna amb un pes
- **Nivells de rendiment** -- Descripcions per a cada nivell de qualitat (p. ex., Exemplar / Competent / En desenvolupament / Inicial) amb puntuacions
- **Tipus de puntuació** -- Punts, percentatge, holístic, punt únic o llista de verificació
- **Metadades** -- Àrea temàtica, nivell acadèmic

#### Ús de rúbriques amb assistents

Quan una rúbrica s'adjunta a un assistent, el pipeline de completions de LAMB injecta automàticament la rúbrica en el context de la IA amb un format optimitzat per a l'avaluació -- incloent-hi instruccions de puntuació, càlculs de pesos i format de sortida esperat. Això significa que la IA produeix propostes d'avaluació consistents segons els criteris específics de la rúbrica, que el professor després revisa i finalitza.

#### Compartició i plantilles

- Les rúbriques poden ser **privades** (només les veu el creador) o **públiques** (visibles per a tots els membres de l'organització)
- Els administradors poden promoure rúbriques com a **plantilles de mostra** disponibles a tota la plataforma
- Les rúbriques es poden **exportar/importar** com a JSON per compartir entre institucions

### 9.2 LAMBA: El pipeline de qualificació (en procés d'integració)

LAMBA va començar com una aplicació LTI independent i ara s'està integrant directament a LAMB. Proporciona el cicle de vida complet de l'avaluació a través de Moodle:

#### El flux de treball d'avaluació

1. **El professorat crea activitats d'avaluació** a Moodle via LTI i assigna un assistent avaluador basat en rúbriques
2. **Els estudiants pugen documents** (PDF, Word, TXT, codi font) a través de la interfície de Moodle
3. **La IA proposa avaluacions** -- l'assistent analitza cada entrega segons la rúbrica i produeix una puntuació suggerida i comentaris escrits
4. **El professorat revisa les propostes de la IA** -- pot acceptar, editar o anul·lar completament la puntuació i els comentaris suggerits per a cada estudiant
5. **El professorat confirma la nota final** -- només la nota aprovada pel professor és la nota real
6. **Les notes finals se sincronitzen amb el quadern de qualificacions de Moodle** via LTI

#### Característiques clau

| Característica | Descripció |
|----------------|------------|
| **Propostes basades en rúbriques** | La IA proposa avaluacions segons rúbriques estructurades, oferint al professor un punt de partida consistent |
| **El professor té l'última paraula** | La suggerència de la IA i la nota real són camps separats -- el professor ha de moure explícitament l'avaluació proposada a la nota final, editant-la si cal |
| **Entregues en grup** | Suport per a treballs en grup amb codis d'entrega compartits |
| **Sincronització de notes amb Moodle** | Només les notes finals confirmades pel professor s'envien al quadern de qualificacions de Moodle |
| **Processament per lots** | Sol·liciteu propostes de la IA per a totes les entregues alhora amb seguiment del progrés en temps real |
| **Supervisió humana** | La IA assisteix; el professor decideix -- consistent amb el Principi 1 del Manifest |

#### Objectiu

Reduir la càrrega de treball d'avaluació del professorat en un **50%** en avaluacions rutinàries, proporcionant comentaris proposats en minuts en lloc de dies. La IA ofereix un punt de partida consistent basat en rúbriques, però **el professor sempre manté l'autoritat plena sobre la nota final**.

---

## 10. Arquitectura general

```
+------------------------------------------------------------------+
|                         Plataforma LAMB                          |
|                                                                  |
|   +----------------+    +----------------+    +----------------+ |
|   |   Interfície   |    |   Backend      |    |   Open WebUI   | |
|   |   de Creació   |<-->|   (FastAPI)     |<-->|   (Xat UI)     | |
|   |   (Svelte)     |    |   Port 9099    |    |   Port 8080    | |
|   +----------------+    +-------+--------+    +----------------+ |
|          |                      |                      |         |
|    El professorat         Lògica central         Els estudiants  |
|    l'utilitza per         i API                  l'utilitzen per  |
|    construir assistents         |                xatejar         |
|                          +------+-------+                        |
|                          |  KB Server   |                        |
|                          |  Port 9090   |                        |
|                          +--------------+                        |
|                                 |                                |
|                          +------+-------+                        |
|                          | Proveïdor LLM|                        |
|                          | OpenAI/Ollama|                        |
|                          +--------------+                        |
+------------------------------------------------------------------+
         |                                           |
    LTI Creator                                 LTI Estudiant
    (El professorat accedeix                    (Els estudiants accedeixen
     a LAMB des de Moodle)                      als assistents des de Moodle)
         |                                           |
+------------------------------------------------------------------+
|                     Moodle (SGA)                                 |
+------------------------------------------------------------------+
```

### Com es respon la pregunta d'un estudiant

1. L'estudiant escriu una pregunta a la interfície de xat (Open WebUI, llançat via LTI)
2. La pregunta arriba a l'API de completions de LAMB
3. LAMB carrega la configuració de l'assistent (prompt de sistema, model, configuració de RAG)
4. El **processador RAG** consulta la base de coneixement per trobar contingut rellevant dels documents pujats
5. El **processador de prompts** combina el prompt de sistema, el context recuperat i la pregunta de l'estudiant
6. El **connector** envia tot al LLM configurat (p. ex., OpenAI GPT-4o)
7. La resposta del LLM es transmet en temps real a l'estudiant amb citacions de les fonts

---

## 11. Privacitat i sobirania de dades

### On resideixen les dades

| Dades | Ubicació | Qui les controla |
|-------|----------|-----------------|
| Comptes d'usuari | Base de dades de LAMB (servidor de la institució) | Institució |
| Configuracions dels assistents | Base de dades de LAMB | Educador + institució |
| Materials de curs (bases de coneixement) | ChromaDB al servidor de la institució | Educador + institució |
| Historial de xat | Base de dades d'Open WebUI al servidor de la institució | Institució |
| Interaccions dels estudiants | Servidor de la institució | Institució |

### Què NO surt de la institució

- Identitats i dades personals dels estudiants
- Converses de xat i historial d'interaccions
- Materials de curs pujats i bases de coneixement
- Analítiques d'ús i dades d'avaluació

### Què s'envia a serveis externs (Configurable)

- **Només el text de les preguntes i el context** s'envia al proveïdor de LLM configurat (OpenAI, etc.)
- Això es pot **eliminar completament** utilitzant models allotjats localment (Ollama amb Llama, Mistral, etc.)
- La institució tria quin proveïdor de LLM utilitzar i pot canviar en qualsevol moment

### Alineació amb el RGPD i FERPA

- Autoallotjat: conformitat total amb els requisits de residència de dades
- Sense registres obligatoris a tercers per als estudiants
- Els estudiants accedeixen als assistents a través del seu SGA existent -- no calen comptes nous
- Retenció de dades clara sota control institucional
- La visibilitat opcional del xat requereix el consentiment explícit de l'estudiant

---

## 12. Glossari

| Terme | Definició |
|-------|-----------|
| **Assistent** | Un xatbot impulsat per IA configurat per un professor amb un comportament, coneixement i configuració de model específics |
| **Interfície de Creació** | La interfície web on el professorat construeix i gestiona assistents |
| **Base de coneixement (KB)** | Una col·lecció de documents pujats que la IA pot consultar en respondre preguntes |
| **RAG** | Retrieval-Augmented Generation (Generació Augmentada per Recuperació) -- la tècnica de recuperar fragments rellevants de documents per incloure'ls en els prompts de la IA |
| **LTI** | Learning Tools Interoperability (Interoperabilitat d'Eines d'Aprenentatge) -- el protocol estàndard per connectar eines externes a un SGA |
| **SGA** | Sistema de Gestió de l'Aprenentatge (p. ex., Moodle, Canvas) |
| **Organització** | Un tenant aïllat a LAMB (departament, institució o equip) amb els seus propis usuaris i configuració |
| **Open WebUI (OWI)** | El component d'interfície de xat on els estudiants interactuen amb els assistents publicats |
| **Prompt de sistema** | Instruccions que defineixen com es comporta un assistent d'IA (personalitat, regles, limitacions) |
| **Connector** | Un connector que connecta LAMB amb un proveïdor de LLM específic (OpenAI, Ollama, Anthropic) |
| **LTI Unificat** | El mode LTI recomanat on una sola eina serveix múltiples assistents per activitat |
| **LTI Creator** | Un mode LTI que permet al professorat accedir a la Interfície de Creació des de Moodle |
| **Evaluaitor** | El sistema integrat de gestió de rúbriques de LAMB per crear criteris d'avaluació estructurats |
| **Rúbrica** | Un conjunt estructurat de criteris amb nivells de rendiment i pesos utilitzat per avaluar el treball dels estudiants de manera consistent |
| **LAMBA** | Learning Activities & Machine-Based Assessment (Activitats d'Aprenentatge i Avaluació Basada en Màquines) -- el pipeline d'avaluació assistida per IA (en procés d'integració a LAMB). La IA proposa avaluacions; el professor decideix la nota final. |
| **Manifest** | El Manifest d'IA Segura en l'Educació -- el marc ètic que guia el disseny de LAMB |

---

## Enllaços clau

| Recurs | URL |
|--------|-----|
| Repositori GitHub de LAMB | https://github.com/Lamb-Project/lamb |
| Lloc web del projecte LAMB | https://lamb-project.org |
| LAMBA (Extensió de qualificació) | https://github.com/Lamb-Project/LAMBA |
| Manifest d'IA Segura en l'Educació | https://manifesto.safeaieducation.org |
| Llista de verificació del Manifest | https://manifesto.safeaieducation.org/checklist |
| Article de recerca (DOI) | https://doi.org/10.1016/j.csi.2024.103940 |

---

*Aquest document ha estat preparat com a material de formació per a parts interessades del projecte LAMB.*
*Darrera actualització: 15 de febrer de 2026*
