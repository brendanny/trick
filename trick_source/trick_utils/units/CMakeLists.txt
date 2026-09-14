trick_utility(trick_units Units)
target_sources(trick_units PRIVATE
    src/UCFn.cpp
    src/Unit.cpp
    src/units_conv.c
)
target_compile_features(trick_units PRIVATE c_std_99)
target_compile_features(trick_units PUBLIC cxx_std_17)
