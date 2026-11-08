# Compila el firmware para ambos objetivos y guarda el informe de tamanos.
#   powershell -File firmware\build_all.ps1
$ErrorActionPreference = "Continue"
$idf = if ($env:IDF_PATH) { $env:IDF_PATH } else { "$env:USERPROFILE\esp\esp-idf" }
. "$idf\export.ps1" | Out-Null
Set-Location $PSScriptRoot
$out = "..\results\firmware"
New-Item -ItemType Directory -Force $out | Out-Null
foreach ($target in "esp32", "esp32s3") {
    $b = "build_$target"
    idf.py -B $b -D IDF_TARGET=$target -D "SDKCONFIG=$b/sdkconfig" -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.$target" build
    if ($LASTEXITCODE -ne 0) { Write-Output "FALLO $target"; exit 1 }
    idf.py -B $b -D IDF_TARGET=$target -D "SDKCONFIG=$b/sdkconfig" size --format json2 --output-file "$out\size_$target.json"
    idf.py -B $b -D IDF_TARGET=$target -D "SDKCONFIG=$b/sdkconfig" size-components --format text --output-file "$out\size_components_$target.txt"
    Write-Output "OK $target"
}
# Placa medidora de B03 (aplicacion aparte); cualquiera de las dos placas puede hacer de medidora.
Set-Location "$PSScriptRoot\meter_app"
foreach ($target in "esp32", "esp32s3") {
    $b = "build_$target"
    idf.py -B $b -D IDF_TARGET=$target -D "SDKCONFIG=$b/sdkconfig" build
    if ($LASTEXITCODE -ne 0) { Write-Output "FALLO medidor $target"; exit 1 }
    Write-Output "OK medidor $target"
}
