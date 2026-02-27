import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ART_DIR = "ml/artifacts/sarimax"
os.makedirs(ART_DIR, exist_ok=True)

DATE_COL = "arrival_date"
TARGET = "modal_price"

def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100

def load_split(path):
    df = pd.read_csv(path, low_memory=False)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df = df.dropna(subset=[DATE_COL, TARGET]).sort_values(DATE_COL)
    return df

def adf_test(series):
    result = adfuller(series.dropna())
    return result[1]  # p-value

def evaluate(y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    _mape = mape(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return rmse, mae, _mape, r2

def train_sarimax(train_series, val_series):
    best_aic = np.inf
    best_model = None
    best_order = None

    p_values = [0,1,2]
    d_values = [0,1]
    q_values = [0,1,2]

    for p in p_values:
        for d in d_values:
            for q in q_values:
                try:
                    model = SARIMAX(train_series,
                                    order=(p,d,q),
                                    enforce_stationarity=False,
                                    enforce_invertibility=False)
                    result = model.fit(disp=False)
                    if result.aic < best_aic:
                        best_aic = result.aic
                        best_model = result
                        best_order = (p,d,q)
                except:
                    continue

    return best_model, best_order

def main():
    train = load_split("ml/data/processed/train.csv")
    val   = load_split("ml/data/processed/val.csv")
    test  = load_split("ml/data/processed/test.csv")

    commodities = train["commodity"].unique()

    results = []

    for com in commodities:
        print("\n" + "="*70)
        print("Commodity:", com)

        train_com = train[train["commodity"] == com]
        val_com   = val[val["commodity"] == com]
        test_com  = test[test["commodity"] == com]

        # pick top 2 markets
        top_markets = (
            train_com.groupby("market")
            .size()
            .sort_values(ascending=False)
            .head(2)
            .index.tolist()
        )

        for market in top_markets:
            print(f"Training SARIMAX for {com} - {market}")

            tr = train_com[train_com["market"] == market].set_index(DATE_COL)[TARGET]
            va = val_com[val_com["market"] == market].set_index(DATE_COL)[TARGET]
            te = test_com[test_com["market"] == market].set_index(DATE_COL)[TARGET]

            if len(tr) < 40:
                print("Skipping (too short)")
                continue

            model, order = train_sarimax(tr, va)
            print("Best order:", order)

            # Forecast VAL
            val_pred = model.forecast(steps=len(va))
            rmse_v, mae_v, mape_v, r2_v = evaluate(va.values, val_pred.values)

            # Refit on train+val for test forecast
            full_series = pd.concat([tr, va])
            model_full = SARIMAX(full_series,
                                 order=order,
                                 enforce_stationarity=False,
                                 enforce_invertibility=False).fit(disp=False)

            test_pred = model_full.forecast(steps=len(te))
            rmse_t, mae_t, mape_t, r2_t = evaluate(te.values, test_pred.values)

            print(f"VAL  | RMSE={rmse_v:.2f} MAPE={mape_v:.2f}% R2={r2_v:.3f}")
            print(f"TEST | RMSE={rmse_t:.2f} MAPE={mape_t:.2f}% R2={r2_t:.3f}")

            results.append([
                com, market,
                rmse_v, mae_v, mape_v, r2_v,
                rmse_t, mae_t, mape_t, r2_t
            ])

    cols = [
        "commodity","market",
        "val_rmse","val_mae","val_mape","val_r2",
        "test_rmse","test_mae","test_mape","test_r2"
    ]

    df_results = pd.DataFrame(results, columns=cols)
    df_results.to_csv(os.path.join(ART_DIR,"sarimax_results.csv"), index=False)

    print("\n✅ SARIMAX results saved.")

if __name__ == "__main__":
    main()