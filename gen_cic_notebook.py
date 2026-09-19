#!/usr/bin/env python3
# builds cic_benchmark.ipynb (run with the venv python)
import nbformat as nbf
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook(); cells = []

cells.append(md(
    "# cic-ids2017 — offline benchmark (RandomForest vs XGBoost, GPU)\n"
    "public benchmark on **CIC-IDS2017** (abluva/CIC-IDS-2017-V2), 40k balanced rows,\n"
    "**78 flow features**. two strong tabular models compared; XGBoost trains on the RTX 3070.\n"
    "note: this is the *offline* benchmark — the board runs our own 6-feature model (`train.ipynb`)."))

cells.append(code(
    "%matplotlib inline\n"
    "import numpy as np, pandas as pd, matplotlib.pyplot as plt, time\n"
    "import xgboost as xgb\n"
    "from sklearn.model_selection import train_test_split\n"
    "from sklearn.ensemble import RandomForestClassifier\n"
    "from sklearn.preprocessing import LabelEncoder\n"
    "from sklearn.metrics import (classification_report, confusion_matrix,\n"
    "    ConfusionMatrixDisplay, accuracy_score)\n"
    "import warnings; warnings.filterwarnings('ignore')\n"
    "\n"
    "df = pd.read_csv('cic_slice.csv').replace([np.inf,-np.inf], np.nan).fillna(0)\n"
    "FEATURES = [c for c in df.columns if c != 'label']\n"
    "print('rows', len(df), '| features', len(FEATURES))\n"
    "print(df['label'].value_counts().to_string())"))

cells.append(md("## detect GPU + prepare data"))
cells.append(code(
    "try:\n"
    "    xgb.XGBClassifier(n_estimators=2, tree_method='hist', device='cuda').fit(\n"
    "        np.zeros((4,2),'float32'), [0,1,0,1])\n"
    "    DEVICE = 'cuda'\n"
    "except Exception as e:\n"
    "    DEVICE = 'cpu'; print('no gpu:', str(e)[:80])\n"
    "print('xgboost device:', DEVICE)\n"
    "\n"
    "X = df[FEATURES].to_numpy(dtype=float)\n"
    "le = LabelEncoder().fit(df['label'].astype(str).to_numpy())\n"
    "y = le.transform(df['label'].astype(str).to_numpy())\n"
    "Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=0)\n"
    "print('train', Xtr.shape, ' test', Xte.shape, ' classes', list(le.classes_))"))

cells.append(md("## head-to-head — RandomForest (16 cores) vs XGBoost (gpu)"))
cells.append(code(
    "t = time.time()\n"
    "rf = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=0).fit(Xtr, ytr)\n"
    "rf_t = time.time()-t; rf_acc = accuracy_score(yte, rf.predict(Xte))\n"
    "\n"
    "t = time.time()\n"
    "xg = xgb.XGBClassifier(n_estimators=300, tree_method='hist', device=DEVICE, random_state=0).fit(Xtr, ytr)\n"
    "xg_t = time.time()-t; xg_acc = accuracy_score(yte, xg.predict(Xte))\n"
    "\n"
    "print(f'RandomForest : acc {rf_acc:.4f}   train {rf_t:5.1f}s  (16 cpu cores)')\n"
    "print(f'XGBoost      : acc {xg_acc:.4f}   train {xg_t:5.1f}s  ({DEVICE})')"))

cells.append(md("## XGBoost — trees vs accuracy"))
cells.append(code(
    "sizes = [50, 100, 200, 400, 800]; acc = []\n"
    "for n in sizes:\n"
    "    m = xgb.XGBClassifier(n_estimators=n, tree_method='hist', device=DEVICE, random_state=0).fit(Xtr, ytr)\n"
    "    acc.append(accuracy_score(yte, m.predict(Xte)))\n"
    "plt.figure(figsize=(8,4)); plt.plot(sizes, acc, marker='o')\n"
    "plt.xlabel('n_estimators'); plt.ylabel('test accuracy'); plt.grid(alpha=.3)\n"
    "plt.title('xgboost: trees vs accuracy'); plt.show()\n"
    "print('accuracies:', [round(a,4) for a in acc])"))

cells.append(md("## best model (XGBoost) — report + confusion matrix"))
cells.append(code(
    "pred = xg.predict(Xte)\n"
    "print('XGBoost test accuracy:', round(accuracy_score(yte, pred), 4))\n"
    "print(classification_report(yte, pred, target_names=le.classes_))\n"
    "fig, ax = plt.subplots(figsize=(6,6))\n"
    "ConfusionMatrixDisplay(confusion_matrix(yte, pred),\n"
    "    display_labels=le.classes_).plot(ax=ax, cmap='Blues', colorbar=False)\n"
    "plt.title('CIC-IDS2017 — XGBoost confusion matrix'); plt.xticks(rotation=45)\n"
    "plt.tight_layout(); plt.show()"))

cells.append(md("## which flow features drive it (XGBoost importance)"))
cells.append(code(
    "imp = pd.Series(xg.feature_importances_, index=FEATURES).sort_values()[-15:]\n"
    "plt.figure(figsize=(8,6)); imp.plot.barh()\n"
    "plt.title('top 15 features (xgboost)'); plt.tight_layout(); plt.show()"))

cells.append(md(
    "## takeaway\n"
    "- **XGBoost** on CIC-IDS2017 (78 flow features, 40k rows) — the strong public benchmark,\n"
    "  trained on the **RTX 3070**; compared head-to-head with RandomForest above.\n"
    "- these 78 flow features can't be computed live on the board, so the **on-board model\n"
    "  stays our 6-feature one** (`train.ipynb`). benchmark = credibility; small model = the edge."))

nb["cells"] = cells
nbf.write(nb, "cic_benchmark.ipynb")
print("wrote cic_benchmark.ipynb with", len(cells), "cells")
