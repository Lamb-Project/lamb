# LAMB - Learning Assistants Manager and Builder

**Plataforma web per projectar, entrenar i publicar assistents d'aprenentatge basats en IA sense escriure codi**

---

## Què és LAMB?

**LAMB** és una plataforma web de codi obert que et permet **dissenyar, entrenar i publicar assistents d'aprenentatge basats en IA** de forma visual i intuïtiva. Funciona com un "constructor de chatbots docents" que combina models de llenguatge (GPT-4, Mistral, models locals) amb els teus propis materials educatius.

**LAMB** és un projecte de codi obert desenvolupat per Marc Alier i Juanan Pereira, professors i investigadors de la Universitat Politècnica de Catalunya (UPC) i Universidad del País Vasco (UPV/EHU).

- **Website:** [http://www.lamb-project.org](http://www.lamb-project.org)
- **GitHub:** [https://github.com/Lamb-Project/lamb](https://github.com/Lamb-Project/lamb)
- **Llicència:** GPL v3
- **Manifest:** [Safe AI Education](https://manifesto.safeaieducation.org)

---

## Característiques Principals

### 🎓 Tutors Temàtics Especialitzats
Dissenya assistents que només responen sobre la matèria que triïs, mantenint-se sempre en el context educatiu apropiat.

### 📚 Ingestió Intel·ligent de Coneixement
Puja documents (PDF, Word, Markdown) i LAMB els processa automàticament amb un **model de dades flexible** que:
- Extreu i estructura el contingut preservant context i relacions
- Crea embeddings semàntics optimitzats per a cerca educativa
- Permet metadades personalitzades per a cada document
- S'adapta a diferents formats i estructures de contingut
- Alimenta el model mitjançant RAG (Retrieval Augmented Generation)

### 🔍 Proves i Depuració Avançades
Mode "debug" que mostra el prompt complet per entendre exactament què s'envia al model, facilitant l'optimització de respostes.

### 🎯 Integració LTI amb Moodle
Publica l'assistent com a eina externa LTI i incrusta'l al teu Moodle en un parell de clics.

### 🔒 Privacitat Garantida
Els estudiants interactuen dins de LAMB; les seves dades no es comparteixen amb proveïdors externs de models d'IA.

---

## Per a qui és LAMB?

- **📖 Docents i formadors** que necessiten un ajudant virtual centrat en la seva temàtica específica
- **🏫 Centres educatius** que usen Moodle o altres LMS i requereixen integrar IA sense exposar dades estudiantils
- **💡 Equips d'innovació** que experimenten amb diferents LLM i necessiten un panell unificat de gestió

---

## Funcionalitats Clau

### Assistents Il·limitats
Cadascun amb les seves pròpies instruccions, to i límits personalitzats.

### Bases de Coneixement Flexibles
- **Model de dades adaptable**: arquitectura flexible que permet diferents tipus de contingut i estructures
- Suport per PDF, DOCX, Markdown (més formats pròximament)
- Bases públiques o privades segons necessitats
- Sistema d'embeddings vectorials per a cerca semàntica
- Connectors en desenvolupament per a fonts externes (Google Drive, YouTube, APIs)

### Múltiples Models d'IA
- OpenAI GPT-4o
- Mistral
- Models locals
- Canvi de model en un clic

### Cites Automàtiques
L'assistent proporciona respostes amb referències als documents font utilitzats.

### Portabilitat Total
- Exportar/importar assistents en format JSON
- Fàcil versionat i compartició

### Interfície Multilingüe
Català, castellà, anglès i euskera inclosos de sèrie.

### Control d'Accés Robust
- Claus secretes per a registre
- Bases privades per evitar usos no autoritzats

### Ecosistema en Creixement
- **Arquitectura modular i extensible**: dissenyada per incorporar noves funcionalitats sense afectar el nucli
- Plugins d'ingestió personalitzables per a diferents fonts de dades
- API oberta per a integracions amb tercers
- Actualització contínua sense dependència d'un sol proveïdor d'IA
- Model de dades flexible que evoluciona amb les necessitats educatives

---

## En poques paraules

**LAMB et dóna el control total per construir un "ChatGPT especialitzat" en la teva assignatura, connectar-lo al teu Moodle i mantenir les dades del teu alumnat completament segures.**

---

## 🎓 Recerca i Fonament Acadèmic

**LAMB** està construït sobre recerca acadèmica sòlida i s'adhereix al **[Manifest d'IA Segura en Educació](https://manifesto.safeaieducation.org)** - un marc integral per al desplegament ètic, segur i educativament alineat de la IA.

### 📚 Publicació Acadèmica

Si fas servir LAMB en la teva recerca, si us plau cita el nostre treball:

**"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"**

- **Autors:** Marc Alier, Juanan Pereira, Francisco José García-Peñalvo, Maria Jose Casañ, Jose Cabré
- **Revista:** Computer Standards & Interfaces, Volum 92, Març 2025
- **DOI:** [10.1016/j.csi.2024.103940](https://doi.org/10.1016/j.csi.2024.103940)

### 🏛️ Socis Acadèmics

- **Universidad del País Vasco (UPV/EHU)** - Institució de recerca i soci de desenvolupament
- **Universitat Politècnica de Catalunya (UPC)** - Institució de recerca i soci de desenvolupament
  - Facultat d'Informàtica de Barcelona
  - Institut de Ciències de l'Educació - ICE
  - Departament d'Enginyeria de Serveis i Sistemes d'Informació (ESSI)

### 🙏 Agraïments

Agraïments especials al **Projecte Open WebUI**, **Projecte Tsugi** (Dr. Chuck Severance), la comunitat de **Conferència TEEM**, i **Tknika** Centre de Recerca Aplicada de FP Basca pel seu suport i col·laboració.

---

*Última actualització: Desembre 2025*
