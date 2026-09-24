def prepare_data(X):
    df = X.copy()
    df['is_bot'] = df['userPersona'].astype(str).apply(lambda x: 1 if 'SCRAPER_BOT' in x else 0)

    cols_to_keep = [
        "timestamp",
        'apiTime', 
        'applicationTime', 
        'databaseTime', 
        'cpuUsage_market', 
        'cpuUsage_trade', 
        'memoryUsage_trade', 
        'memoryUsage_market', 
        'endpointUrl', 
        'apiMethod',
        "is_bot"
    ]

    df = df[cols_to_keep].copy()
    num_cols = df.select_dtypes(include='number').columns
    df[num_cols] = df[num_cols].fillna(0)
    df["apiMethod"] = (df["apiMethod"] == "POST").astype(int) # POST = 1; GET = 0

    return df

def time_split(df, test_size=0.2):
    df = df.sort_values(by="timestamp", axis=0, ascending=True).drop("timestamp", axis=1)
    y = df.pop("is_bot")
    
    n_train = int(len(df) * (1 - test_size))

    X_train, y_train = df.iloc[:n_train, :], y.iloc[:n_train]
    X_test, y_test = df.iloc[n_train:, :], y.iloc[n_train:]
    return X_train, X_test, y_train, y_test