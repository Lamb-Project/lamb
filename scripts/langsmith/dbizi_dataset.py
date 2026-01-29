import os
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

# Load environment variables from backend
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "backend" / ".env")

example_inputs = [
    (
        "¿Cómo inicio el servicio con una bicicleta tanto mecánica como eléctrica?",
        "Mediante la app de PBSC. Selecciona la opción 'obtener una bicicleta' dentro del mapa principal, escanea el código QR y espera a que la luz amarilla se vuelva verde para poder retirar tu bicicleta. Fuente: https://www.dbizi.eus/es/preguntas-frecuentes",
    ),
    (
        "¿Cómo contacto con atención al cliente si tengo una incidencia o duda?",
        "Para contactar con atención al cliente de Dbizi en caso de tener una incidencia o duda, puedes enviar un correo electrónico a mailto:soporte@dbizi.eus explicando lo que te ha ocurrido. Si se trata de una emergencia o de un problema más urgente, es recomendable llamar al 943 060 888, que está dedicado a averías. Fuente: https://www.dbizi.eus/es/preguntas-frecuentes",
    ),
    (
        "¿Cómo puedo contactar con Dbizi?",
        "Puedes contactar por WhatsApp/Telegram al 648 019 332, teléfono 943 060 888 y correo info@dbizi.eus. Fuente: https://www.dbizi.eus/es/contacto",
    ),
    (
        "¿Qué pasa cuando no hay espacio disponible en una estación para devolver la bicicleta?",
        "Si quieres dejar una bicicleta y la estación está llena, solicita la ampliación de 10 minutos adicionales sin coste en la app para poder llegar a la estación más próxima con espacio. Fuente: https://www.dbizi.eus/es/preguntas-frecuentes",
    ),
    (
        "¿Existen descuentos para familias numerosas o empresas?",
        "Sí, hay descuentos del 20% (normal) y 50% (especial) para familias numerosas, y descuentos para empresas a partir del sexto miembro. Fuente: https://www.dbizi.eus/es/tarifas",
    ),
    (
        "¿Qué tipos de abonos existen, cuál es su duración y cómo funcionan los precios?",
        "Hay abonos ordinarios (individual y grupal, 12 meses) y ocasionales (individual, 30 días). El abono grupal es para 2-5 personas. El abono no incluye viajes, se cobra por uso. Fuente: https://www.dbizi.eus/es/tarifas",
    ),
    (
        "¿Qué ocurre si la estación está llena al devolver la bicicleta?",
        "Si la estación está llena, el sistema te otorga 10 minutos extra para devolver la bicicleta en la estación más cercana sin coste adicional. Fuente: https://www.dbizi.eus/es/como-funciona",
    ),
    (
        "¿En qué ámbito se pueden utilizar las bicicletas del sistema?",
        "Las bicicletas del sistema podrán utilizarse única y exclusivamente dentro del término municipal de San Sebastián y deberán ser recogidas y devueltas en las estaciones del sistema. Fuente: https://www.dbizi.eus/es/preguntas-frecuentes",
    ),
    (
        "¿A partir de qué edad está permitida la utilización del sistema?",
        "El servicio está permitido a mayores de 16 años. Las personas de 16 o 17 años han de aportar la autorización del tutor legal como requisito indispensable para darse de alta. Fuente: https://www.dbizi.eus/es/preguntas-frecuentes",
    ),
    (
        "¿Cuál es el horario de atención para contactos?",
        "El horario publicado es Lunes-Viernes: 8h-16h. Fuente: https://www.dbizi.eus/es/contacto",
    ),
    (
        "¿Cómo puedo inscribirme y quién puede hacerlo?",
        "Puedes inscribirte en la web de Dbizi eligiendo la tarifa que prefieras. Los mayores de 16 y menores de 18 años pueden inscribirse con autorización. Fuente: https://www.dbizi.eus/es/como-funciona",
    ),
    (
        "¿Qué es Dbizi?",
        "Dbizi es el sistema de alquiler de bicicletas del Ayuntamiento de San Sebastián (Donostia). Fuente: https://www.dbizi.eus/es/bienvenido",
    ),
    (
        "¿Cuántas bicicletas y estaciones hay?",
        "Según la web, hay 317 bicicletas mecánicas, 317 bicicletas eléctricas y 70 estaciones. Fuente: https://www.dbizi.eus/es/bienvenido",
    ),
    (
        "¿Dónde puedo consultar el mapa de estaciones y la disponibilidad de bicicletas?",
        "En la sección 'Plano y estaciones' de la web puedes ver un mapa interactivo con la ubicación y disponibilidad de bicicletas en tiempo real. Fuente: https://www.dbizi.eus/es/plano-y-estaciones",
    ),
    (
        "¿Qué tipos de bicicletas ofrece Dbizi y cómo se desbloquean?",
        "Dbizi ofrece bicicletas mecánicas y eléctricas, que se desbloquean utilizando la app PBSC en tu móvil. Fuente: https://www.dbizi.eus/es/como-funciona",
    ),
]


DATASET_NAME = "dbizi dataset"

DATASET_DESCRIPTION = (
    "FAQ de Dbizi con respuestas de referencia para evaluar al asistente."
)


def get_or_create_dataset(client: Client):
    """Retrieves the dataset by name or creates it if it doesn't exist."""
    existing = list(client.list_datasets(dataset_name=DATASET_NAME))

    if existing:
        dataset = existing[0]
        print(f"ℹ️ Existing dataset '{DATASET_NAME}' -> {dataset.id}")
        return dataset

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME, description=DATASET_DESCRIPTION
    )
    print(f"✅ Dataset created '{DATASET_NAME}' -> {dataset.id}")
    return dataset


def main() -> None:
    client = Client()

    dataset = get_or_create_dataset(client)

    # Build idempotent examples based on the question
    existing_questions = {
        example.inputs.get("question")
        for example in client.list_examples(dataset_id=dataset.id)
        if isinstance(example.inputs, dict)
    }

    examples = [
        {
            "inputs": {"question": input_prompt},
            "outputs": {"answer": output_answer}, 
        }
        for input_prompt, output_answer in example_inputs
        if input_prompt not in existing_questions
    ]

    if not examples:
        print(
            "ℹ️ The dataset already contains all questions, no new examples were added."
        )
        return

    client.create_examples(
        dataset_id=dataset.id,
        examples=examples,
    )

    print(f"✅ Done: created {len(examples)} examples in dataset {dataset.id}.")


if __name__ == "__main__":
    main()
