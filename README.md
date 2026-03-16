# LAMB - Learning Assistants Manager and Builder

<div align="center">
  <img src="static/lamb_1.png" alt="LAMB Logo" width="300">
  
  **Create AI assistants for education integrated in your Learning Management System**

  [![Website](https://img.shields.io/badge/Website-lamb--project.org-blue)](http://www.lamb-project.org)
  [![License](https://img.shields.io/badge/license-GPL%20v3-blue.svg)](LICENSE)
  [![Safe AI in Education](https://img.shields.io/badge/Safe_AI_Education-Manifesto-green)](https://manifesto.safeaieducation.org)
  [![GitHub](https://img.shields.io/badge/GitHub-Lamb--Project-black)](https://github.com/Lamb-Project/lamb)
</div>

## 📋 Project Description

**LAMB** (Learning Assistants Manager and Builder) is an open-source web platform that enables educators to design, test, and publish AI-based learning assistants into your Learning Management System (LMS like Moodle) without writing any code. It functions as a visual "teaching chatbot builder" that seamlessly combines large language models (GPT-4, Mistral, local models) with your own educational materials.

Developed by Marc Alier and Juanan Pereira, professors and researchers at the Universitat Politècnica de Catalunya (UPC) and Universidad del País Vasco (UPV/EHU), LAMB addresses the critical need for educational AI tools that maintain student privacy while providing powerful, context-aware learning support.

## 🎯 Key Features

### 🎓 **Specialized Subject Tutors**
Design assistants that stay grounded on your chosen subject area, ensuring responses are always educationally appropriate and contextually relevant.

### 📚 **Intelligent Knowledge Ingestion**
Upload educational materials (PDF, Word, Markdown) and LAMB automatically processes them with:
- Flexible data model that preserves context and relationships
- Semantic embeddings optimized for educational search
- Custom metadata support for each document
- Adaptive processing for different content structures
- RAG (Retrieval Augmented Generation) integration

### 🔒 **Privacy-First Architecture**
- The students will access the Learning Assitants as Learning Activities within the LMS Course
- No user information is shared with AI model providers
- Can run on open source and open weights models running on your compute
- Secure, self-hosted solution

### 🔌 **LTI Integration**
Seamlessly integrate with Moodle and other Learning Management Systems through LTI (Learning Tools Interoperability) standard - publish your assistant as an external tool with just a few clicks.

### 🤖 **Multi-Model Support**
- Works with OpenAI API compatible models
- Ollama inetgration
- One-click model switching
- Model-agnostic architecture

### 🔍 **Advanced Testing & Debugging**
- Debug mode showing complete prompts
- Citation tracking with source references


### 🌍 **Multilingual Interface**
Built-in support for Basque, Catalan, Spanish, and English, with easy extensibility for additional languages.  

### 💾 **Portability & Versioning**
- Export/import assistants in JSON format


## 👥 Target Audience

LAMB is designed for:

- **📖 Teachers and Trainers**: Create virtual assistants focused on specific curricula without technical expertise
- **🏫 Educational Institutions**: Integrate AI into existing LMS platforms while maintaining data sovereignty
- **💡 Innovation Teams**: Experiment with different LLMs through a unified management interface
- **🔬 Researchers**: Study AI in education with complete control over the learning environment

## 🏗️ Architecture Overview

LAMB features a modular, extensible architecture:

- **Backend**: FastAPI-based server handling assistant management, LTI integration, and model orchestration
- **Frontend**: Modern Svelte 5 application providing intuitive UI for assistant creation and management
- **Knowledge Base Server**: Dedicated service for document ingestion and vector search
- **Integration Layer**: Bridges with Open WebUI for model management  https://github.com/open-webui/open-webui

## 🚀 Installation

### Recommended: Docker Installation

For the easiest setup experience, we recommend using Docker Compose to run all LAMB services:

📘 **[Docker Installation Guide](Documentation/deployment.md)** - One-command deployment with all services configured

### Alternative: Manual Installation

For development or custom deployments:

📘 **[Complete Installation Guide](Documentation/installationguide.md)** - Step-by-step manual setup for all components

### Quick Overview

LAMB requires four main services:
1. **Open WebUI Server** (port 8080) - Model management interface
2. **LAMB Knowledge Base Server** (port 9090) - Document processing and vector search
3. **LAMB Backend Server** (port 9099) - Core API and business logic
4. **Frontend Application** (port 5173) - Web interface

## 📖 Documentation

### 📚 For End Users
Visit our [official website](http://www.lamb-project.org) for:
- **User guides and tutorials**
- **Feature documentation**
- **Educational resources**
- **Community support**

### 📖 Developer Documentation
Comprehensive documentation is available in the `/Documentation` directory:

- [Backend Architecture](Documentation/small-context/backend_architecture.md)
- [Frontend Development Guide](Documentation/small-context/frontend_architecture.md)
- [Knowledge Base Integration](Documentation/attic/kb-server-integration.md)
- [Multi-Organization Setup](Documentation/attic/multi_org.md)
- [Database Schema](Documentation/LAMB_DATABASE_SCHEMA.md)
- [Final Setup Guide](Documentation/slop-docs/final-setup.md)

## 🗂️ Project Structure

```
lamb/
├── backend/               # FastAPI backend server
│   ├── lamb/             # Core LAMB functionality
│   ├── creator_interface/# Assistant creation interface
│   └── utils/            # Utility functions
├── frontend/             # Svelte 5 frontend
│   └── svelte-app/      # Main web application
├── lamb-kb-server/       # Knowledge base server
├── Documentation/        # Project documentation
└── docker-compose.yaml   # Container orchestration
```

## 🤝 Contributing

We welcome contributions! LAMB is an open-source project that thrives on community involvement. Areas where you can help:

- 📝 Documentation improvements
- 🌍 Translations to new languages
- 🔌 New LMS integrations
- 🤖 Additional model support
- 🐛 Bug fixes and testing

Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📜 License

LAMB is licensed under the GNU General Public License v3.0 (GPL v3).

Copyright (c) 2024-2025 Marc Alier (UPC) @granludo & Juanan Pereira (UPV/EHU) @juananpe

See [LICENSE](LICENSE) for full details.

## 📚 Publications & Research

### Academic Publications on LAMB

If you use LAMB in your research, please cite our work:

**LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems**
- **Authors**: Marc Alier, Juanan Pereira, Francisco José García-Peñalvo, Maria Jose Casañ, Jose Cabré
- **Journal**: Computer Standards & Interfaces
- **Volume**: 92
- **Pages**: 103940
- **Publication Date**: March 2025
- **DOI**: [10.1016/j.csi.2024.103940](https://doi.org/10.1016/j.csi.2024.103940)
- **Direct Link**: [ScienceDirect Article](https://www.sciencedirect.com/science/article/pii/S0920548924001090)

```bibtex
@article{ALIER2024103940,
title = {LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems},
journal = {Computer Standards \& Interfaces},
volume = {92},
pages = {103940},
year = {2025},
issn = {0920-5489},
doi = {https://doi.org/10.1016/j.csi.2024.103940},
url = {https://www.sciencedirect.com/science/article/pii/S0920548924001090},
author = {Marc Alier and Juanan Pereira and Francisco Jos{\'e} Garc{\'i}a-Pe{\~n}alvo and Maria Jose Casan and Jose Cabr{\'e}}
}
```

### Research Collaborators

We acknowledge the valuable contributions and research collaboration from the authors and researchers who have worked on LAMB:

#### Project Leaders
- **Juanan Pereira** (Universidad del País Vasco, UPV/EHU) - Co-Lead & Principal Researcher
- **Marc Alier** (Universitat Politècnica de Catalunya, UPC) - Co-Lead & Principal Researcher

#### Senior Researchers & Academic Collaborators
- **Francisco José García-Peñalvo** - Advisor and Senior Researcher
- **Maria Jose Casañ** (Universitat Politècnica de Catalunya, UPC) - Research Contributor & Developer
- **Ariadna Maria LLorens** (Universitat Politècnica de Catalunya, UPC) - Research Contributor
- **Jose Cabré** (Universitat Politècnica de Catalunya, UPC) - Research Contributor 
- **David Lopez Alvarez** (Universitat Politècnica de Catalunya, UPC) - Research Contributor
  

## 🙏 Acknowledgments

### Academic & Institutional Partners
- **Universidad del País Vasco (UPV/EHU)** - Research institution and development partner
- **Universitat Politècnica de Catalunya (UPC)** - Research institution and development partner
  - **Barcelona School of Informatics** (https://fib.upc.edu)
  - **Institut de Ciències de l'Educació - ICE** (https://ice.upc.edu)
  - **Department of Service and Information System Engineering. ESSI** (http://essi.upc.edu)
- **Universidad de Salamanca** - Grial Research Group 

### Open Source Dependencies
- **Open WebUI Project** - (https://github.com/open-webui/) Advanced chatbot web interface integration, and a lot of design descisions borrowed from the openwebui pipelines project. 
- **TSugi Project** (https://www.tsugi.org) Used in early Lamb implementations for LTI provider support. Many thanks to Dr. Chuck (Charles Severance) for his support and inspiration. 


### Research & Educational Community
- **TEEM Conference** - (https://teemconference.eu) The TEEM conference has a vibrant community of researchers working on multidisciplinary fields connected to technology and education. The LAMB project was born on a coffe break conversation after the "Managing Generative AI in educational settings", we lost control of it :-) .   
- **Teaching Community** - Early adopters and beta testers:
  - https://tknika.eus/en/ Basque VET Applied Research Centre 
- **All Contributors** - For their dedication to improving education through technology

### Funding projects directly or indirectly contributing to the project

- Universitat Politecnica de Cataluya. Galaxia d'Aprenentatge projecte PROPER, Factulat d'Informatica de Barcelona (2024-2025). 
- Departament de Recerca i Universitats de la Generalitat de Catalunya through the 2021 SGR 01412 research groups award (2021-2025). 
- Universidad del País Vasco/Euskal Herriko Unibertsitatea through the contract GIU21/037 under the program “Convocatoria para la Concesión de Ayudas a los Grupos de Investigación en la Universidad del País Vasco/Euskal Herriko Unibertsitatea (2021)


## 🛡️ Safe AI in Education Manifesto

LAMB proudly adheres to the **[Safe AI in Education Manifesto](https://manifesto.safeaieducation.org)** - a comprehensive framework for ethical, secure, and educationally-aligned AI deployment.

### 📋 Manifesto TLDR

The Safe AI in Education Manifesto outlines 7 core principles for responsible AI use in education:

1. **Human Oversight** - AI complements, never replaces, human educators
2. **Privacy Protection** - Student data confidentiality and security
3. **Educational Alignment** - AI supports institutional strategies and learning objectives
4. **Didactic Integration** - Seamless integration with teaching methodologies
5. **Accuracy & Explainability** - Reliable, source-attributed information
6. **Transparent Interfaces** - Clear communication of AI limitations and capabilities
7. **Ethical Training** - Models trained with educational ethics and transparency

### 🎯 How LAMB Implements These Principles

**LAMB is designed from the ground up to embody these principles:**

- **🔍 Human Oversight**: All assistants are created and managed by educators with full control over behavior and content
- **🔒 Privacy-First**: Self-hosted architecture keeps all student data within institutional control
- **📚 Educational Focus**: Specialized subject tutors stay grounded in educational content and objectives
- **🧠 Didactic Integration**: Seamless LTI integration with Moodle and other LMS platforms
- **📖 Source Attribution**: Automatic citations and references to source materials
- **💬 Transparent Communication**: Clear assistant responses with educational context and limitations
- **🎓 Ethical Foundation**: Open-source, academically-developed with research collaboration

### 🤝 Our Commitment

As signatories to the manifesto, LAMB's core team members are committed to advancing ethical AI in education. LAMB represents a practical implementation of manifesto principles in action.

## 📧 Contact
- **Project Leads**: Marc Alier (UPC), Juanan Pereira (UPV/EHU) 
- **Research**: Academic collaborations and research partnerships
- **GitHub**: [https://github.com/Lamb-Project/lamb](https://github.com/Lamb-Project/lamb)
- **Issues**: [GitHub Issues](https://github.com/Lamb-Project/lamb/issues)
- **Website**: [http://www.lamb-project.org](http://www.lamb-project.org)

---

**LAMB** - Empowering educators to create intelligent, privacy-respecting AI assistants for enhanced learning experiences.

