'''
tune_skin_tone.py - Fine-tuning script for the skin tone classification model.

This script improves the already-trained model (skin_tone_model.pt) using better settings.
The original model had 77% accuracy. This script tries to push it higher.

What makes this better than the original training:
  - Starts from the existing model instead of training from scratch
  - Uses more varied training images (flips, rotations, color changes, blur)
  - Gives extra weight to the brown class since it is the hardest to classify
  - Mixes two training images together to help with edge cases
  - Stops automatically if the model stops improving

Run from Backend/:
    venv\\Scripts\\python.exe tune_skin_tone.py
'''

import os, time, math, copy
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import transforms, datasets, models

# Paths to the dataset and model file
HERE       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(HERE, "Face Dataset")
CKPT_PATH  = os.path.join(HERE, "skin_tone_model.pt")

# Training settings
IMG_SIZE        = 224
BATCH_SIZE      = 32
NUM_WORKERS     = 0          # set to 0 for Windows compatibility
VAL_SPLIT       = 0.15
SEED            = 42

LR_FINETUNE     = 8e-5       # lower learning rate for fine-tuning (gentler than original)
LR_MIN          = 1e-6
WARMUP_EPOCHS   = 3
FINETUNE_EPOCHS = 35
WEIGHT_DECAY    = 1e-3       # helps reduce overfitting
GRAD_CLIP       = 1.0

DROPOUT_P       = 0.35       # higher dropout to reduce overfitting
LABEL_SMOOTH    = 0.1        # stops the model from being overconfident
BROWN_WEIGHT    = 1.3        # brown class gets 1.3x more weight in the loss
MIXUP_ALPHA     = 0.3        # blends pairs of training images together
PATIENCE        = 10         # stop if no improvement for 10 epochs

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}  |  PyTorch {torch.__version__}\n")

torch.manual_seed(SEED)
np.random.seed(SEED)

# Image transforms for training — more variation helps the model generalise better
train_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE + 32, IMG_SIZE + 32)),
    transforms.RandomCrop(IMG_SIZE),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(p=0.05),
    transforms.RandomRotation(12),
    transforms.RandomAffine(degrees=0, translate=(0.08, 0.08), shear=5),
    transforms.ColorJitter(brightness=0.45, contrast=0.45, saturation=0.35, hue=0.06),
    transforms.RandomGrayscale(p=0.04),
    transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    transforms.RandomErasing(p=0.15, scale=(0.02, 0.10)),
])

# Validation images only get resized and normalised — no random changes
val_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# Load images from the Face Dataset folder (expects Black/, Brown/, White/ subfolders)
full_ds = datasets.ImageFolder(DATA_DIR)
classes = full_ds.classes          # alphabetical order: ['Black','Brown','White']
n       = len(full_ds)
print(f"Total images: {n}  | Classes: {classes}\n")

# Split into training and validation sets
idx      = list(range(n))
np.random.shuffle(idx)
n_val    = max(1, int(n * VAL_SPLIT))
val_idx  = idx[:n_val]
train_idx= idx[n_val:]

from torch.utils.data import Subset

# Helper class that applies a transform to a subset of the dataset
class TransformSubset(torch.utils.data.Dataset):
    def __init__(self, subset, transform):
        self.subset    = subset
        self.transform = transform
    def __len__(self):  return len(self.subset)
    def __getitem__(self, i):
        img, lbl = self.subset[i]
        return self.transform(img), lbl

train_sub = TransformSubset(Subset(full_ds, train_idx), train_tf)
val_sub   = TransformSubset(Subset(full_ds, val_idx),   val_tf)

# Use weighted sampling so harder/rarer classes appear more often during training
labels_train = [full_ds.targets[i] for i in train_idx]
class_counts  = np.bincount(labels_train, minlength=len(classes))
class_weights = 1.0 / (class_counts + 1e-6)
# Give brown an extra boost since it is the hardest class to get right
brown_idx = classes.index("Brown")
class_weights[brown_idx] *= BROWN_WEIGHT
sample_w  = [class_weights[l] for l in labels_train]
sampler   = WeightedRandomSampler(sample_w, num_samples=len(train_idx), replacement=True)

train_loader = DataLoader(train_sub, batch_size=BATCH_SIZE, sampler=sampler,
                          num_workers=NUM_WORKERS, pin_memory=False)
val_loader   = DataLoader(val_sub,   batch_size=BATCH_SIZE, shuffle=False,
                          num_workers=NUM_WORKERS, pin_memory=False)

print(f"Train: {len(train_idx)}  |  Val: {len(val_idx)}\n")


def build_model(dropout_p: float):
    # MobileNetV2 with a custom classification head for 3 skin tone classes
    model = models.mobilenet_v2(weights=None)
    model.classifier = nn.Sequential(
        nn.Dropout(dropout_p),
        nn.Linear(1280, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(dropout_p * 0.75),
        nn.Linear(256, 3),
    )
    return model

model = build_model(DROPOUT_P)

# Load the existing checkpoint to continue from where we left off
print(f"Loading checkpoint: {CKPT_PATH}")
ckpt      = torch.load(CKPT_PATH, map_location="cpu", weights_only=False)
label_map = ckpt["label_map"]   # {'black':0,'brown':1,'white':2}

missing, unexpected = model.load_state_dict(ckpt["model_state"], strict=False)
if missing:    print(f"  Missing keys  : {missing}")
if unexpected: print(f"  Unexpected keys: {unexpected}")
print("Checkpoint loaded.\n")
model = model.to(device)

# Loss function — brown gets extra weight, label smoothing reduces overconfidence
cw_tensor = torch.tensor(
    [1.0, BROWN_WEIGHT, 1.0], dtype=torch.float32, device=device
)
criterion = nn.CrossEntropyLoss(weight=cw_tensor, label_smoothing=LABEL_SMOOTH)

# AdamW optimizer with weight decay to fight overfitting
optimizer = optim.AdamW(model.parameters(), lr=LR_FINETUNE, weight_decay=WEIGHT_DECAY)

# Learning rate: warm up for 3 epochs then slowly decrease with cosine curve
def lr_lambda(epoch):
    if epoch < WARMUP_EPOCHS:
        return (epoch + 1) / WARMUP_EPOCHS
    progress = (epoch - WARMUP_EPOCHS) / max(1, FINETUNE_EPOCHS - WARMUP_EPOCHS)
    return LR_MIN / LR_FINETUNE + 0.5 * (1 - LR_MIN / LR_FINETUNE) * (
        1 + math.cos(math.pi * progress)
    )

scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def mixup_batch(x, y, alpha):
    # Blend two training images together to create a mixed example
    if alpha <= 0:
        return x, y, y, 1.0
    lam = np.random.beta(alpha, alpha)
    bs  = x.size(0)
    perm = torch.randperm(bs, device=x.device)
    x_mix = lam * x + (1 - lam) * x[perm]
    return x_mix, y, y[perm], lam

def mixup_loss(pred, y_a, y_b, lam):
    # Calculate loss for the mixed image using both original labels
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


# Training loop — runs for up to FINETUNE_EPOCHS epochs with early stopping
best_val_acc  = 0.0
best_state    = None
patience_cnt  = 0
t0            = time.time()

print(f"{'Epoch':>6}  {'TrainLoss':>10}  {'TrainAcc':>9}  {'ValAcc':>7}  {'LR':>10}")
print("-" * 58)

for epoch in range(FINETUNE_EPOCHS):
    # Training phase
    model.train()
    run_loss = correct = total = 0
    for x, y in train_loader:
        x, y = x.to(device), y.to(device)
        x_m, y_a, y_b, lam = mixup_batch(x, y, MIXUP_ALPHA)
        optimizer.zero_grad()
        out  = model(x_m)
        loss = mixup_loss(out, y_a, y_b, lam)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
        optimizer.step()
        run_loss += loss.item() * x.size(0)
        pred      = out.argmax(1)
        correct  += (pred == y).sum().item()
        total    += y.size(0)
    scheduler.step()

    train_loss = run_loss / total
    train_acc  = correct  / total * 100

    # Validation phase — no gradients needed here
    model.eval()
    v_correct = v_total = 0
    with torch.no_grad():
        for x, y in val_loader:
            x, y = x.to(device), y.to(device)
            out  = model(x)
            v_correct += (out.argmax(1) == y).sum().item()
            v_total   += y.size(0)
    val_acc = v_correct / v_total * 100
    cur_lr  = optimizer.param_groups[0]["lr"]

    print(f"{epoch+1:>6}  {train_loss:>10.4f}  {train_acc:>8.2f}%  {val_acc:>6.2f}%  {cur_lr:>10.2e}")

    if val_acc > best_val_acc:
        best_val_acc = val_acc
        best_state   = copy.deepcopy(model.state_dict())
        patience_cnt = 0
    else:
        patience_cnt += 1
        if patience_cnt >= PATIENCE:
            print(f"\nEarly stopping at epoch {epoch+1}  (no improvement for {PATIENCE} epochs)")
            break

# Load the best version of the model we found during training
print(f"\nBest validation accuracy: {best_val_acc:.2f}%\n")

model.load_state_dict(best_state)
model.eval()

from collections import defaultdict

# Build a confusion matrix to see which classes are getting mixed up
n_cls    = len(classes)
conf_mat = np.zeros((n_cls, n_cls), dtype=int)

with torch.no_grad():
    for x, y in val_loader:
        x, y  = x.to(device), y.to(device)
        preds = model(x).argmax(1).cpu().numpy()
        trues = y.cpu().numpy()
        for t, p in zip(trues, preds):
            conf_mat[t][p] += 1

print("Confusion Matrix (rows=true, cols=predicted):")
header = "".join(f"{c:>10}" for c in [c.lower() for c in classes])
print(f"{'':12}{header}")
for i, row in enumerate(conf_mat):
    print(f"  {classes[i].lower():<10}" + "".join(f"{v:>10}" for v in row))

print("\nPer-class metrics:")
for i, cls in enumerate(classes):
    tp = conf_mat[i, i]
    fp = conf_mat[:, i].sum() - tp
    fn = conf_mat[i, :].sum() - tp
    prec = tp / (tp + fp + 1e-9)
    rec  = tp / (tp + fn + 1e-9)
    f1   = 2 * prec * rec / (prec + rec + 1e-9)
    print(f"  {cls.lower():<8}  precision={prec:.3f}  recall={rec:.3f}  f1={f1:.3f}")

# Save the best model so it can be loaded later
torch.save({
    "model_state": best_state,
    "label_map":   label_map,
    "img_size":    IMG_SIZE,
    "arch":        "MobileNetV2",
}, CKPT_PATH)

elapsed = (time.time() - t0) / 60
print(f"\nModel saved -> {CKPT_PATH}")
print(f"Total time: {elapsed:.1f} min")
print("Restart Flask server to pick up the new model.")
