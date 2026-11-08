cmake_minimum_required(VERSION 3.16)
# Se conservan las carpetas por responsabilidad como componentes de ESP-IDF.
set(EXTRA_COMPONENT_DIRS communication inference timing power_monitor)
set(COMPONENTS main)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(biped_policy_server)
