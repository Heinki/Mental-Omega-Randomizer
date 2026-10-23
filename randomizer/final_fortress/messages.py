"""Short literal messages that fit the native 32-byte trigger text field."""

from textwrap import wrap


def message_actions(text):
    """Reserve six bytes for NOSTR: and one for the native terminator."""
    text = ' '.join(text.replace(',', ' ').replace(';', '.').split())
    return [['11', '4', 'NOSTR:' + line, '0', '0', '0', '0', 'A']
            for line in wrap(text, width=25)]


def camp_clear_actions(camp, *, coop=False):
    actions = message_actions(camp['display_name'] + ' cleared!')
    actions += message_actions(f'+{camp["gems"]} Defensive Points')
    if coop:
        actions += message_actions('Awarded to every player.')
    return actions + message_actions('Collect reward crate.')
