#!/usr/bin/env python3
"""Train the on-board model and export it as an int8 TensorFlow Lite file.

    python training/train.py

Reads data/dataset.csv (windows recorded on the board with edge_ids.py --record),
trains a small neural network on all of it and writes board/model.tflite and
board/model.json. notebooks/train.ipynb goes through the same steps with plots
and a held-out test set.
"""
import csv
import json
import pathlib

import numpy as np
import tensorflow as tf

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dataset.csv"
OUT = ROOT / "board"
FEATURES = ["pkts", "ports", "syns", "top_port", "held", "nic_pps"]   # same order edge_ids.py uses

tf.keras.utils.set_random_seed(0)

with open(DATA) as f:
    rows = list(csv.DictReader(f))
labels = sorted({r["label"] for r in rows})
X = np.array([[float(r[k]) for k in FEATURES] for r in rows], np.float32)
y = np.array([labels.index(r["label"]) for r in rows])

# The features go from 0 up to ~100k (packet rate). log1p squashes that and
# dividing by the max puts everything in 0..1. The board has to do exactly the
# same, so the max values are saved as "scale" in model.json.
X = np.log1p(X)
scale = X.max(axis=0)
scale[scale == 0] = 1
X = (X / scale).astype(np.float32)

model = tf.keras.Sequential([
    tf.keras.layers.Input((len(FEATURES),)),
    tf.keras.layers.Dense(24, activation="relu"),
    tf.keras.layers.Dense(len(labels), activation="softmax"),
])
model.compile("adam", "sparse_categorical_crossentropy", metrics=["accuracy"])
model.fit(X, y, epochs=400, verbose=0)
float_acc = model.evaluate(X, y, verbose=0)[1]


# int8 quantization. Every weight and activation is stored as a whole number
# from -128 to 127 plus a scale and a zero point:
#     real value = scale * (int8 value - zero_point)
# To choose those, the converter pushes real rows through the model and looks
# at the range each layer actually uses. That's what representative_data is for.
def representative_data():
    for x in X:
        yield [x.reshape(1, -1)]


converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]                        # turn quantization on
converter.representative_dataset = representative_data                      # real data to measure ranges on
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]  # int8 ops only, fail if impossible
converter.inference_input_type = tf.int8                                    # the board feeds int8 in
converter.inference_output_type = tf.int8                                   # and gets int8 back
tflite = converter.convert()

(OUT / "model.tflite").write_bytes(tflite)
with open(OUT / "model.json", "w") as f:
    json.dump({"features": FEATURES, "labels": labels, "scale": scale.tolist(),
               "transform": "log1p"}, f)

# Run the int8 model over the data the same way edge_ids.py does on the board.
interp = tf.lite.Interpreter(model_content=tflite)
interp.allocate_tensors()
inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
in_scale, in_zero = inp["quantization"]
out_scale, out_zero = out["quantization"]
correct = 0
for x, want in zip(X, y):
    q = np.clip(np.round(x / in_scale + in_zero), -128, 127).astype(np.int8)
    interp.set_tensor(inp["index"], q.reshape(inp["shape"]))
    interp.invoke()
    probs = (interp.get_tensor(out["index"]).astype(np.float32) - out_zero) * out_scale
    correct += int(probs.argmax()) == want

print("labels:", labels)
print(f"float model accuracy: {float_acc:.1%}")
print(f"int8 model accuracy:  {correct}/{len(X)} = {correct / len(X):.1%}")
print(f"wrote {OUT / 'model.tflite'} ({len(tflite)} bytes) and model.json")
