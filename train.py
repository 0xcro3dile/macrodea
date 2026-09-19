#!/usr/bin/env python3
# train a tiny multi-class IDS model from dataset.csv, export int8-quantized model.tflite.
# needs tensorflow (run in tfenv). log1p handles the wide feature ranges (counts .. 90k pps).
import csv, json, numpy as np, tensorflow as tf

FEATURES = ["pkts", "ports", "syns", "top_port", "held", "nic_pps"]
rows = list(csv.DictReader(open("dataset.csv")))
labels = sorted({r["label"] for r in rows})
Xraw = np.array([[float(r[f]) for f in FEATURES] for r in rows], np.float32)
y = np.array([labels.index(r["label"]) for r in rows])

Xlog = np.log1p(Xraw)                       # compress wide dynamic range
scale = Xlog.max(0); scale[scale == 0] = 1  # -> [0,1]; save for the board
Xn = (Xlog / scale).astype(np.float32)

model = tf.keras.Sequential([
    tf.keras.layers.Input((len(FEATURES),)),
    tf.keras.layers.Dense(24, activation="relu"),
    tf.keras.layers.Dense(len(labels), activation="softmax"),
])
model.compile("adam", "sparse_categorical_crossentropy", metrics=["accuracy"])
model.fit(Xn, y, epochs=400, verbose=0)
float_acc = model.evaluate(Xn, y, verbose=0)[1]

def rep():
    for x in Xn:
        yield [x.reshape(1, -1)]

conv = tf.lite.TFLiteConverter.from_keras_model(model)
conv.optimizations = [tf.lite.Optimize.DEFAULT]              # <-- int8 quantization
conv.representative_dataset = rep
conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
conv.inference_input_type = conv.inference_output_type = tf.int8
open("model.tflite", "wb").write(conv.convert())
json.dump({"features": FEATURES, "labels": labels, "scale": scale.tolist(),
           "transform": "log1p"}, open("model.json", "w"))

# verify the int8 model
it = tf.lite.Interpreter("model.tflite"); it.allocate_tensors()
inp, out = it.get_input_details()[0], it.get_output_details()[0]
si, zi = inp["quantization"]; so, zo = out["quantization"]
ok = 0
for i in range(len(Xn)):
    q = np.clip(np.round(Xn[i]/si + zi), -128, 127).astype(np.int8).reshape(inp["shape"])
    it.set_tensor(inp["index"], q); it.invoke()
    o = (it.get_tensor(out["index"]).astype(np.float32) - zo) * so
    ok += (int(np.argmax(o)) == y[i])
print(f"labels: {labels}")
print(f"float keras accuracy: {float_acc:.2%}")
print(f"int8 tflite accuracy: {ok}/{len(Xn)} = {ok/len(Xn):.2%}")
print("wrote model.tflite (%d bytes) + model.json" % len(open('model.tflite','rb').read()))
