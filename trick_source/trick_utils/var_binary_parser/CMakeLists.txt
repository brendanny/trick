trick_utility(trick_var_binary_parser VarBinaryParser)
target_sources(trick_var_binary_parser PRIVATE
    src/var_binary_parser.cc
)
target_compile_features(trick_var_binary_parser PUBLIC cxx_std_17)
