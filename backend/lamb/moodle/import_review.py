"""Human-readable import approval. Detailed hashes stay in the stored review."""
LABELS = {
    'en': ('Source', 'Course / activity', 'Destination', 'single-file grounding', 'Knowledge base',
           'Converted size', 'characters', 'estimated tokens', 'Images / media omitted', 'Other conversion warnings',
           'Hidden chapters skipped', 'Replaces the previous imported version',
           'Text conversion preserves headings, lists, links and simple tables.\nImages and media (including image-based formulae) are omitted. No OCR.',
           'The assistant model needs room for the document, instructions and conversation.\nTokens are estimated from UTF-8 bytes / 3, not the model tokenizer.',
           'LARGE DOCUMENT: a knowledge base is recommended.\nApprove only if you explicitly want the entire document as single-file grounding.'),
    'es': ('Fuente', 'Curso / actividad', 'Destino', 'documento de contexto de archivo único', 'Base de conocimiento',
           'Tamaño convertido', 'caracteres', 'tokens estimados', 'Imágenes / medios omitidos', 'Otras advertencias de conversión',
           'Capítulos ocultos omitidos', 'Sustituye la versión importada anterior',
           'La conversión conserva títulos, listas, enlaces y tablas sencillas.\nOmite imágenes y medios, incluidas fórmulas en imagen. Sin OCR.',
           'El modelo del asistente necesita espacio para el documento, las instrucciones y la conversación.\nLos tokens se estiman con los bytes UTF-8 / 3, sin el tokenizador del modelo.',
           'DOCUMENTO GRANDE: se recomienda una base de conocimiento.\nAprueba solo si quieres expresamente el documento completo como contexto de archivo único.'),
    'ca': ('Font', 'Curs / activitat', 'Destinació', 'document de context d’un sol fitxer', 'Base de coneixement',
           'Mida convertida', 'caràcters', 'tokens estimats', 'Imatges / mitjans omesos', 'Altres advertiments de conversió',
           'Capítols ocults omesos', 'Substitueix la versió importada anterior',
           'La conversió conserva títols, llistes, enllaços i taules senzilles.\nOmet imatges i mitjans, incloses fórmules en imatge. Sense OCR.',
           'El model de l’assistent necessita espai per al document, les instruccions i la conversa.\nEls tokens s’estimen amb els bytes UTF-8 / 3, sense el tokenitzador del model.',
           'DOCUMENT GRAN: es recomana una base de coneixement.\nAprova només si vols expressament el document complet com a context d’un sol fitxer.'),
    'eu': ('Iturria', 'Ikastaroa / jarduera', 'Helmuga', 'fitxategi bakarreko testuingurua', 'Ezagutza-basea',
           'Bihurtutako tamaina', 'karaktere', 'zenbatetsitako tokenak', 'Baztertutako irudiak / multimedia', 'Bihurketaren beste ohar batzuk',
           'Baztertutako ezkutuko kapituluak', 'Aurretik inportatutako bertsioa ordezten du',
           'Bihurketak izenburuak, zerrendak, estekak eta taula sinpleak mantentzen ditu.\nIrudiak eta multimedia baztertzen ditu, baita irudietako formulak ere. OCRrik gabe.',
           'Laguntzailearen ereduak dokumenturako, jarraibideetarako eta elkarrizketarako lekua behar du.\nTokenak UTF-8 byteak / 3 erabiliz zenbatesten dira, ereduaren tokenizatzailea erabili gabe.',
           'DOKUMENTU HANDIA: ezagutza-basea gomendatzen da.\nOnartu soilik dokumentu osoa fitxategi bakarreko testuinguru gisa nahi baduzu.'),
}


def render_review(review, language):
    l = LABELS.get(language, LABELS['en'])
    source, dest = review['source'], review['destination']
    loss = review.get('conversion_losses', {})
    lines = [f"{l[0]}: {source['title']}", source['source_url'],
             f"{l[1]}: {source['course_id']} / {source['module_id']}",
             f"{l[2]}: {l[3] if dest['single_file'] else l[4] + ' ' + str(dest['kb_id'])}"]
    if review.get('kind') == 'folder':
        words = {
            'en': ('Files to import', 'Skipped files', 'One approval covers the listed files, including subfolders.'),
            'es': ('Archivos para importar', 'Archivos excluidos', 'Una aprobación cubre los archivos indicados, incluidas las subcarpetas.'),
            'ca': ('Fitxers per importar', 'Fitxers exclosos', 'Una aprovació cobreix els fitxers indicats, incloses les subcarpetes.'),
            'eu': ('Inportatzeko fitxategiak', 'Baztertutako fitxategiak', 'Onarpen bakarrak zerrendatutako fitxategiak hartzen ditu, azpikarpetak barne.'),
        }.get(language, ('Files to import', 'Skipped files', 'One approval covers the listed files, including subfolders.'))
        lines += [f"{words[0]}: {review['file_count']}", f"{l[5]}: {review['bytes']} bytes"]
        for file in review['files']:
            losses = file['conversion_losses']
            lines.append(f"- {file['path']} ({file['bytes']} bytes; {l[8]}: {losses.get('images', 0) + losses.get('media', 0)}; {l[9]}: {sum(v for k, v in losses.items() if k not in {'images', 'media'})})")
        lines.append(f"{words[1]}: {len(review['skipped'])}")
        reasons = dict(zip(('excluded_by_user', 'unsupported_format', 'external_repository_file', 'over_10_MiB'), {
            'en': ('excluded by you', 'unsupported format', 'external repository link', 'over 10 MiB'),
            'es': ('excluido por ti', 'formato no compatible', 'enlace a repositorio externo', 'supera 10 MiB'),
            'ca': ('exclòs per tu', 'format no compatible', 'enllaç a un repositori extern', 'supera 10 MiB'),
            'eu': ('zuk baztertua', 'formatu onartugabea', 'kanpoko biltegirako esteka', '10 MiB baino gehiago'),
        }.get(language, ('excluded by you', 'unsupported format', 'external repository link', 'over 10 MiB'))))
        lines += [f"- {file['path']}: {reasons.get(file['reason'], file['reason'])}" for file in review['skipped']]
        return '\n'.join(lines + [l[12], words[2]])
    if review.get('replacement_of'): lines.append(l[11])
    if 'characters' in review:
        lines += [f"{l[5]}: {review['characters']} {l[6]}, ~{review['estimated_tokens']} {l[7]}", l[13]]
    else: lines.append(f"{l[5]}: {review['bytes']} bytes")
    lines += [f"{l[8]}: {loss.get('images', 0)} / {loss.get('media', 0)}",
              f"{l[9]}: {sum(v for k, v in loss.items() if k not in {'images', 'media'})}",
              f"{l[10]}: {review.get('hidden_chapters_skipped', 0)}", l[12]]
    if review.get('estimated_tokens', 0) > review.get('reference_document_max_tokens', 24000):
        lines += ['', l[14]]
    return '\n'.join(lines)
