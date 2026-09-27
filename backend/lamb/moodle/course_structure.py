"""Make Moodle subsection nesting explicit in course contents (#521).

Moodle returns each subsection's content as a separate (delegated) section and places a
`subsection` module in the parent section whose customdata names that section. Without
the link an agent cannot tell which section holds a subsection's resources.
"""
import json


def _section_id(module):
    data = module.get('customdata')
    if isinstance(data, str):
        try: data = json.loads(data)
        except ValueError: return None
    try: return int((data or {}).get('sectionid'))
    except (TypeError, ValueError, AttributeError): return None


def with_subsection_links(sections):
    if not isinstance(sections, list): return sections
    by_id = {s.get('id'): s for s in sections if isinstance(s, dict)}
    for parent in sections:
        if not isinstance(parent, dict): continue
        for module in parent.get('modules') or []:
            if not isinstance(module, dict) or module.get('modname') != 'subsection': continue
            child = by_id.get(_section_id(module))
            if child is None or child is parent: continue
            module['subsection_section_id'] = child.get('id')
            child['subsection_of'] = {'section_id': parent.get('id'), 'section_name': parent.get('name'),
                                      'module_id': module.get('id')}
    return sections


def inventory(sections, modname=None, mimetype=None):
    """One row per course module, in course order, with its section, parent section and files.

    A flat, compact view of course contents for tasks over many activities or resources
    (#521). Filters keep the totals honest: `total_modules` counts every module read.
    """
    sections = with_subsection_links(sections if isinstance(sections, list) else [])
    rows, total = [], 0
    for section in sections:
        parent = section.get('subsection_of') or {}
        for module in section.get('modules') or []:
            total += 1
            if modname and module.get('modname') != modname: continue
            files = [{'filename': f.get('filename'), 'mimetype': f.get('mimetype'), 'filesize': f.get('filesize')}
                     for f in module.get('contents') or [] if isinstance(f, dict) and f.get('type', 'file') == 'file']
            if mimetype and not any((f.get('mimetype') or '') == mimetype for f in files): continue
            rows.append({'id': module.get('id'), 'name': module.get('name'), 'modname': module.get('modname'),
                         'section_id': section.get('id'), 'section_name': section.get('name'),
                         'parent_section_id': parent.get('section_id'), 'parent_section_name': parent.get('section_name'),
                         'subsection_section_id': module.get('subsection_section_id'),
                         'visible': module.get('visible'), 'uservisible': module.get('uservisible'), 'files': files})
    return {'sections': len(sections), 'total_modules': total, 'matched': len(rows),
            'filters': {'modname': modname, 'mimetype': mimetype}, 'modules': rows}
