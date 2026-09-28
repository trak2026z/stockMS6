import os
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

OUTPUT_DIR = 'EDA'

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_text_report(filename, content):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Zapisano raport: {filepath}")

def sepReplicas(source_path):
    print("Agregacja zasobów Trade (CPU + RAM)")
    input_file = os.path.join(source_path, 'trade_cpu.csv')
    output_file = os.path.join(source_path, 'trade_cpu_pivot.csv')
    
    try:
        if not os.path.exists(input_file):
            print(f"Pominięto: brak pliku {input_file}")
            return

        trade_cpu = pd.read_csv(input_file)
        
        if 'timestamp' in trade_cpu.columns:
            trade_cpu['timestamp'] = pd.to_datetime(trade_cpu['timestamp'])
            trade_cpu['timestamp_sec'] = trade_cpu['timestamp'].dt.floor('1s')
            
            agg_trade = trade_cpu.groupby('timestamp_sec')[['cpuUsage', 'memoryUsage']].mean().reset_index()
            
            agg_trade = agg_trade.rename(columns={
                'timestamp_sec': 'timestamp', 
                'cpuUsage': 'cpuUsage_trade',
                'memoryUsage': 'memoryUsage_trade'
            })
            
            agg_trade = agg_trade.sort_values('timestamp')
            
            agg_trade.to_csv(output_file, index=False)
            print(f"Stworzono zagregowany plik Trade: {output_file}")
        else:
            pass
    except Exception as e:
        print(e)

def mergeData(source_path):
    print("\nŁączenie danych")
    try:
        files_map = {
            'market_log': 'complete_market_log_csv.csv',
            'trade_log': 'sum_trade_log.csv',
            'market_cpu': 'market_cpu.csv',
            'trade_cpu_pivot': 'trade_cpu_pivot.csv',
            'traffic_cpu': 'traffic_cpu.csv'
        }
        
        dfs = {}
        for key, filename in files_map.items():
            filepath = os.path.join(source_path, filename)
            if os.path.exists(filepath):
                df = pd.read_csv(filepath, na_values=['\\N'])
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
                    df = df.sort_values('timestamp')
                    dfs[key] = df

        if 'market_log' not in dfs:
            return False

        merged_df = dfs['market_log']

        if 'traffic_cpu' in dfs:
            t_df = dfs['traffic_cpu'].rename(columns={
                'cpuUsage': 'cpuUsage_traffic', 
                'memoryUsage': 'memoryUsage_traffic'
            })
            if 'id' in t_df.columns: t_df = t_df.drop(columns=['id'])
            merged_df = pd.merge_asof(merged_df, t_df, on='timestamp', direction='nearest', tolerance=pd.Timedelta('30s'))

        if 'trade_log' in dfs:
            merged_df = pd.merge_asof(merged_df, dfs['trade_log'], on='timestamp', direction='backward', tolerance=pd.Timedelta('1min'), suffixes=('', '_trade_log'))

        if 'market_cpu' in dfs:
            m_cpu = dfs['market_cpu'].rename(columns={
                'cpuUsage': 'cpuUsage_market',
                'memoryUsage': 'memoryUsage_market'
            })
            cols_to_drop = [c for c in m_cpu.columns if 'id' in c]
            m_cpu = m_cpu.drop(columns=cols_to_drop)
            merged_df = pd.merge_asof(merged_df, m_cpu, on='timestamp', direction='nearest', tolerance=pd.Timedelta('30s'))

        if 'trade_cpu_pivot' in dfs:
            merged_df = pd.merge_asof(merged_df, dfs['trade_cpu_pivot'], on='timestamp', direction='nearest', tolerance=pd.Timedelta('30s'))

        merged_df = merged_df.dropna(subset=['applicationTime']) 
        if 'userPersona' in merged_df.columns:
            merged_df['userPersona'] = merged_df['userPersona'].fillna('UNKNOWN')

        output_file = os.path.join(source_path, 'merged_data.csv')
        merged_df.to_csv(output_file, index=False)
        print(f"Zapisano merged_data.csv. Kolumny: {list(merged_df.columns)}")
        return not merged_df.empty
        
    except Exception as e:
        print(e)
        return False

def focusedPersonaCorrelation(source_path):
    print("\nDedykowana analiza korelacji")
    input_file = os.path.join(source_path, 'merged_data.csv')
    try:
        df = pd.read_csv(input_file)
        
        if 'userPersona' not in df.columns:
            return

        persona_dummies = pd.get_dummies(df['userPersona'], prefix='Persona')
        
        numeric_cols = [col for col in df.select_dtypes(include=[np.number]).columns 
                        if col not in ['id', 'userId', 'id_trade_log', 'timestamp']]
        
        if 'apiMethod' in df.columns:
             method_dummies = pd.get_dummies(df['apiMethod'], prefix='Method')
             analysis_df = pd.concat([persona_dummies, df[numeric_cols], method_dummies], axis=1)
        else:
             analysis_df = pd.concat([persona_dummies, df[numeric_cols]], axis=1)

        corr_matrix = analysis_df.corr(method='pearson')
        
        persona_rows = [c for c in corr_matrix.index if c.startswith('Persona_')]
        other_cols = [c for c in corr_matrix.columns if not c.startswith('Persona_')]
        
        focused_corr = corr_matrix.loc[persona_rows, other_cols]
        
        focused_corr = focused_corr.loc[:, (focused_corr != 0).any(axis=0)]

        if focused_corr.empty:
            print("Brak istotnych korelacji.")
            return

        plt.figure(figsize=(16, 8))
        sns.heatmap(focused_corr, annot=True, cmap='RdBu_r', center=0, fmt=".2f", linewidths=.5)
        plt.title('Klasa użytkownika względem parametrów systemowych i typów API')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        output_img = os.path.join(OUTPUT_DIR, 'persona_correlation_matrix.png')
        plt.savefig(output_img)
        plt.close()
        
        report = "Najsilniejsze korelacje dla Person (abs > 0.1):\n"
        for persona in persona_rows:
            series = focused_corr.loc[persona]
            strong_corrs = series[series.abs() > 0.1].sort_values(key=abs, ascending=False)
            if not strong_corrs.empty:
                report += f"\n[{persona}]:\n"
                report += strong_corrs.to_string() + "\n"
        
        save_text_report('persona_correlation_report.txt', report)

    except Exception as e:
        print(e)
        import traceback
        traceback.print_exc()

def personaAnalysis(source_path):
    print("\nAnaliza wydajności per klasa użytkownika")
    input_file = os.path.join(source_path, 'merged_data.csv')
    try:
        df = pd.read_csv(input_file)
        if 'userPersona' not in df.columns or 'apiTime' not in df.columns:
            return

        plt.figure(figsize=(12, 8))
        sns.boxplot(x='userPersona', y='apiTime', data=df, palette="Set3")
        plt.title('Rozkład czasu odpowiedzi API (ms) wg typu użytkownika')
        plt.yscale('log')
        plt.ylabel('Czas API (ms) - skala log')
        plt.savefig(os.path.join(OUTPUT_DIR, 'persona_performance.png'), bbox_inches='tight')
        plt.close()
        print("Zapisano: persona_performance.png")

        report = df.groupby('userPersona')[['apiTime', 'databaseTime', 'applicationTime']].describe().to_string()
        save_text_report('persona_stats.txt', report)

    except Exception as e:
        print(e)

def main():
    global OUTPUT_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', type=str, default='.', help='Katalog z plikami CSV')
    args = parser.parse_args()
    
    if not os.path.exists(args.dir):
        return

    OUTPUT_DIR = os.path.join(args.dir, 'EDA')
    ensure_dir(OUTPUT_DIR)
    
    sepReplicas(args.dir)
    
    if mergeData(args.dir):
        focusedPersonaCorrelation(args.dir)
        personaAnalysis(args.dir)
    else:
        pass


if __name__ == "__main__":
    main()