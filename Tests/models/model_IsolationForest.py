import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder  # <-- Dodano import
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os
import argparse
from utils import prepare_data, time_split

def train_occ(input_file, model_output):
    if not os.path.exists(input_file):
        print(f"Błąd: Nie znaleziono pliku {input_file}")
        return

    print("Wczytywanie danych...")
    df = prepare_data(pd.read_csv(input_file, on_bad_lines='skip', low_memory=False))

    X_train, X_test, y_train, y_test = time_split(df, test_size=0.2)

    X_train = X_train[y_train == 0]

    print(f"Trening na {len(X_train)} próbkach (tylko Human).")
    print(f"Test na {len(X_test)} próbkach (Human + Bot).")
    
    url_counts = X_train['endpointUrl'].value_counts(normalize=True)
    
    def map_url_rarity(data_series, counts):
        return data_series.map(counts).fillna(0)
    
    X_train['endpointUrl'] = map_url_rarity(X_train['endpointUrl'], url_counts)
    X_test['endpointUrl'] = map_url_rarity(X_test['endpointUrl'], url_counts)
    
    X_train = X_train.astype(float)
    X_test = X_test.astype(float)

    train_columns = X_train.columns.tolist()
    print(f"Liczba cech: {len(train_columns)}")

    clf = IsolationForest(
        n_estimators=100, 
        max_samples='auto', 
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train)

    y_pred = (clf.predict(X_test) == -1).astype(int)

    print("\nWyniki")
    cm = confusion_matrix(y_test, y_pred)
    try:
        print(f"TP (Bot wykryty): {cm[1][1]}")
        print(f"FP (User zablokowany): {cm[0][1]}")
        print(f"TN (User wpuszczony): {cm[0][0]}")
        print(f"FN (Bot wpuszczony): {cm[1][0]}")
    except IndexError:
        print(cm)

    print("\nRaport klasyfikacji:")
    print(classification_report(y_test, y_pred, target_names=['Human', 'Bot']))

    save_data = {
        'model': clf,
        'url_counts': url_counts,
        'train_columns': train_columns
    }
    
    joblib.dump(save_data, model_output)
    print(f"Model Isolation Forest oraz metadane zapisane w: {model_output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=str, required=True, help='Nazwa podkatalogu z danymi')
    args = parser.parse_args()

    input_file_path = f'../{args.dir}/merged_data.csv'
    
    model_output_path = f'bot_occ_model{args.dir}.pkl'
    
    print(f"Uruchamianie dla katalogu: {args.dir}")
    print(f"Plik wejściowy: {input_file_path}")
    
    train_occ(input_file_path, model_output_path)