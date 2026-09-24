# Runtime metadata uses executable symbol lookup; consumers opt in explicitly.
function(trick_enable_runtime target)
    target_link_libraries(${target} PRIVATE Trick::Runtime)
    set_target_properties(${target} PROPERTIES ENABLE_EXPORTS ON)
endfunction()
