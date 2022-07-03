import pandas as pd
import os

import config as cfg
from utils.yahoo_downloader import YahooDownloader
import utils.helper_functions as hf

from stockstats import wrap

import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.feature_selection import mutual_info_classif

pd.options.mode.chained_assignment = None

def get_yahoo_data(folder_path: str, file_name: str, start_date: str, end_date: str, tickers: list[str]) -> pd.DataFrame:
    """ Save a db with ohlcv + day + tickers data and return df """
    file_path = folder_path + file_name

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    if os.path.isfile(file_path):
        df = pd.read_pickle(file_path)
    else:
        df = YahooDownloader(start_date, end_date, tickers).fetch_data()        
        df.to_pickle(file_path)

    return df

def add_stats(df: pd.DataFrame) -> pd.DataFrame:
    """" Add stockstats data to df """
    df = wrap(df) # Convert to stockstats legible format

    df['ups'] = df['change'] > 0
    df['downs'] = df['change'] < 0
    df[cfg.stats]
    df['change_-10~0_min'] = df['close'] / df['close_-10~0_min']
    df['change_-10~0_max'] = df['close'] / df['close_-10~0_max']
    df[cfg.target_feature] = df[::-1]['close'].rolling(cfg.target_days).max() / df['close']
    df[cfg.target_feature_class] = df[cfg.target_feature] > 1 + cfg.target_percent_increase

    print(df.head())
    print(df.shape)

    return df.dropna()

def plot_correlations(df: pd.DataFrame, folder_path: str, file_name: str) -> None:
    """ Save a pdf plot of correlations between features """
    df = df[::-1]  # reverse temporality
    corr_df = df.corr().round(2)
    plt.figure(figsize=(70,40))
    sns.heatmap(corr_df, annot=True)
    plt.subplots_adjust(left=0.2, bottom=0.35)
    plt.savefig(folder_path + file_name)
    plt.close()

def plot_feature_importances(df: pd.DataFrame, X_features: list, y_feature: str, folder_path: str, file_name: str) -> None:
    """ Save a pdf plot of feature importances on injuries """
    X_df = df[X_features]
    y_df = df[y_feature]

    feature_importances = mutual_info_classif(X_df, y_df, random_state=0, n_neighbors=3, discrete_features='auto')
    feature_importances = pd.Series(feature_importances, X_df.columns)
    feature_importances.plot(figsize=(20,15), kind='barh', title='Feature importances')
    plt.subplots_adjust(left=0.3)
    plt.savefig(folder_path + file_name)
    plt.close()

def add_supports_resistances(df: pd.DataFrame) -> pd.DataFrame:
    df['rolling_min'] = hf.get_rolling_min(df['low'], cfg.target_days)
    df['rolling_max'] = hf.get_rolling_max(df['high'], cfg.target_days)
    df['last_close'] = df['close'].shift(1)

    df['pivot'] = hf.get_pivot(df['rolling_max'], df['rolling_min'], df['last_close'])

    df = df.dropna()

    df['support1'] = hf.get_support1(df['pivot'], df['rolling_max'])
    df['support2'] = hf.get_support2(df['pivot'], df['rolling_max'], df['rolling_min'])
    df['resistance1'] = hf.get_resistance1(df['pivot'], df['rolling_min'])
    df['resistance2'] = hf.get_resistance2(df['pivot'], df['rolling_max'], df['rolling_min'])

    return df

def get_profit(df: pd.DataFrame, support_column: str, resistance_column: str) -> list:
    profit = 1
    buy_price = 0
    bought_days = 0
    is_bought = False

    support = df.iloc[0][support_column]
    resistance = df.iloc[0][resistance_column]

    for row in df.itertuples():
        last_close = row.last_close
        open = row.open

        if (is_bought and last_close > resistance):
            is_bought = False
            sell_price = open
            profit *= (sell_price / buy_price) * cfg.fee_coef
        elif (not is_bought and last_close < support):
            is_bought = True
            buy_price = open
            profit *= cfg.fee_coef
        
        if is_bought:
            bought_days += 1

    if bought_days > 0:
        return profit, bought_days
    else:
        return 0, 0

def main():
    all_df = get_yahoo_data(
        folder_path='./db/', file_name='ohlcv.pkl',
        start_date=cfg.start_date, end_date=cfg.end_date,
        tickers=cfg.tickers)
    
    profits = []

    for ticker in cfg.tickers:
        df = all_df.loc[all_df['tic'] == ticker]

        if not df.empty:
            df = add_supports_resistances(df)

            days = len(df)
            profit, bought_days = get_profit(df, 'support1', 'resistance1')

            profits.append({
                'ticker': ticker,
                'profit': hf.pct(profit - 1) if bought_days > 0 else 0,
                'daily_profit': hf.pct(profit / bought_days) if bought_days > 0 else 0,
                'days': days,
                'bought_days': bought_days,
                'bought_days%': hf.pct(bought_days / days)
            })

    profit_df = pd.DataFrame(profits)
    print(profit_df.head())
    print(profit_df['daily_profit'].mean(skipna=True))
    print(profit_df['bought_days%'].mean(skipna=True))

    # df = add_stats(df)
    # plot_correlations(df=df, folder_path='./plots/', file_name='correlations.pdf')
    # plot_feature_importances(
    #     df=df,
    #     X_features=cfg.X_features, y_feature=cfg.target_feature_class,
    #     folder_path='./plots/', file_name='feature_importances.pdf')

if __name__ == "__main__":
    main()
