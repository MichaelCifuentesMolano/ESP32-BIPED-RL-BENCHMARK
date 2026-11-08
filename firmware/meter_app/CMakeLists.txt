# Placa medidora de B03: aplicacion aparte, nunca corre en la placa medida.
cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS ../communication ../power_monitor)
set(COMPONENTS main)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(biped_power_meter)
