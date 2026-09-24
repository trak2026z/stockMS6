import pandas as pd
import numpy as np
from sklearn.covariance import EllipticEnvelope
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
import joblib
import os
import argparse
from utils import prepare_data, time_split

def train_gaussian(input_file, model_output):    
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
    
    clf = EllipticEnvelope(
        contamination=0.01,
        random_state=42,
        support_fraction=0.9
    )
    
    clf.fit(X_train)

    y_pred = (clf.predict(X_test) == -1).astype(int)

    print("\nWyniki na zbiorze TESTOWYM:")
    cm = confusion_matrix(y_test, y_pred)
    
    try:
        tn, fp, fn, tp = cm.ravel()
        print(f"TP (Bot wykryty): {tp}")
        print(f"FP (User zablokowany - False Alarm): {fp}")
        print(f"TN (User wpuszczony): {tn}")
        print(f"FN (Bot wpuszczony): {fn}")
    except ValueError:
        print(cm)
    
    print("\nRaport klasyfikacji:")
    print(classification_report(y_test, y_pred, target_names=['Human', 'Bot']))

    save_path = model_output
    if os.path.exists('weights'):
        save_path = os.path.join('weights', model_output)
    
    save_data = {
        'model': clf,
        'url_counts': url_counts,
        'train_columns': train_columns
    }

    joblib.dump(save_data, save_path)
    print(f"Model i metadane zapisane jako: {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=str, required=True, help='Nazwa katalogu (np. H1U10-50-40-10)')
    args = parser.parse_args()

    input_path = f'../{args.dir}/merged_data.csv'
    output_path = f'bot_gaussian_model_{args.dir}.pkl'

    print(f"Uruchamianie dla katalogu: {args.dir}")
    train_gaussian(input_path, output_path)