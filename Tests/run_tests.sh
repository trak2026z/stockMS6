#!/bin/bash

# Ustawienie przerywania skryptu w przypadku błędu
set -e

echo "Tworzenie wirtualnego środowiska venv..."
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
else
    echo "Środowisko 'venv' już istnieje."
fi

echo "Aktywacja wirtualnego środowiska..."
source ./venv/bin/activate

echo "Instalacja zależności z requirements.txt..."
pip install -r requirements.txt > /dev/null

# Znajdowanie pliku SQL (szuka w ./main i w folderze bieżącym)
sqlFilePath=$(find . -path "./main/*.sql" -o -name "*.sql" -maxdepth 2 | head -n 1)

if [[ -z "$sqlFilePath" ]]; then
    echo "Błąd: Nie znaleziono pliku SQL!"
    exit 1
fi

# Wyciągnięcie nazwy pliku bez rozszerzenia dla folderu wyjściowego
sqlFileName=$(basename "$sqlFilePath")
outputDir="${sqlFileName%.*}"

echo "Znaleziono plik SQL: $sqlFilePath"
echo "Wyniki zostaną zapisane w folderze: $outputDir"

echo "\nKonwersja SQL do CSV"
python3 ./sqlToCsv.py --file "$sqlFilePath" --out "$outputDir"

echo "\nTworzenie listy użytkowników"
python3 ./generate_user_classes.py --dir "./$outputDir"

echo "\nPrzygotowanie danych"
python3 ./dataPrep.py --dir "./$outputDir"

echo "\nGłówna analiza"
python3 ./mainAnalysis.py --dir "./$outputDir"

echo "\nAnaliza pojedynczego scenariusza"
python3 ./single_scenario_analysis.py --dir "./$outputDir"

echo "\nAnaliza Macierzy Pomyłek"
python3 ./analyze_confusion_matrix.py --dir "./$outputDir"

echo "\nZAKOŃCZONO"