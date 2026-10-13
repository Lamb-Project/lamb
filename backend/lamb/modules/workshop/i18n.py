"""Workshop localization — consent copy and locale resolution.

The consent page is rendered **server-side** by Jinja (``templates/consent.html``),
so it cannot use the SPA's ``svelte-i18n`` bundle: the strings live here instead.

Locale resolution follows the same chain as the wizard (decision C6):

    ``?lang=`` (from the LTI ``launch_presentation_locale`` claim)
      → ``activity['locale']`` (reserved for an activity-level override)
      → ``Accept-Language``
      → ``en``

``Accept-Language`` entries with ``q=0`` are explicit refusals and are skipped.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = ("en", "es", "ca", "eu")
DEFAULT_LOCALE = "en"

# Version of the consent notice. Bump it whenever the copy below changes in a
# way that materially changes what the student is told — the v2 notice added
# model-based evaluation — so returning students can be asked again (C8/C20).
CONSENT_VERSION = "2026-10"

# ─────────────────────────────────────────────────────────────────────────────
# Consent page copy (all four supported languages)
#
# The page must disclose the *three* things the workshop does with student
# work — build an assistant, run test conversations, and send the submission
# to a model for formative feedback — plus how long the data lives and how it
# is deleted. The model *class* (local vs external) is not written here: it is
# resolved at render time from the real completion config (decision C17), so
# the page can never claim a model setup the deployment does not have.
# ─────────────────────────────────────────────────────────────────────────────

CONSENT_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "lang": "en",
        "title": "Before you start",
        "intro": (
            "This activity asks you to build a small AI assistant. "
            "Please read how your work is used before you continue."
        ),
        "purposeHeading": "What this activity does with your work",
        "purposeBuild": (
            "<strong>You build an assistant.</strong> The instructions you write "
            "and the document you upload are stored so the assistant can use them."
        ),
        "purposeTest": (
            "<strong>You test it in a chat.</strong> Your messages and the "
            "assistant's answers are stored with your activity so you can review "
            "them and your teacher can see your progress."
        ),
        "purposeEvaluate": (
            "<strong>Your submission is reviewed by a model.</strong> When you "
            "submit, the conversation, your reflection and your design decisions "
            "are sent to a language model that produces formative feedback. "
            "The feedback is a suggestion — your teacher decides the final grade."
        ),
        "modelHeading": "Which model sees your work",
        "retentionHeading": "How long it is kept",
        "retentionBody": (
            "Your assistant and your submitted work stay available to you and "
            "your teacher. Your uploaded document and your conversation can be "
            "deleted automatically after a retention period configured by your "
            "school; your teacher can also delete your data at any time."
        ),
        "privacyHeading": "Your choices",
        "privacyBody": (
            "You can take part without uploading a personal document — any "
            "course material works. If you would rather not take part, tell your "
            "teacher instead of continuing."
        ),
        "modelLocal": "A model running on your school's own infrastructure.",
        "modelExternal": (
            "A model provided by an external service ({model}). The text of your "
            "conversation and submission is sent to that provider."
        ),
        "modelUnknown": (
            "The model for this activity is not configured yet, so nothing is "
            "sent anywhere until your teacher finishes setting it up."
        ),
        "retentionDays": "Retention period configured by your school: {days} days.",
        "consentButton": "I understand — start the activity",
        "declineHint": "If you do not agree, close this page and tell your teacher.",
    },
    "es": {
        "lang": "es",
        "title": "Antes de empezar",
        "intro": (
            "Esta actividad te pide construir un pequeño asistente de IA. "
            "Lee cómo se utiliza tu trabajo antes de continuar."
        ),
        "purposeHeading": "Qué hace esta actividad con tu trabajo",
        "purposeBuild": (
            "<strong>Construyes un asistente.</strong> Las instrucciones que "
            "escribes y el documento que subes se guardan para que el asistente "
            "pueda usarlos."
        ),
        "purposeTest": (
            "<strong>Lo pruebas en un chat.</strong> Tus mensajes y las "
            "respuestas del asistente se guardan con tu actividad para que puedas "
            "revisarlos y tu profesor pueda ver tu progreso."
        ),
        "purposeEvaluate": (
            "<strong>Un modelo revisa tu entrega.</strong> Al enviar, la "
            "conversación, tu reflexión y tus decisiones de diseño se envían a un "
            "modelo de lenguaje que genera una retroalimentación formativa. Es "
            "una sugerencia: la nota final la decide tu profesor."
        ),
        "modelHeading": "Qué modelo ve tu trabajo",
        "retentionHeading": "Cuánto tiempo se conserva",
        "retentionBody": (
            "Tu asistente y tu entrega siguen disponibles para ti y para tu "
            "profesor. El documento que subes y tu conversación pueden borrarse "
            "automáticamente tras un periodo de conservación configurado por tu "
            "centro; tu profesor también puede borrar tus datos en cualquier "
            "momento."
        ),
        "privacyHeading": "Tú decides",
        "privacyBody": (
            "Puedes participar sin subir un documento personal: sirve cualquier "
            "material del curso. Si prefieres no participar, díselo a tu profesor "
            "en lugar de continuar."
        ),
        "modelLocal": "Un modelo que se ejecuta en la infraestructura de tu centro.",
        "modelExternal": (
            "Un modelo proporcionado por un servicio externo ({model}). El texto "
            "de tu conversación y de tu entrega se envía a ese proveedor."
        ),
        "modelUnknown": (
            "El modelo de esta actividad aún no está configurado, así que no se "
            "envía nada a ningún sitio hasta que tu profesor lo termine de "
            "configurar."
        ),
        "retentionDays": "Periodo de conservación configurado por tu centro: {days} días.",
        "consentButton": "Lo entiendo — empezar la actividad",
        "declineHint": "Si no estás de acuerdo, cierra esta página y avisa a tu profesor.",
    },
    "ca": {
        "lang": "ca",
        "title": "Abans de començar",
        "intro": (
            "Aquesta activitat et demana construir un petit assistent d'IA. "
            "Llegeix com s'utilitza la teva feina abans de continuar."
        ),
        "purposeHeading": "Què fa aquesta activitat amb la teva feina",
        "purposeBuild": (
            "<strong>Construeixes un assistent.</strong> Les instruccions que "
            "escrius i el document que puges es guarden perquè l'assistent els "
            "pugui fer servir."
        ),
        "purposeTest": (
            "<strong>El proves en un xat.</strong> Els teus missatges i les "
            "respostes de l'assistent es guarden amb la teva activitat perquè els "
            "puguis revisar i el teu professor pugui veure el teu progrés."
        ),
        "purposeEvaluate": (
            "<strong>Un model revisa el teu lliurament.</strong> Quan l'envies, la "
            "conversa, la teva reflexió i les teves decisions de disseny s'envien "
            "a un model de llenguatge que genera retroacció formativa. És un "
            "suggeriment: la nota final la decideix el teu professor."
        ),
        "modelHeading": "Quin model veu la teva feina",
        "retentionHeading": "Quant de temps es conserva",
        "retentionBody": (
            "El teu assistent i el teu lliurament continuen disponibles per a tu "
            "i per al teu professor. El document que puges i la teva conversa es "
            "poden esborrar automàticament després d'un període de conservació "
            "configurat pel teu centre; el teu professor també pot esborrar les "
            "teves dades en qualsevol moment."
        ),
        "privacyHeading": "Tu decideixes",
        "privacyBody": (
            "Pots participar sense pujar cap document personal: qualsevol "
            "material del curs serveix. Si prefereixes no participar, digues-ho "
            "al teu professor en lloc de continuar."
        ),
        "modelLocal": "Un model que s'executa a la infraestructura del teu centre.",
        "modelExternal": (
            "Un model proporcionat per un servei extern ({model}). El text de la "
            "teva conversa i del teu lliurament s'envia a aquest proveïdor."
        ),
        "modelUnknown": (
            "El model d'aquesta activitat encara no està configurat, així que no "
            "s'envia res enlloc fins que el teu professor l'acabi de configurar."
        ),
        "retentionDays": "Període de conservació configurat pel teu centre: {days} dies.",
        "consentButton": "Ho entenc — començar l'activitat",
        "declineHint": "Si no hi estàs d'acord, tanca aquesta pàgina i avisa el teu professor.",
    },
    "eu": {
        "lang": "eu",
        "title": "Hasi aurretik",
        "intro": (
            "Jarduera honek IA laguntzaile txiki bat eraikitzeko eskatzen dizu. "
            "Irakurri zure lana nola erabiltzen den jarraitu aurretik."
        ),
        "purposeHeading": "Zer egiten du jarduera honek zure lanarekin",
        "purposeBuild": (
            "<strong>Laguntzaile bat eraikitzen duzu.</strong> Idazten dituzun "
            "argibideak eta igotzen duzun dokumentua gordetzen dira laguntzaileak "
            "erabili ahal izan ditzan."
        ),
        "purposeTest": (
            "<strong>Txat batean probatzen duzu.</strong> Zure mezuak eta "
            "laguntzailearen erantzunak zure jarduerarekin gordetzen dira, berrikusi "
            "ahal izateko eta zure irakasleak zure aurrerapena ikusi ahal izateko."
        ),
        "purposeEvaluate": (
            "<strong>Modelo batek zure lana berrikusten du.</strong> Bidaltzen "
            "duzunean, elkarrizketa, zure gogoeta eta diseinu-erabakiak hizkuntza "
            "eredu batera bidaltzen dira, feedback formatiboa sortzeko. Iradokizun "
            "bat da: azken kalifikazioa zure irakasleak erabakitzen du."
        ),
        "modelHeading": "Zein modelok ikusten du zure lana",
        "retentionHeading": "Zenbat denboraz gordetzen da",
        "retentionBody": (
            "Zure laguntzailea eta bidalitako lana zure eta zure irakaslearen "
            "eskura egongo dira. Igotzen duzun dokumentua eta zure elkarrizketa "
            "automatikoki ezaba daitezke zure ikastetxeak ezarritako gordetze-"
            "epearen ondoren; zure irakasleak ere edozein unetan ezaba ditzake "
            "zure datuak."
        ),
        "privacyHeading": "Zuk erabakitzen duzu",
        "privacyBody": (
            "Parte har dezakezu dokumentu pertsonalik igo gabe: ikastaroko "
            "edozein material balio du. Parte hartu nahi ez baduzu, esan zure "
            "irakasleari jarraitu beharrean."
        ),
        "modelLocal": "Zure ikastetxearen azpiegitura propioan exekutatzen den modeloa.",
        "modelExternal": (
            "Kanpoko zerbitzu batek emandako modeloa ({model}). Zure "
            "elkarrizketaren eta bidalitako lanaren testua hornitzaile horri "
            "bidaltzen zaio."
        ),
        "modelUnknown": (
            "Jarduera honetako modeloa oraindik ez dago konfiguratuta, beraz ez da "
            "ezer inora bidaltzen zure irakasleak konfiguratu arte."
        ),
        "retentionDays": "Zure ikastetxeak ezarritako gordetze-epea: {days} egun.",
        "consentButton": "Ulertzen dut — hasi jarduera",
        "declineHint": "Ados ez bazaude, itxi orri hau eta esan zure irakasleari.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# "The teacher goes first" waiting page (decision C13)
#
# When an organization requires the teacher to take the workshop before opening
# it to a class, students who launch early must be told what is happening. A
# bare error page would read as "the activity is broken"; this says who is
# doing what and that they should try again shortly.
# ─────────────────────────────────────────────────────────────────────────────

PILOT_REQUIRED_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Not open yet",
        "body": (
            "Your teacher is completing this activity themselves first, so that "
            "they can guide you through it. Please try again in a few minutes."
        ),
        "hint": "If it is still closed later, ask your teacher to open the activity.",
    },
    "es": {
        "title": "Todavía no está abierta",
        "body": (
            "Tu profesor está completando antes esta actividad para poder "
            "guiarte. Vuelve a intentarlo dentro de unos minutos."
        ),
        "hint": "Si sigue cerrada más tarde, pídele a tu profesor que abra la actividad.",
    },
    "ca": {
        "title": "Encara no està oberta",
        "body": (
            "El teu professor està completant abans aquesta activitat per poder "
            "guiar-te. Torna-ho a provar d'aquí a uns minuts."
        ),
        "hint": "Si encara està tancada més tard, demana al teu professor que obri l'activitat.",
    },
    "eu": {
        "title": "Oraindik ez dago irekita",
        "body": (
            "Zure irakaslea jarduera hau lehenago egiten ari da, gero zure "
            "gidari izateko. Saiatu berriro minutu batzuen buruan."
        ),
        "hint": "Geroago ere itxita badago, eskatu irakasleari jarduera irekitzeko.",
    },
}


def normalize_locale(value: Any) -> Optional[str]:
    """Map a locale-ish string onto a supported locale, or None.

    Accepts BCP-47 tags with region/script subtags (``es-ES`` → ``es``) and
    is case-insensitive.
    """
    if not value:
        return None
    text = str(value).strip().lower().replace("_", "-")
    if not text:
        return None
    base = text.split("-")[0]
    return base if base in SUPPORTED_LOCALES else None


def parse_accept_language(header: Optional[str]) -> list:
    """Parse an ``Accept-Language`` header into preferred locales.

    Entries with ``q=0`` are explicit refusals and are dropped; remaining
    entries are ordered by descending quality (stable for equal q).
    """
    if not header:
        return []
    parsed = []
    for index, part in enumerate(str(header).split(",")):
        chunk = part.strip()
        if not chunk:
            continue
        pieces = chunk.split(";")
        tag = pieces[0].strip()
        quality = 1.0
        for param in pieces[1:]:
            param = param.strip()
            if param.startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
        if quality <= 0:
            continue
        locale = normalize_locale(tag)
        if locale:
            parsed.append((quality, index, locale))
    parsed.sort(key=lambda item: (-item[0], item[1]))
    return [locale for _q, _i, locale in parsed]


def resolve_locale(
    request: Any = None,
    activity: Optional[Dict[str, Any]] = None,
    url_lang: Optional[str] = None,
) -> str:
    """Resolve the locale for a workshop page (server side).

    Chain (decision C6):
        explicit ``?lang=`` → activity locale → ``Accept-Language`` → ``en``
    """
    explicit = normalize_locale(url_lang)
    if explicit:
        return explicit

    if activity:
        from_activity = normalize_locale(activity.get("locale"))
        if from_activity:
            return from_activity

    header = None
    if request is not None:
        try:
            header = request.headers.get("accept-language")
        except Exception:  # pragma: no cover - defensive
            header = None
    for locale in parse_accept_language(header):
        return locale

    return DEFAULT_LOCALE


def consent_strings(locale: Optional[str]) -> Dict[str, str]:
    """Consent copy for a locale, falling back to English."""
    return CONSENT_STRINGS.get(
        normalize_locale(locale) or DEFAULT_LOCALE, CONSENT_STRINGS[DEFAULT_LOCALE])
