# MarkItDown Plus - Guia d'Usuari

## Què és aquest complement?

**MarkItDown Plus** és una eina que converteix els teus documents (PDFs, arxius de Word, PowerPoints, etc.) en un format que pot ser cercat i consultat per assistents d'IA. Divideix els teus documents en peces més petites anomenades "fragments" i els emmagatzema en una base de coneixements.

Pensa-ho com crear un índex per a un llibre: en lloc de llegir tot el llibre per trobar informació, la IA pot buscar ràpidament les seccions rellevants.

---

## Privacitat i Seguretat

### 🔒 Els teus documents romanen privats per defecte

**Important:** Aquesta eina processa els teus documents **als nostres servidors** (localment) per defecte. El teu contingut NO s'envia a serveis externs com OpenAI tret que tu específicament ho triïs.

| Configuració | Què passa amb les teves dades |
|--------------|-------------------------------|
| Descripció d'imatges: **Cap** (per defecte) | ✅ Tot roman local. No s'usen serveis externs. |
| Descripció d'imatges: **Bàsica** | ✅ Tot roman local. Les imatges s'extreuen i es guarden. |
| Descripció d'imatges: **Amb IA** | ⚠️ Les imatges s'envien a OpenAI per descripció. |

**Recomanació:** Per a documents confidencials, registres d'empleats, dades financeres o qualsevol informació sensible, utilitza sempre el mode "Cap" o "Bàsica".

---

## Entenent les Opcions

### 1. Gestió d'Imatges

Quan el teu document conté imatges (gràfics, diagrames, fotos), pots triar com gestionar-les:

#### Opció: Cap (Recomanada per a documents sensibles)
- **Què fa:** Manté les referències d'imatges existents però no extreu ni processa imatges
- **Millor per:** Documents confidencials, processament més ràpid
- **Privacitat:** ✅ Completament local

#### Opció: Bàsica
- **Què fa:** Extreu imatges del document i les guarda amb descripcions simples basades en noms d'arxiu
- **Millor per:** Documents on vols imatges accessibles però no necessites descripcions detallades
- **Privacitat:** ✅ Completament local

#### Opció: Amb IA (LLM)
- **Què fa:** Envia les imatges a la IA d'OpenAI per generar descripcions detallades i intel·ligents
- **Millor per:** Materials educatius, documents públics on el context de les imatges importa
- **Privacitat:** ⚠️ **Les imatges s'envien a OpenAI** - NO usar per a documents confidencials

---

### 2. Com Dividir el teu Document (Mode de Fragmentació)

El teu document necessita dividir-se en peces més petites perquè la IA pugui cercar eficientment. Hi ha tres formes de fer-ho:

#### Opció: Estàndard (Per defecte)
- **Què fa:** Divideix el teu document en peces de mida aproximadament igual (mesurada en caràcters)
- **Millor per:** Documents generals, correus electrònics, articles, text sense estructura
- **Com funciona:** Com tallar una cinta llarga en peces iguals

**Configuracions addicionals per al mode Estàndard:**
- **Mida del fragment:** Com de gran ha de ser cada peça (per defecte: 1000 caràcters, aproximadament 150-200 paraules)
- **Solapament:** Quant text es repeteix entre peces per mantenir el context (per defecte: 200 caràcters)

*Consell: Fragments més petits (500-800) funcionen millor per a preguntes i respostes. Fragments més grans (1500-2500) funcionen millor per a resums.*

#### Opció: Per Pàgina
- **Què fa:** Manté cada pàgina com una peça separada
- **Millor per:** PDFs, presentacions, documents on els salts de pàgina són significatius
- **Funciona amb:** PDF, Word (.docx), PowerPoint (.pptx) únicament

**Configuracions addicionals per al mode Pàgina:**
- **Pàgines per fragment:** Quantes pàgines agrupar juntes (per defecte: 1)

*Exemple: Un PDF de 10 pàgines amb "Pàgines per fragment: 2" crea 5 fragments, cadascun amb 2 pàgines.*

#### Opció: Per Secció
- **Què fa:** Utilitza els encapçalaments del teu document (títols, subtítols) per crear divisions naturals
- **Millor per:** Informes, manuals, documents estructurats amb seccions clares
- **Com funciona:** Respecta l'organització del teu document

**Configuracions addicionals per al mode Secció:**
- **Dividir en nivell d'encapçalament:** Quin nivell d'encapçalament defineix un fragment
  - Nivell 1 = Títols principals (# Encapçalament)
  - Nivell 2 = Subtítols (## Encapçalament) - *recomanat*
  - Nivell 3 = Sub-subtítols (### Encapçalament)
- **Seccions per fragment:** Quantes seccions agrupar juntes (per defecte: 1)

*Exemple: Un informe amb capítols i seccions, usant "Nivell 2" i "1 secció per fragment" crea un fragment per secció, amb els títols de capítol preservats per context.*

---

## Exemples Pràctics

### Exemple 1: Document de Polítiques d'Empresa (Confidencial)

**Escenari:** Estàs pujant un manual de l'empleat amb polítiques sensibles de RRHH.

**Configuració recomanada:**
- Gestió d'imatges: **Cap**
- Mode de fragmentació: **Per Secció**
- Dividir en nivell: **2** (per capturar cada secció de política)
- Seccions per fragment: **1**

**Per què:** Manté tot privat, respecta l'estructura del document, facilita trobar polítiques específiques.

---

### Exemple 2: Catàleg de Productes amb Fotos

**Escenari:** Estàs pujant un catàleg de productes amb moltes imatges que necessiten descripcions.

**Configuració recomanada:**
- Gestió d'imatges: **Bàsica** (o Amb IA si les descripcions són crucials i el contingut no és sensible)
- Mode de fragmentació: **Per Pàgina**
- Pàgines per fragment: **1**

**Per què:** Cada pàgina de producte roman junta, les imatges són accessibles.

---

### Exemple 3: Article d'Investigació

**Escenari:** Estàs pujant un article acadèmic per a propòsits d'investigació.

**Configuració recomanada:**
- Gestió d'imatges: **Bàsica** (per extreure figures i gràfics)
- Mode de fragmentació: **Per Secció**
- Dividir en nivell: **2**
- Seccions per fragment: **1**

**Per què:** Respecta l'estructura de l'article (Resum, Introducció, Mètodes, etc.), manté les figures accessibles.

---

### Exemple 4: Document de Text Llarg

**Escenari:** Estàs pujant un document llarg sense estructura clara (com una transcripció o novel·la).

**Configuració recomanada:**
- Gestió d'imatges: **Cap**
- Mode de fragmentació: **Estàndard**
- Mida del fragment: **1000**
- Solapament: **200**

**Per què:** El mode estàndard funciona millor per a text sense estructura, el solapament assegura que no es perdi context entre peces.

---

## Preguntes Freqüents

### P: Què passa si trio "Per Secció" però el meu document no té encapçalaments?

El sistema automàticament canvia al mode "Estàndard". Obtindràs fragments de mida uniforme en el seu lloc.

### P: Com sé quina mida de fragment usar?

- **Per a preguntes i respostes:** Fragments més petits (500-1000) funcionen millor perquè són més enfocats
- **Per a resums:** Fragments més grans (1500-2500) proporcionen més context
- **En cas de dubte:** El valor per defecte (1000) funciona bé per a la majoria de casos

### P: Quins tipus d'arxiu són compatibles?

PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), HTML, arxius d'àudio (.mp3, .wav), CSV, JSON, XML, arxius ZIP i llibres electrònics EPUB.

### P: Es preservarà el meu arxiu original?

Sí! L'arxiu original es guarda, i també es crea una versió en Markdown per facilitar la visualització.

### P: Quant temps triga el processament?

Depèn de la mida de l'arxiu i les opcions triades:
- Documents petits (< 10 pàgines): Uns segons
- Documents grans amb descripcions d'imatges per IA: Diversos minuts

---

## Obtenir Ajuda

Si tens preguntes o trobes problemes:
1. Verifica que el teu arxiu estigui en un format compatible
2. Prova primer amb la configuració per defecte
3. Contacta el teu administrador del sistema per assistència

---

*Última actualització: Gener 2026*

