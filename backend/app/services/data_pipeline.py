import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class DataCleaningPipeline:
    """
    Pipeline estadístico y de Machine Learning para la limpieza y preparación 
    de datos financieros intradía y diarios (MIT License compliance).
    
    Este pipeline asegura que el motor predictivo no sea contaminado por 
    outliers irracionales o datos nulos procedentes del feed en tiempo real.
    """
    
    def __init__(self, z_score_threshold: float = 3.0):
        self.z_score_threshold = z_score_threshold
        
    def clean_intraday_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Limpia un DataFrame de precios y volumenes intradía.
        1. Imputa valores nulos.
        2. Detecta y suaviza outliers de volumen y precio (flash crashes/spikes).
        """
        if df.empty:
            return df
            
        df_clean = df.copy()
        
        # 1. Forward fill for missing prices (asume que el precio no cambió si no hay trades)
        price_columns = [col for col in ['open', 'high', 'low', 'close'] if col in df_clean.columns]
        for col in price_columns:
            df_clean[col] = df_clean[col].ffill().bfill()
            
        # Para el volumen, los nulos se asumen como 0
        if 'volume' in df_clean.columns:
            df_clean['volume'] = df_clean['volume'].fillna(0)
            
        # 2. Outlier Detection (Z-Score method para volumen)
        if 'volume' in df_clean.columns and len(df_clean) > 30:
            vol_mean = df_clean['volume'].mean()
            vol_std = df_clean['volume'].std()
            if vol_std > 0:
                z_scores = (df_clean['volume'] - vol_mean) / vol_std
                # Cap the outliers to the threshold
                max_vol = vol_mean + (self.z_score_threshold * vol_std)
                df_clean.loc[z_scores > self.z_score_threshold, 'volume'] = max_vol
                
        return df_clean

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extrae features para el motor predictivo XGBoost/LSTM.
        (Ejemplo: Log Returns, Momentum, Volatility)
        """
        if df.empty or 'close' not in df.columns:
            return df
            
        df_features = df.copy()
        
        # Log Returns (Statistically preferred over simple returns)
        df_features['log_return'] = np.log(df_features['close'] / df_features['close'].shift(1))
        
        # Volatilidad móvil (20 periodos)
        df_features['volatility_20'] = df_features['log_return'].rolling(window=20).std()
        
        # Momentum (Cambio de precio de 10 periodos)
        df_features['momentum_10'] = df_features['close'].pct_change(periods=10)
        
        # Drop NaNs generados por los shifts y rollings
        df_features.dropna(inplace=True)
        
        return df_features

def process_ticker_snapshot(ticker: str, data: list[dict]) -> pd.DataFrame:
    """
    Función helper para procesar un snapshot de mercado en tiempo real.
    """
    if not data:
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
    pipeline = DataCleaningPipeline()
    df_clean = pipeline.clean_intraday_data(df)
    df_features = pipeline.extract_features(df_clean)
    
    return df_features
