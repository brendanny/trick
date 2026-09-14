trick_utility(trick_optimization Optimization)
target_sources(trick_optimization PRIVATE
    src/dPDIP_solver.c
)
target_compile_features(trick_optimization PRIVATE c_std_99)
target_link_libraries(trick_optimization PRIVATE Trick::Math)
