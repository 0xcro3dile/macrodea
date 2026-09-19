#!/usr/bin/env python3
# builds train.ipynb (run with the venv python)
import nbformat as nbf

nb = nbf.v4.new_notebook()
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
cells = []

cells.append(md(
    "# edge ids — model training & evaluation\n"
    "live notebook: traffic features → attack class "
    "(`normal / scan / flood / bruteforce / slowloris`).\n"
    "steps: explore data · epoch sweep · full-core grid search · confusion matrix."))

cells.append(code(
    "%matplotlib inline\n"
    "import numpy as np, pandas as pd, matplotlib.pyplot as plt\n"
    "from sklearn.model_selection import train_test_split, GridSearchCV\n"
    "from sklearn.preprocessing import StandardScaler\n"
    "from sklearn.neural_network import MLPClassifier\n"
    "from sklearn.metrics import (classification_report, confusion_matrix,\n"
    "    ConfusionMatrixDisplay, accuracy_score)\n"
    "import warnings; warnings.filterwarnings('ignore')\n"
    "\n"
    "df = pd.read_csv('dataset.csv')\n"
    "FEATURES = ['pkts','ports','syns','top_port','held','nic_pps']\n"
    "print(df['label'].value_counts())\n"
    "df.head()"))

cells.append(md("## per-class feature signature (why the classes are separable)"))
cells.append(code("df.groupby('label')[FEATURES].mean().round(1)"))

cells.append(md("## prepare + split (scaled features, stratified 70/30)"))
cells.append(code(
    "X = df[FEATURES].to_numpy(dtype=float)\n"
    "y = df['label'].astype(str).to_numpy()      # plain numpy (works w/ or w/o pyarrow)\n"
    "classes = np.unique(y)\n"
    "scaler = StandardScaler().fit(X)\n"
    "Xs = scaler.transform(X)\n"
    "Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.3, stratify=y, random_state=0)\n"
    "print('train', Xtr.shape, ' test', Xte.shape)"))

cells.append(md("## epoch sweep — accuracy vs epochs (different epochs, different accuracy)"))
cells.append(code(
    "clf = MLPClassifier(hidden_layer_sizes=(16,), random_state=0)\n"
    "tr_acc, te_acc = [], []\n"
    "for e in range(200):\n"
    "    clf.partial_fit(Xtr, ytr, classes=classes)\n"
    "    tr_acc.append(accuracy_score(ytr, clf.predict(Xtr)))\n"
    "    te_acc.append(accuracy_score(yte, clf.predict(Xte)))\n"
    "plt.figure(figsize=(9,4))\n"
    "plt.plot(tr_acc, label='train'); plt.plot(te_acc, label='test')\n"
    "plt.xlabel('epoch'); plt.ylabel('accuracy'); plt.legend(); plt.grid(alpha=.3)\n"
    "plt.title('accuracy vs epochs'); plt.show()\n"
    "print('final test accuracy:', round(te_acc[-1], 3))"))

cells.append(md("## full-power grid search (uses all cpu cores: `n_jobs=-1`)"))
cells.append(code(
    "grid = GridSearchCV(\n"
    "    MLPClassifier(max_iter=1000, random_state=0),\n"
    "    {'hidden_layer_sizes': [(8,), (16,), (32,), (16,16)],\n"
    "     'alpha': [1e-4, 1e-3, 1e-2],\n"
    "     'activation': ['relu','tanh']},\n"
    "    cv=3, n_jobs=-1, scoring='accuracy')\n"
    "grid.fit(Xtr, ytr)\n"
    "print('best params:', grid.best_params_)\n"
    "print('best cv accuracy:', round(grid.best_score_, 3))\n"
    "best = grid.best_estimator_"))

cells.append(md("## evaluation — classification report + confusion matrix"))
cells.append(code(
    "pred = best.predict(Xte)\n"
    "print(classification_report(yte, pred))\n"
    "fig, ax = plt.subplots(figsize=(6,6))\n"
    "ConfusionMatrixDisplay(confusion_matrix(yte, pred, labels=classes),\n"
    "    display_labels=classes).plot(ax=ax, cmap='Blues', colorbar=False)\n"
    "plt.title('confusion matrix (test set)'); plt.xticks(rotation=45)\n"
    "plt.tight_layout(); plt.show()"))

cells.append(md("## save the trained model"))
cells.append(code(
    "import joblib\n"
    "joblib.dump({'model': best, 'scaler': scaler, 'features': FEATURES,\n"
    "             'classes': list(classes)}, 'ids_model.joblib')\n"
    "print('saved ids_model.joblib')"))

cells.append(md(
    "## next: int8 quantization for the board\n"
    "this notebook runs on python 3.14 (sklearn). the int8 **tflite** export needs a\n"
    "tensorflow-compatible python (3.11/3.12). options: a 3.12 env for tflite, or a\n"
    "manual numpy int8 quantization that runs on the board's `tflite_runtime`/numpy.\n"
    "**record more rows per class first** — 63 rows makes the metrics thin."))

nb["cells"] = cells
nbf.write(nb, "train.ipynb")
print("wrote train.ipynb with", len(cells), "cells")
