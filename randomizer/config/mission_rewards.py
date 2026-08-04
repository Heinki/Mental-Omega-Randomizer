"""Validation helpers for configurable mission reward multipliers."""


def validate_mission_reward_config(sections, path, invalid):
    reward_config = sections['mission_reward_multipliers']
    class_multipliers = reward_config.get('class_multipliers')
    mission_classes = reward_config.get('mission_classes')
    mission_overrides = reward_config.get('mission_overrides')
    default_multiplier = reward_config.get('default_multiplier')

    def nonempty_string(value):
        return isinstance(value, str) and bool(value)

    def valid_multiplier(value):
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 1 <= value <= 30
        )

    if (
        not valid_multiplier(default_multiplier)
        or not isinstance(class_multipliers, dict)
        or not class_multipliers
        or not all(
            nonempty_string(name) and valid_multiplier(multiplier)
            for name, multiplier in class_multipliers.items()
        )
        or not isinstance(mission_classes, dict)
        or set(mission_classes) != set(class_multipliers)
        or not isinstance(mission_overrides, dict)
    ):
        invalid('Invalid mission reward multiplier config', path)

    classified_codes = []
    for class_name, codes in mission_classes.items():
        if not isinstance(codes, list) or not all(
            nonempty_string(code)
            and code in sections['build_classifications']
            for code in codes
        ):
            invalid(f'Invalid mission reward class {class_name!r}', path)
        classified_codes.extend(codes)
    if (
        len(classified_codes) != len(set(classified_codes))
        or set(classified_codes) != set(sections['build_classifications'])
    ):
        invalid(
            'Mission reward classes must classify every mission exactly once',
            path,
        )
    if not all(
        nonempty_string(code)
        and code in sections['build_classifications']
        and valid_multiplier(multiplier)
        for code, multiplier in mission_overrides.items()
    ):
        invalid('Invalid mission reward multiplier override', path)
