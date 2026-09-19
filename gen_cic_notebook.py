#!/usr/bin/env python3
# builds cic_benchmark.ipynb (run with the venv python)
import nbformat as nbf
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook(); cells = []

cells.append(md(
    "# cic-ids2017 — offline benchmark (RandomForest vs XGBoost vs MLP)\n"
    "public benchmark on **CIC-IDS2017** (abluva/CIC-IDS-2017-V2), 40k balanced rows,\n"
    "**78 flow features**, mapped to our 5 classes. three models compared; XGBoost on the RTX 3070.\n"
    "*offline* benchmark — the board runs our own 6-feature model (`train.ipynb`)."))

cells.append(code(
    "%matplotlib inline\n"
    "import numpy as np, pandas as pd, matplotlib.pyplot as plt, time\n"
    "import xgboost as xgb\n"
    "from sklearn.model_selection import train_test_split\n"
    "from sklearn.ensemble import RandomForestClassifier\n"
    "from sklearn.neural_network import MLPClassifier\n"
    "from sklearn.preprocessing import StandardScaler, LabelEncoder\n"
    "from sklearn.metrics import (classification_report, confusion_matrix,\n"
    "    ConfusionMatrixDisplay, accuracy_score)\n"
    "import warnings; warnings.filterwarnings('ignore')\n"
    "\n"
    "df = pd.read_csv('cic_slice.csv').replace([np.inf,-np.inf], np.nan).fillna(0)\n"
    "FEATURES = [c for c in df.columns if c != 'label']\n"
    "print('rows', len(df), '| features', len(FEATURES))\n"
    "print(df['label'].value_counts().to_string())"))

cells.append(md("## detect GPU + prepare data (split + scale)"))
cells.append(code(
    "try:\n"
    "    xgb.XGBClassifier(n_estimators=2, tree_method='hist', device='cuda').fit(\n"
    "        np.zeros((4,2),'float32'), [0,1,0,1])\n"
    "    DEVICE = 'cuda'\n"
    "except Exception:\n"
    "    DEVICE = 'cpu'\n"
    "print('xgboost device:', DEVICE)\n"
    "\n"
    "X = df[FEATURES].to_numpy(dtype=float)\n"
    "le = LabelEncoder().fit(df['label'].astype(str).to_numpy())\n"
    "y = le.transform(df['label'].astype(str).to_numpy())\n"
    "Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=0)\n"
    "sc = StandardScaler().fit(Xtr)\n"
    "Xtr_s, Xte_s = sc.transform(Xtr), sc.transform(Xte)   # MLP needs scaling\n"
    "print('train', Xtr.shape, ' test', Xte.shape, ' classes', list(le.classes_))"))

cells.append(md("## three models head-to-head — RandomForest vs XGBoost (GPU) vs MLP"))
cells.append(code(
    "res = {}\n"
    "t=time.time(); rf = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=0).fit(Xtr, ytr)\n"
    "res['RandomForest'] = (accuracy_score(yte, rf.predict(Xte)), time.time()-t, '16 cores')\n"
    "t=time.time(); xg = xgb.XGBClassifier(n_estimators=300, tree_method='hist', device=DEVICE, random_state=0).fit(Xtr, ytr)\n"
    "res['XGBoost'] = (accuracy_score(yte, xg.predict(Xte)), time.time()-t, DEVICE)\n"
    "t=time.time(); mlp = MLPClassifier(hidden_layer_sizes=(64,32), max_iter=300, random_state=0).fit(Xtr_s, ytr)\n"
    "res['MLP'] = (accuracy_score(yte, mlp.predict(Xte_s)), time.time()-t, 'cpu')\n"
    "print(f\"{'model':14}{'accuracy':>10}{'train':>9}   hardware\")\n"
    "for k,(a,tt,hw) in res.items(): print(f'{k:14}{a:>10.4f}{tt:>8.1f}s   {hw}')"))

cells.append(md("## XGBoost — report + confusion matrix"))
cells.append(code(
    "pred = xg.predict(Xte)\n"
    "print('XGBoost test accuracy:', round(accuracy_score(yte, pred), 4))\n"
    "print(classification_report(yte, pred, target_names=le.classes_))\n"
    "fig, ax = plt.subplots(figsize=(6,6))\n"
    "ConfusionMatrixDisplay(confusion_matrix(yte, pred), display_labels=le.classes_).plot(ax=ax, cmap='Blues', colorbar=False)\n"
    "plt.title('CIC-IDS2017 — XGBoost'); plt.xticks(rotation=45); plt.tight_layout(); plt.show()"))

cells.append(md("## MLP — report + confusion matrix (tested on CIC too)"))
cells.append(code(
    "predm = mlp.predict(Xte_s)\n"
    "print('MLP test accuracy:', round(accuracy_score(yte, predm), 4))\n"
    "print(classification_report(yte, predm, target_names=le.classes_))\n"
    "fig, ax = plt.subplots(figsize=(6,6))\n"
    "ConfusionMatrixDisplay(confusion_matrix(yte, predm), display_labels=le.classes_).plot(ax=ax, cmap='Purples', colorbar=False)\n"
    "plt.title('CIC-IDS2017 — MLP'); plt.xticks(rotation=45); plt.tight_layout(); plt.show()"))

cells.append(md("## top flow features (XGBoost importance)"))
cells.append(code(
    "imp = pd.Series(xg.feature_importances_, index=FEATURES).sort_values()[-15:]\n"
    "plt.figure(figsize=(8,6)); imp.plot.barh()\n"
    "plt.title('top 15 features (xgboost)'); plt.tight_layout(); plt.show()"))

cells.append(md(
    "## takeaway\n"
    "- three strong models on **CIC-IDS2017** (78 flow features) — XGBoost (GPU), RandomForest, MLP.\n"
    "- all near-perfect; **XGBoost** is the headline benchmark.\n"
    "- these 78 features can't be computed live on the board, so the **on-board model is our own\n"
    "  6-feature one** (`train.ipynb`). benchmark = credibility; small model = the edge."))

nb["cells"] = cells
nbf.write(nb, "cic_benchmark.ipynb")
print("wrote cic_benchmark.ipynb with", len(cells), "cells")
