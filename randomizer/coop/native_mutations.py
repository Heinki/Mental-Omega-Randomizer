"""Keep co-op Nanofiber evolution within each human's earned roster."""

from randomizer.maps.ini import all_section_value_maps_preserve, merge_ini_section_values
from randomizer.maps.nanofiber import nanofiber_multi_clone_rules
from randomizer.rewards.definitions import LINKED_BUFF_VARIANTS
from randomizer.rewards.roster import randomizer_unit_roster
from randomizer.ui.cameos import installed_rules_registry


def apply_coop_native_mutations(lines, manifest):
    countries = {manifest['player_country'], manifest.get('guest_country', '')}
    powers = list(manifest.get('power_reward_ids', ()))
    for loadout in manifest.get('player_loadouts', {}).values():
        powers.extend(loadout.get('power_reward_ids', ()))
    from randomizer.rewards.catalogue import canonical_reward
    if not (countries & {'Guild1', 'Guild2', 'Guild3'} or any(
        str(canonical_reward({'name': power}).get('superweapon', '')).upper()
        == 'NANOFIBERSYNCSPECIAL' for power in powers
    )):
        return
    current = {str(key).upper(): values
               for key, values in all_section_value_maps_preserve(lines).items()}
    _, clone_ids, _ = randomizer_unit_roster()
    sources = set(LINKED_BUFF_VARIANTS)
    sources.update(target for variants in LINKED_BUFF_VARIANTS.values() for target in variants)
    clone_sets = []
    for scope in ('P', 'H', 'G'):
        handled = {}
        for source in sorted(sources):
            clone = clone_ids.get(source, f'MORP{source}') if scope == 'P' else f'MOR{scope}{source}'
            if clone.upper() in current:
                handled[source] = {'clone_id': clone}
        if handled:
            clone_sets.append(handled)
    payload_sets = {}
    for clone, source in current.get('MORPOWERPAYLOADSOURCES', {}).items():
        values = current.get(str(clone).upper(), {})
        owner = next((str(value) for field, value in values.items()
                      if str(field).lower() == 'owner'), '')
        payload_sets.setdefault(owner, {})[str(source).upper()] = {'clone_id': clone}
    clone_sets.extend(payload_sets.values())
    if clone_sets:
        _, installed = installed_rules_registry(synchronous=True)
        rules = nanofiber_multi_clone_rules(lines, installed, clone_sets)
        merge_ini_section_values(lines, rules)
