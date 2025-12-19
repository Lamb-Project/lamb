# LAMB - Learning Assistants Manager and Builder

**Web platform to design, train and publish AI-based learning assistants without writing code**

---

## What is LAMB?

**LAMB** is an open source web platform that allows you to **design, train and publish AI-based learning assistants** in a visual and intuitive way. It works as a "teaching chatbot builder" that combines language models (GPT-4, Mistral, local models) with your own educational materials.

**LAMB** is an open source project developed by Marc Alier and Juanan Pereira, professors and researchers at the Universitat Politècnica de Catalunya (UPC) and Universidad del País Vasco (UPV/EHU).

- **Website:** [http://www.lamb-project.org](http://www.lamb-project.org)
- **GitHub:** [https://github.com/Lamb-Project/lamb](https://github.com/Lamb-Project/lamb)
- **License:** GPL v3
- **Manifesto:** [Safe AI Education](https://manifesto.safeaieducation.org)

---

## Main Features

### 🎓 Specialized Subject Tutors
Design assistants that only respond about the subject you choose, always staying within the appropriate educational context.

### 📚 Intelligent Knowledge Ingestion
Upload documents (PDF, Word, Markdown) and LAMB processes them automatically with a **flexible data model** that:
- Extracts and structures content while preserving context and relationships
- Creates semantic embeddings optimized for educational search
- Allows custom metadata for each document
- Adapts to different formats and content structures
- Feeds the model through RAG (Retrieval Augmented Generation)

### 🔍 Advanced Testing and Debugging
"Debug" mode that shows the complete prompt to understand exactly what is sent to the model, facilitating response optimization.

### 🎯 LTI Integration with Moodle
Publish the assistant as an external LTI tool and embed it in your Moodle in a couple of clicks.

### 🔒 Guaranteed Privacy
Students interact within LAMB; their data is not shared with external AI model providers.

---

## Who is LAMB for?

- **📖 Teachers and trainers** who need a virtual assistant focused on their specific curriculum
- **🏫 Educational centers** that use Moodle or other LMS and need to integrate AI without exposing student data
- **💡 Innovation teams** experimenting with different LLMs and need a unified management panel

---

## Key Functionalities

### Unlimited Assistants
Each with their own instructions, tone and personalized limits.

### Flexible Knowledge Bases
- **Adaptable data model**: flexible architecture that allows different types of content and structures
- Support for PDF, DOCX, Markdown (more formats coming soon)
- Public or private bases according to needs
- Vector embeddings system for semantic search
- Connectors in development for external sources (Google Drive, YouTube, APIs)

### Multiple AI Models
- OpenAI GPT-4o
- Mistral
- Local models
- One-click model switching

### Automatic Citations
The assistant provides responses with references to the source documents used.

### Total Portability
- Export/import assistants in JSON format
- Easy versioning and sharing

### Multilingual Interface
Catalan, Spanish, English and Basque included as standard.

### Robust Access Control
- Secret keys for registration
- Private bases to prevent unauthorized use

### Growing Ecosystem
- **Modular and extensible architecture**: designed to incorporate new features without affecting the core
- Customizable ingestion plugins for different data sources
- Open API for third-party integrations
- Continuous updates without dependence on a single AI provider
- Flexible data model that evolves with educational needs

---

## In short

**LAMB gives you total control to build a "specialized ChatGPT" for your subject, connect it to your Moodle and keep your students' data completely secure.**

---

## 🎓 Research & Academic Foundation

**LAMB** is built on solid academic research and adheres to the **[Safe AI in Education Manifesto](https://manifesto.safeaieducation.org)** - a comprehensive framework for ethical, secure, and educationally-aligned AI deployment.

### 📚 Academic Publication

If you use LAMB in your research, please cite our work:

**"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"**

- **Authors:** Marc Alier, Juanan Pereira, Francisco José García-Peñalvo, Maria Jose Casañ, Jose Cabré
- **Journal:** Computer Standards & Interfaces, Volume 92, March 2025
- **DOI:** [10.1016/j.csi.2024.103940](https://doi.org/10.1016/j.csi.2024.103940)

### 🏛️ Academic Partners

- **Universidad del País Vasco (UPV/EHU)** - Research institution and development partner
- **Universitat Politècnica de Catalunya (UPC)** - Research institution and development partner
  - Barcelona School of Informatics
  - Institut de Ciències de l'Educació - ICE
  - Department of Service and Information System Engineering (ESSI)

### 🙏 Acknowledgments

Special thanks to the **Open WebUI Project**, **Tsugi Project** (Dr. Chuck Severance), **TEEM Conference** community, and **Tknika** Basque VET Applied Research Centre for their support and collaboration.

---

*Last updated: December 2025*
