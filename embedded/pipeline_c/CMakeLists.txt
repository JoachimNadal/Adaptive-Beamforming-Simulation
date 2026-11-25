cmake_minimum_required(VERSION 3.16)
project(abf_pipeline VERSION 2.0.0 LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

option(ABFP_BUILD_TESTS "Build tests, benchmark and tools" ON)
option(ABFP_WERROR "Treat warnings as errors" ON)
option(ABFP_SANITIZE "Enable address and undefined-behaviour sanitizers" OFF)
option(ABFP_NATIVE "Tune for the machine that builds (-march=native)" OFF)

# The Phase 1 core is compiled from its frozen sources.
set(CORE ${CMAKE_CURRENT_SOURCE_DIR}/../core)
set(SOURCES src/abfp_numeric.c src/abfp_pipeline.c src/abfp_sqrt.c ${CORE}/src/abf_weights.c
            ${CORE}/src/abf_frame.c)

function(abfp_configure target)
  target_include_directories(${target} PUBLIC include ${CORE}/include)
  if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(
      ${target}
      PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wdouble-promotion
              -Wstrict-prototypes $<$<BOOL:${ABFP_WERROR}>:-Werror>
              $<$<BOOL:${ABFP_NATIVE}>:-march=native>)
  endif()
  if(ABFP_SANITIZE)
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endif()
  if(NOT WIN32)
    target_link_libraries(${target} PUBLIC m)
  endif()
endfunction()

foreach(precision f32 f64)
  add_library(abfp_${precision} STATIC ${SOURCES})
  add_library(abfp_${precision}_shared SHARED ${SOURCES})
  target_compile_definitions(abfp_${precision}_shared PRIVATE ABFP_SHARED ABF_SHARED)
  foreach(target abfp_${precision} abfp_${precision}_shared)
    if(precision STREQUAL "f64")
      target_compile_definitions(${target} PUBLIC ABFP_DOUBLE)
    endif()
    abfp_configure(${target})
  endforeach()
endforeach()

if(ABFP_BUILD_TESTS)
  enable_testing()
  foreach(precision f32 f64)
    add_executable(test_pipeline_${precision} tests/test_pipeline.c)
    target_link_libraries(test_pipeline_${precision} PRIVATE abfp_${precision})
    abfp_configure(test_pipeline_${precision})
    add_test(NAME pipeline_${precision} COMMAND test_pipeline_${precision})

    add_executable(bench_pipeline_${precision} tests/bench_pipeline.c)
    target_link_libraries(bench_pipeline_${precision} PRIVATE abfp_${precision})
    abfp_configure(bench_pipeline_${precision})

    add_executable(abf_replay_${precision} tools/abf_replay.c)
    target_link_libraries(abf_replay_${precision} PRIVATE abfp_${precision})
    abfp_configure(abf_replay_${precision})
  endforeach()

  # C11 atomics and POSIX threads: the live receiver only exists on POSIX systems.
  if(UNIX)
    find_package(Threads REQUIRED)
    foreach(program test_ring abf_receiver)
      if(program STREQUAL "test_ring")
        add_executable(${program} tests/test_ring.c)
      else()
        add_executable(${program} tools/abf_receiver.c)
      endif()
      set_target_properties(${program} PROPERTIES C_STANDARD 11)
      target_compile_definitions(${program} PRIVATE _POSIX_C_SOURCE=200809L)
      target_link_libraries(${program} PRIVATE abfp_f64 Threads::Threads)
      abfp_configure(${program})
    endforeach()
    add_test(NAME ring COMMAND test_ring)
  endif()
endif()
