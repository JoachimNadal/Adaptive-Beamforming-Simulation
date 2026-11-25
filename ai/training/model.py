"""Small CNN on spectrograms (PyTorch)."""

import torch
from torch import nn


class SpectrogramCNN(nn.Module):
    """About 24 000 parameters, so that it stays realistic for a single-board computer."""

    def __init__(self, num_classes):
        super().__init__()

        def block(inputs, outputs):
            return nn.Sequential(
                nn.Conv2d(inputs, outputs, 3, padding=1),
                nn.BatchNorm2d(outputs),
                nn.ReLU(),
                nn.MaxPool2d(2),
            )

        self.features = nn.Sequential(block(1, 16), block(16, 32), block(32, 64))
        self.head = nn.Linear(64, num_classes)

    def forward(self, x):
        # (batch, frames, frequency) -> global average pooling makes it size-agnostic
        return self.head(self.features(x[:, None]).mean(dim=(2, 3)))


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def predict_logits(model, inputs, batch_size=256):
    """Logits for a NumPy array of spectrograms."""
    model.eval()
    with torch.no_grad():
        chunks = [
            model(torch.from_numpy(inputs[i : i + batch_size]))
            for i in range(0, len(inputs), batch_size)
        ]
    return torch.cat(chunks).numpy()
