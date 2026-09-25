// Precisely append the workshop namespace to each locale file, preserving the
// original bytes (CRLF, duplicate keys, ordering) — only inserting before the
// final top-level closing brace.
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'src', 'lib', 'locales');

const translations = {
	en: {
		title: 'AI Workshop',
		step1: 'Instructions',
		step2: 'Attach Document',
		step3: 'Connect Knowledge Base',
		step4: 'Add Tool',
		step5: 'Test & Reflect',
		instructionsPlaceholder: 'Write what your assistant should do and how to answer...',
		attachDoc: 'Attach a document',
		connectKb: 'Connect a knowledge base',
		addTool: 'Add a tool',
		calculator: 'Calculator',
		kbQuery: 'Knowledge Base Query',
		sandbox: 'Sandbox Execution (unavailable)',
		testChat: 'Test your assistant',
		reflection: 'Reflect on your design',
		submit: 'Submit workshop',
		next: 'Next',
		back: 'Back',
		observabilityTitle: 'What your assistant received',
		systemInstructions: 'Active instructions',
		retrievedContext: 'Retrieved context',
		finalMessages: 'Messages sent to LLM',
		toolTimeline: 'Tool calls'
	},
	es: {
		title: 'Taller de IA',
		step1: 'Instrucciones',
		step2: 'Adjuntar documento',
		step3: 'Conectar base de conocimiento',
		step4: 'Añadir herramienta',
		step5: 'Probar y reflexionar',
		instructionsPlaceholder: 'Escribe qué debe hacer tu asistente y cómo responder...',
		attachDoc: 'Adjuntar un documento',
		connectKb: 'Conectar una base de conocimiento',
		addTool: 'Añadir una herramienta',
		calculator: 'Calculadora',
		kbQuery: 'Consulta de base de conocimiento',
		sandbox: 'Ejecución en sandbox (no disponible)',
		testChat: 'Prueba tu asistente',
		reflection: 'Reflexiona sobre tu diseño',
		submit: 'Enviar taller',
		next: 'Siguiente',
		back: 'Atrás',
		observabilityTitle: 'Qué recibió tu asistente',
		systemInstructions: 'Instrucciones activas',
		retrievedContext: 'Contexto recuperado',
		finalMessages: 'Mensajes enviados al LLM',
		toolTimeline: 'Llamadas a herramientas'
	},
	ca: {
		title: "Taller d'IA",
		step1: 'Instruccions',
		step2: 'Adjunta un document',
		step3: 'Connecta la base de coneixement',
		step4: 'Afegeix una eina',
		step5: 'Prova i reflexiona',
		instructionsPlaceholder: "Escriu què ha de fer el teu assistent i com respondre...",
		attachDoc: 'Adjunta un document',
		connectKb: 'Connecta una base de coneixement',
		addTool: 'Afegeix una eina',
		calculator: 'Calculadora',
		kbQuery: 'Consulta de base de coneixement',
		sandbox: 'Execució sandbox (no disponible)',
		testChat: 'Prova el teu assistent',
		reflection: 'Reflexiona sobre el teu disseny',
		submit: 'Envia el taller',
		next: 'Següent',
		back: 'Enrere',
		observabilityTitle: "Què ha rebut el teu assistent",
		systemInstructions: 'Instruccions actives',
		retrievedContext: 'Context recuperat',
		finalMessages: "Missatges enviats a l'LLM",
		toolTimeline: 'Crides a eines'
	},
	eu: {
		title: 'IA Tailerra',
		step1: 'Argibideak',
		step2: 'Dokumentua erantsi',
		step3: 'Ezagutza-basea konektatu',
		step4: 'Tresna gehitu',
		step5: 'Probatu eta hausnartu',
		instructionsPlaceholder: 'Idatzi zure laguntzaileak zer egin behar duen eta nola erantzun...',
		attachDoc: 'Dokumentu bat erantsi',
		connectKb: 'Ezagutza-base bat konektatu',
		addTool: 'Tresna bat gehitu',
		calculator: 'Kalkulagailua',
		kbQuery: 'Ezagutza-basearen kontsulta',
		sandbox: 'Sandbox exekuzioa (erabilgarri ez)',
		testChat: 'Probatu zure laguntzailea',
		reflection: 'Hausnartu zure diseinuaz',
		submit: 'Tailerra bidali',
		next: 'Hurrengoa',
		back: 'Atzera',
		observabilityTitle: 'Zure laguntzaileak zer jaso duen',
		systemInstructions: 'Indarrean dauden argibideak',
		retrievedContext: 'Berreskuratutako testuingurua',
		finalMessages: 'LLMra bidalitako mezuak',
		toolTimeline: 'Tresna-deiak'
	}
};

function block(lang) {
	const t = translations[lang];
	const lines = [
		'  "workshop": {'
	];
	for (const [k, v] of Object.entries(t)) {
		lines.push(`    "${k}": ${JSON.stringify(v)}${k === 'toolTimeline' ? '' : ','}`);
	}
	lines.push('  }');
	return lines.join('\r\n');
}

for (const lang of ['en', 'es', 'ca', 'eu']) {
	const file = path.join(dir, `${lang}.json`);
	const original = fs.readFileSync(file, 'utf8');
	// The file ends with:
	//   "libraries": { ... }
	// }            <- top-level close
	// Find the LAST line that is exactly "}" (top-level close).
	const lines = original.split('\r\n');
	let lastTop = -1;
	for (let i = lines.length - 1; i >= 0; i--) {
		if (lines[i] === '}') { lastTop = i; break; }
	}
	if (lastTop === -1) throw new Error(`no top-level close in ${lang}.json`);

	const insertion = block(lang);
	// Close the "libraries" object: the line before top-level "}" should be "  }"
	// — append a comma to it so the new namespace follows it.
	lines[lastTop - 1] = lines[lastTop - 1] + ',';
	const out = [...lines.slice(0, lastTop), insertion, '}', ...lines.slice(lastTop + 1)].join('\r\n');
	fs.writeFileSync(file, out, 'utf8');
	console.log(`updated ${lang}.json (top-level close at line ${lastTop + 1})`);
}