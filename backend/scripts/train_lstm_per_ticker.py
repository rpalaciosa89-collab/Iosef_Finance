import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)
PLOT_DIR = BASE_DIR.parent / "artifacts" / "plots"
PLOT_DIR.mkdir(parents=True, exist_ok=True)

class TickerLSTM(nn.Module):
    """
    Arquitectura LSTM pura enfocada en secuencias (20 días).
    Atiende especialmente a: Volumen, Momentum, Volatilidad, Returns.
    """
    def __init__(self, input_size=4, hidden_size=32, num_layers=2):
        super(TickerLSTM, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # x shape: (batch, seq_len, features)
        out, (hn, cn) = self.lstm(x)
        # Tomar el último paso de la secuencia
        out = out[:, -1, :]
        out = self.fc(out)
        return self.sigmoid(out)

def create_synthetic_sequence_data(samples=1000, seq_len=20):
    """
    Genera datos sintéticos secuenciales simulando el flujo de un ticker.
    Features: [Volume(Norm), LogReturn, Momentum, MACD]
    """
    np.random.seed(42)
    # Dimensiones: (samples, seq_len, 4)
    X = np.random.normal(0, 1, (samples, seq_len, 4))
    
    # Simular que si el volumen (feature 0) es alto y el retorno (feature 1) es positivo,
    # hay más probabilidad de éxito.
    volume_effect = np.mean(X[:, :, 0], axis=1)
    return_effect = np.mean(X[:, :, 1], axis=1)
    
    prob = 1 / (1 + np.exp(-(volume_effect + return_effect * 2)))
    y = np.random.binomial(1, prob).astype(np.float32)
    
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32).unsqueeze(1)

def train_ticker_model(ticker="AAPL"):
    logger.info(f"--- Iniciando Entrenamiento LSTM para: {ticker} ---")
    
    # 1. Preparar datos
    seq_len = 20
    X_train, y_train = create_synthetic_sequence_data(1000, seq_len)
    
    # 2. Inicializar Modelo, Loss y Optimizador
    model = TickerLSTM(input_size=4)
    criterion = nn.BCELoss()  # Binary Cross Entropy
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    
    epochs = 50
    losses = []
    
    # 3. Loop de Entrenamiento
    logger.info(f"[{ticker}] Entrenando red neuronal...")
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
        
        losses.append(loss.item())
        if (epoch+1) % 10 == 0:
            logger.info(f"[{ticker}] Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")
            
    # 4. Guardar Modelo
    model_path = MODEL_DIR / f"lstm_{ticker}.pth"
    torch.save(model.state_dict(), model_path)
    logger.info(f"[{ticker}] Modelo guardado en: {model_path}")
    
    # 5. Generar Gráfico (Innegociable)
    plt.figure(figsize=(10, 5))
    sns.set_style("darkgrid")
    
    # Curva de Convergencia
    plt.plot(losses, label='Loss (BCE)', color='purple', linewidth=2)
    plt.title(f'[{ticker}] Convergencia de Red Neuronal (LSTM)')
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend()
    
    plot_path = PLOT_DIR / f"lstm_loss_{ticker}.png"
    plt.savefig(plot_path)
    plt.close()
    
    logger.info(f"[{ticker}] Gráfico generado: {plot_path}")

if __name__ == "__main__":
    # Prueba de concepto con tres tickers importantes
    tickers_to_train = ["AAPL", "MSFT", "NVDA"]
    for t in tickers_to_train:
        train_ticker_model(t)
