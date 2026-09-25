// Opening an empty conversation is not a request to start a workflow.
const greetings = {
    en: "Hi! I’m LAMB AGENT. I can help you create and improve assistants, work with knowledge bases and rubrics, run tests, and find your way around LAMB. What would you like to do?",
    es: '¡Hola! Soy LAMB AGENT. Puedo ayudarte a crear y mejorar asistentes, trabajar con bases de conocimiento y rúbricas, ejecutar pruebas y orientarte en LAMB. ¿Qué quieres hacer?',
    ca: 'Hola! Soc LAMB AGENT. Et puc ajudar a crear i millorar assistents, treballar amb bases de coneixement i rúbriques, executar proves i orientar-te per LAMB. Què vols fer?',
    eu: 'Kaixo! LAMB AGENT naiz. Laguntzaileak sortzen eta hobetzen, ezagutza-baseekin eta errubrikekin lan egiten, probak egiten eta LAMB erabiltzen lagun diezazuket. Zer egin nahi duzu?'
};

export function agentWelcome(language) {
    return greetings[language] || greetings.en;
}
