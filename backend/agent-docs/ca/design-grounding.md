<a id="choose-grounding"></a>
# Com triar les fonts de l’assistent

Comença pels materials i per la tasca d’aprenentatge. Si l’alumnat necessita pràctica general i les respostes no han de seguir una font concreta, pot ser suficient un assistent sense fonts externes. Per a un únic document breu i estable que càpiga al context del model, incorporar el fitxer sencer sol ser més fàcil d’inspeccionar i mantenir que una col·lecció amb cerca. Al frontend, l’educador ha de seleccionar i carregar el fitxer amb la interfície.

Per a diversos documents, materials que canvien o contingut massa extens per incloure’l sencer, considera una base de coneixement. La recuperació pot ometre fragments rellevants: prepara preguntes que comprovin la cobertura i inspecciona el context construït abans de confiar en les respostes.

La recuperació que té en compte el context de la conversa pot ser útil quan les preguntes de seguiment depenen dels torns anteriors. Afegeix una reescriptura de la consulta, temps de resposta i una altra possible font d’error. Compara els mateixos casos de seguiment amb una recuperació més simple abans de triar-la. Augmentar top-k és un experiment, no una solució garantida. Proposa només alternatives presents al mapa de capacitats de la instal·lació. Pregunta per la mida, l’estabilitat dels materials i les necessitats de seguiment; esmentar un document no justifica crear una base de coneixement.
