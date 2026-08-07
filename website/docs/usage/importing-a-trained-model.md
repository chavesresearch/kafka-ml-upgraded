---
sidebar_position: 9
---

# Importing a Trained Model

Already have a trained model from outside Kafka-ML - trained locally, in
a notebook, or by another tool entirely - and just want to serve it for
inference? You don't need a real training run to do that. Importing skips
straight to a finished result: no data streaming, no Kubernetes training
Job, just the trained weights.

Only single (non-distributed) models are supported - a distributed
father/child pair would need two coordinated weight files, out of scope
for this.

## 1. Define the model

Create the model the normal way (see [Single Models](./single-models)
step 1) - same code, same framework rules. For **PyTorch specifically**,
the code you provide must be the *exact* architecture that produced the
weights you're about to upload: importing validates by actually building
the model from this code and loading your weights onto it, and a
mismatched architecture (wrong layer sizes, missing/extra parameters)
fails validation with the real PyTorch error. TensorFlow doesn't have
this constraint - a `.h5` file already bundles its own architecture and
weights together.

## 2. Group it into a configuration

Same as [Single Models](./single-models) step 2 - a configuration with
just this one model.

## 3. Import the trained file

From the **Configurations** list, open the row's menu and choose
**Import trained model**. Upload the file (`.h5` for TensorFlow, `.pth`
for PyTorch) and optionally fill in known metrics (train/validation/test,
as JSON, plus training time) if you have them - none of this is required.

The upload is validated for real before anything is created: TensorFlow
files are loaded with `tf.keras.models.load_model()`, PyTorch weights are
loaded via `load_state_dict()` onto a model built from the code you
entered in step 1. A bad file is rejected immediately with the real
underlying error - nothing gets created until it actually passes.

## 4. Use it like any other result

Once imported, the result behaves exactly like one that finished a real
training run - it shows up in **Training** with `finished` status, can be
deployed for [real-time inference](./single-models#6-deploy-a-trained-model-for-inference)
or [IoT/TFLite deployment](./iot-tflite-deployment), and can be
[compared](./comparing-results) against other results, metrics permitting.
