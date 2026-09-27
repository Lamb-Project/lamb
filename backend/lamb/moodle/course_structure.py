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
