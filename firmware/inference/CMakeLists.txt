idf_component_register(SRCS "policy.c" "models_generated.c" INCLUDE_DIRS "include")
target_compile_options(${COMPONENT_LIB} PRIVATE -O3)
