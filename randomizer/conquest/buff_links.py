"""Keep Fortress's isolated types on Reloaded's Shop/Grid clone contracts."""

from randomizer.maps.clone_builder import LINKED_CLONE_REFERENCE_KEYS


SUPPORT_REFERENCE_KEYS = frozenset({'spawns', 'unloadingclass'})
BUFF_REFERENCE_KEYS = LINKED_CLONE_REFERENCE_KEYS | SUPPORT_REFERENCE_KEYS
TYPE_REFERENCE_KEYS = BUFF_REFERENCE_KEYS | {
    'freeunit', 'powersupbuilding', 'dock', 'builtat', 'academy.types', 'academy.ignore',
}


def linked_types(row, categories):
    """Follow native transforms and payloads, never unrelated incoming links."""
    names = {kind.upper(): kind for kind in categories}
    for field, value in row.items():
        if field.lower() not in BUFF_REFERENCE_KEYS - {'passengers.allowed'}:
            continue
        for token in value.split(','):
            target = names.get(token.strip().upper())
            if target:
                yield field.lower(), target


def rewrite_type_links(row, aliases):
    """Resolve all links after allocating every private identity, as in Shop/Grid."""
    names = {kind.upper(): alias for kind, alias in aliases.items()}
    for field, value in tuple(row.items()):
        if field.lower() in TYPE_REFERENCE_KEYS:
            row[field] = ','.join(names.get(token.strip().upper(), token.strip())
                                  for token in value.split(','))
