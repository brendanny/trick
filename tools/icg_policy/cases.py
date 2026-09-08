"""Independent expected observations for unchanged legacy ICG and the resolver."""

HEADER = "/* PURPOSE: (policy characterization) */\n"


def field(units="1", io=15):
    return dict(units=units, io=io)


def cases():
    values = [
        (
            "trailing",
            HEADER + "struct Model { double x; /* trick_units(r) */\n};\n",
            {"Model": {"x": field("rad")}},
            {},
        ),
        (
            "no-header",
            "struct Model { double x; /* trick_units(r) */\n};\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "last-same-line",
            HEADER
            + "struct Model { double x; /* trick_units(m) */ /* trick_units(cm) */\n};\n",
            {"Model": {"x": field("cm")}},
            {},
        ),
        (
            "preceding-same-line",
            HEADER + "struct Model { /* trick_units(km) */ double x;\n};\n",
            {"Model": {"x": field("km")}},
            {},
        ),
        (
            "attached-previous-line",
            HEADER + "struct Model {\n/** trick_units(r) */\ndouble x;\n};\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "no-comment",
            "/* PURPOSE: (policy) ICG: (NoComment) */\nstruct Model { double x; /* trick_units(r) */\n};\n",
            {"Model": {"x": field()}},
            {},
        ),
        ("no", "/* PURPOSE: (policy) ICG: (No) */\nstruct Model { int x; };\n", {}, {}),
        (
            "attributes",
            "/* @trick_parse{attributes} */\nstruct Model { double x; /* trick_units(r) */\n};\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "dependencies",
            "/* @trick_parse{dependencies_only} */\nstruct Model { int x; };\n",
            {},
            {},
        ),
        (
            "directive-precedence",
            "/* PURPOSE: (policy) ICG: (No) @trick_parse{everything} */\nstruct Model { int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "first-header",
            HEADER
            + "/* @trick_parse{dependencies_only} */\nstruct Model { int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "ignore",
            "/* PURPOSE: (policy) ICG_IGNORE_TYPES: ((Hidden)) */\nstruct Hidden { int x; };\nstruct Model { int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "exclude-typename",
            "/* @trick_parse{everything} @trick_exclude_typename{Hidden} */\nstruct Hidden { int x; };\nstruct Model { int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "unknown-io",
            HEADER + "struct Model { int x; /* trick_io(bogus) */\n};\n",
            {"Model": {}},
            {},
        ),
        (
            "dash-io",
            HEADER + "struct Model { int x; /* trick_io(--) trick_units(1) */\n};\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "short-io-precedence",
            HEADER
            + "struct Model { int x; /* io(i) trick_io(o) trick_units(1) */\n};\n",
            {"Model": {"x": field(io=10)}},
            {},
        ),
        (
            "friend",
            HEADER + "class Model { friend void init_attrModel(); int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "friend-overload",
            HEADER + "class Model { friend void init_attrModel(int); int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "friend-prefix",
            HEADER + "class Model { friend void init_attrModelExtra(); int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "no-friend",
            HEADER + "class Model { int x; };\n",
            {"Model": {"x": field()}},
            {},
        ),
        (
            "env-ignore",
            HEADER + "struct Hidden { int x; };\nstruct Model { int x; };\n",
            {"Model": {"x": field()}},
            {"TRICK_ICG_IGNORE_TYPES": " Hidden ;"},
        ),
        (
            "env-no-comment",
            HEADER + "struct Model { double x; /* trick_units(r) */\n};\n",
            {"Model": {"x": field()}},
            {"TRICK_ICG_NOCOMMENT": "$HEADER"},
        ),
        (
            "env-exclude",
            HEADER + "struct Model { int x; };\n",
            {},
            {"TRICK_ICG_EXCLUDE": "$HEADER"},
        ),
        (
            "env-trick-exclude",
            HEADER + "struct Model { int x; };\n",
            {},
            {"TRICK_EXCLUDE": "$HEADER"},
        ),
        (
            "env-system-exclude",
            HEADER + "struct Model { int x; };\n",
            {},
            {"TRICK_SYSTEM_ICG_EXCLUDE": "$HEADER"},
        ),
        (
            "env-external",
            HEADER + "struct Model { int x; };\n",
            {},
            {"TRICK_EXT_LIB_DIRS": "$HEADER"},
        ),
        (
            "env-override",
            HEADER + "struct Model { int x; };\n",
            {"Model": {"x": field()}},
            {
                "TRICK_EXT_LIB_DIRS": "$HEADER",
                "TRICK_EXT_LIB_DIRS_OVERRIDES": "$HEADER",
            },
        ),
        (
            "env-missing",
            HEADER + "struct Model { int x; };\n",
            {"Model": {"x": field()}},
            {"TRICK_ICG_EXCLUDE": "$HEADER.missing"},
        ),
    ]
    permissions = ("**", "o", "i", "io")
    source = HEADER + "struct Model {\n"
    expected = {}
    for primary in range(4):
        for checkpoint in range(4):
            name = f"f{primary}_{checkpoint}"
            source += f"int {name}; /* trick_io({permissions[primary]}) trick_chkpnt_io({permissions[checkpoint]}) trick_units(1) */\n"
            io = primary + checkpoint * 4
            if io:
                expected[name] = field(io=io)
    source += "};\n"
    values.append(("all-io", source, {"Model": expected}, {}))
    values.append((
        "aliases",
        HEADER
        + "struct Model {\ndouble r; /* trick_units(r) */\ndouble d; /* trick_units(d) */\ndouble m; /* M distance */\n};\n",
        {"Model": {"r": field("rad"), "d": field("degree"), "m": field("m")}},
        {},
    ))
    values.append((
        "closing-marker-units",
        HEADER + "struct Model { int x; /* trick_io(io) */\n};\n",
        {"Model": {"x": field()}},
        {},
    ))
    return values


def rejections():
    # Legacy repairs these to defaults; this bounded policy refuses to guess.
    return [
        (
            "malformed-units",
            HEADER + "struct Model { double x; /* trick_units(r */\n};\n",
            {"Model": {"x": field()}},
            {},
            "ICG_POLICY_ANNOTATION",
        ),
        (
            "unknown-units",
            HEADER + "struct Model { double x; /* trick_units(no_such_unit) */\n};\n",
            {"Model": {"x": field()}},
            {},
            "ICG_POLICY_UNITS",
        ),
    ]
