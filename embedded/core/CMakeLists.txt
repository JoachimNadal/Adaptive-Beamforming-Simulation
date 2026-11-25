cmake_minimum_required(VERSION 3.16)
project(abf_core VERSION 1.0.0 LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

option(ABF_BUILD_TESTS "Build unit tests and benchmark" ON)
option(ABF_WERROR "Treat warnings as errors" ON)
option(ABF_SANITIZE "Enable address and undefined-behaviour sanitizers" OFF)

set(ABF_SOURCES src/abf_weights.c src/abf_frame.c)

function(abf_configure target)
  target_include_directories(${target} PUBLIC include)
  if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion
                           -Wdouble-promotion -Wstrict-prototypes $<$<BOOL:${ABF_WERROR}>:-Werror>)
  endif()
  if(ABF_SANITIZE)
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endif()
  if(NOT WIN32)
    target_link_libraries(${target} PUBLIC m)
  endif()
endfunction()

add_library(abf STATIC ${ABF_SOURCES})
abf_configure(abf)

# Shared build used by the Python cross-checks (tests/test_c_core.py).
add_library(abf_shared SHARED ${ABF_SOURCES})
target_compile_definitions(abf_shared PRIVATE ABF_SHARED)
abf_configure(abf_shared)

if(ABF_BUILD_TESTS)
  enable_testing()
  add_executable(test_abf tests/test_abf.c)
  target_link_libraries(test_abf PRIVATE abf)
  abf_configure(test_abf)
  add_test(NAME abf_unit COMMAND test_abf)

  add_executable(bench_abf tests/bench_abf.c)
  target_link_libraries(bench_abf PRIVATE abf)
  abf_configure(bench_abf)
endif()
