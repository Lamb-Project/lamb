import os
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

# Load environment variables from backend
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "backend" / ".env")

example_inputs = [
    (
        "Nola hasten da zerbitzua bizikleta mekaniko zein elektriko batekin?",
        "PBSC-ko app-aren bidez. Hautatu 'bizikleta bat lortu' aukera mapa nagusiaren barruan, eskaneatu QR kodea, eta itxaron argi horia berde jarri arte zure bizikleta hartu ahal izateko. 3 minutu dituzu bizikletaren egoera egiaztatzeko, eta egoera onean ez dagoela uste baduzu, itzuli dezakezu, eta beste bat hartu, 10 minutu itxaron beharrik gabe. Iturria: https://www.dbizi.eus/eu/ohiko-galderak",
    ),
    (
        "Nola jarri naiteke harremanetan bezeroarentzako arreta zerbitzuarekin intzidentzia edo zalantza bat badut?",
        "Dbiziko bezeroarentzako arreta zerbitzuarekin harremanetan jartzeko, mezu elektroniko bat bidal dezakezu mailto:soporte@dbizi.eus helbidera gertatutakoa azalduz. Larrialdi edo arazo larriagoetan, gomendagarria da 943 060 888 zenbakira deitzea; zenbaki hori aberientzako da. Iturria: https://www.dbizi.eus/eu/ohiko-galderak",
    ),
    (
        "Nola jar naiteke harremanetan Dbizirekin?",
        "WhatsApp/Telegram bidez 648 019 332 zenbakira, telefono bidez 943 060 888ra eta info@dbizi.eus helbidera idatziz jar zaitezke harremanetan. Iturria: https://www.dbizi.eus/eu/kontaktua",
    ),
    (
        "Zer gertatzen da geltoki batean bizikleta itzultzeko lekurik ez dagoenean?",
        "Bizikleta bat utzi nahi baduzu eta geltokia beteta badago, eskatu 10 minutu gehiago appean, kosturik gabe, zugandik hurbilen dagoen eta leku libreak dituen geltoki batera iritsi ahal izateko. Horrez gain, zerbitzuak geltoki+ sistema du honako geltoki hauetan: Añorga, Buenavista, Herrera, Txaparrene, Nornahi, Atarizar, Munto, Andoain, Tranbia, Urbia eta Av. Barcelona. Iturria: https://www.dbizi.eus/eu/ohiko-galderak",
    ),
    (
        "Familia ugarientzako edo enpresentzako deskontuak badaude?",
        "Bai, %20ko (ohikoa) eta %50eko (berezia) deskontuak daude familia ugarientzat, eta deskontuak enpresentzat seigarren kidetik aurrera. Iturria: https://www.dbizi.eus/eu/tarifak",
    ),
    (
        "Zer bonu mota daude, zenbat irauten dute eta nola funtzionatzen dute prezioek?",
        "Abonu arruntak daude (banakakoa eta taldekoa, 12 hilabete) eta noizbehinkakoak (banakakoa, 30 egun). Taldeko abonoa 2-5 pertsonarentzat da. Bonuak ez ditu bidaiak barne hartzen; erabileraren arabera kobratzen da. Iturria: https://www.dbizi.eus/eu/tarifak",
    ),
    (
        "Zer gertatzen da bizikleta itzultzean geltokia beteta badago?",
        "Geltokia beteta badago, sistemak 10 minutu gehigarri ematen dizkizu kosturik gabe bizikleta hurbileneko geltokian uzteko. Iturria: https://www.dbizi.eus/eu/nola-erabili",
    ),
    (
        "Zein eremutan erabil daitezke sistemako bizikletak?",
        "Sistemako bizikletak Donostiako udal mugartean baino ezingo dira erabili, eta sistemaren geltokietan jaso eta itzuli beharko dira. Iturria: https://www.dbizi.eus/eu/ohiko-galderak",
    ),
    (
        "Zein adinetik aurrera erabil daiteke sistema?",
        "Zerbitzua 16 urtetik gorakoentzat dago baimenduta. 16 edo 17 urteko pertsonek legezko tutorearen baimena aurkeztu/erantsi behar dute, alta emateko ezinbesteko baldintza baita. Iturria: https://www.dbizi.eus/eu/ohiko-galderak",
    ),
    (
        "Zein da harremanetarako arreta ordutegia?",
        "Argitaratutako ordutegia astelehenetik ostiralera 8:00etatik 16:00etara da. Iturria: https://www.dbizi.eus/eu/kontaktua",
    ),
    (
        "Nola eman dezaket izena eta nork egin dezake?",
        "Dbiziren webgunean eman dezakezu izena aukeratzen duzun tarifa hautatuz. 16 urtetik gorako eta 18 urtetik beherako pertsonek baimenarekin eman dezakete izena. Iturria: https://www.dbizi.eus/eu/nola-erabili",
    ),
    (
        "Zer da Dbizi?",
        "Dbizi Donostiako Udalaren bizikleta alokairu sistema da. Iturria: https://www.dbizi.eus/eu/ongi-etorri",
    ),
    (
        "Zenbat bizikleta eta geltoki daude?",
        "Webguneak dioenez, 317 bizikleta mekaniko, 317 bizikleta elektriko eta 70 geltoki daude. Iturria: https://www.dbizi.eus/eu/ongi-etorri",
    ),
    (
        "Non kontsulta dezaket geltokien mapa eta bizikleten erabilgarritasuna?",
        "Webguneko 'Mapa eta geltokiak' atalean mapa interaktibo bat ikus dezakezu bizikleten kokapena eta erabilgarritasuna denbora errealean kontsultatzeko. Iturria: https://www.dbizi.eus/eu/mapa-eta-geltokiak",
    ),
    (
        "Zer motatako bizikletak eskaintzen ditu Dbizik eta nola desblokeatzen dira?",
        "Dbizik bizikleta mekanikoak eta elektrikoak eskaintzen ditu; mugikorrean PBSC aplikazioa erabiliz desblokeatzen dira. Iturria: https://www.dbizi.eus/eu/nola-erabili",
    ),
]

DATASET_NAME = "dbizi dataset eus"
DATASET_DESCRIPTION = (
    "Dbiziren maiz egiten diren galderak erantzun erreferentedunekin, laguntzailea ebaluatzeko."
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
