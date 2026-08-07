---
sidebar_position: 2
---

# Distributed Models

A distributed model splits work across a hierarchy of sub-models (e.g.
edge → fog → cloud), each trained together as one chain.

Currently only TensorFlow supports distributed models. The setup is the
same as [Single Models](./single-models), with each sub-model marked
distributed and linked to its parent.

## 1. Define a distributed model

This three-tier MNIST example is a simple way to start:

```py
edge_input = keras.Input(shape=(28,28,1), name='input_img')
x = tf.keras.layers.Conv2D(28, kernel_size=(3,3), name='conv2d')(edge_input)
x = tf.keras.layers.MaxPooling2D(pool_size=(2,2), name='maxpooling')(x)
x = tf.keras.layers.Flatten(name='flatten')(x)
output_to_fog = tf.keras.layers.Dense(64, activation=tf.nn.relu, name='output_to_fog')(x)
edge_output = tf.keras.layers.Dense(10, activation=tf.nn.softmax, name='edge_output')(output_to_fog)
edge_model = keras.Model(inputs=[edge_input], outputs=[output_to_fog, edge_output], name='edge_model')

fog_input = keras.Input(shape=64, name='fog_input')
output_to_cloud = tf.keras.layers.Dense(64, activation=tf.nn.relu, name='output_to_cloud')(fog_input)
fog_output = tf.keras.layers.Dense(10, activation=tf.nn.softmax, name='fog_output')(output_to_cloud)
fog_model = keras.Model(inputs=[fog_input], outputs=[output_to_cloud, fog_output], name='fog_model')

cloud_input = keras.Input(shape=64, name='cloud_input')
x = tf.keras.layers.Dense(64, activation=tf.nn.relu, name='relu1')(cloud_input)
x = tf.keras.layers.Dense(128, activation=tf.nn.relu, name='relu2')(x)
x = tf.keras.layers.Dropout(0.2)(x)
cloud_output = tf.keras.layers.Dense(10, activation=tf.nn.softmax, name='cloud_output')(x)
cloud_model = keras.Model(inputs=cloud_input, outputs=[cloud_output], name='cloud_model')
```

Insert each sub-model's code into the Web UI separately, and mark each as
distributed. The "Upper model" field links each sub-model to its parent:
in this example, Edge's upper model is Fog, and Fog's upper model is
Cloud (Cloud sits at the top of the chain, so it has no upper model).

![Create a distributed model](/img/docs/create-distributed-model.png)

## 2. Define a configuration

Kafka-ML only lists sub-models at the top of a distributed chain —
choosing one adds its whole chain to the configuration.

![Create a distributed configuration](/img/docs/create-distributed-configuration.png)

## 3. Deploy the configuration for training

![Deploy a distributed configuration](/img/docs/deploy-distributed-configuration.png)

Set optimizer, learning rate, loss, metrics, batch size, and
training/validation parameters — same format as TensorFlow's
`fit`/`evaluate`. Optimizer/learning-rate/loss/metrics are optional and
default to `adam`, `0.001`, `sparse_categorical_crossentropy`, and
`sparse_categorical_accuracy` respectively. Validation parameters only
apply if `validation_rate > 0` or `test_rate > 0`.

![Configure a distributed deployment](/img/docs/configure-distributed-deployment.png)

Once deployed, you'll see one training result per sub-model — the whole
chain is ready to receive stream data.

![Distributed training results](/img/docs/distributed-training-results.png)

## 4. Stream data for training

```sh
python examples/MNIST_RAW_format/mnist_dataset_training_example.py
```

Set `deployment_id` to the id Kafka-ML generated, same as for single
models.

## 5. Model metrics visualization

Once trained, you'll see per-sub-model metrics and can download any
sub-model, or continue to deploy one for inference.

![Distributed training metrics](/img/docs/distributed-training-metrics.png)

## 6. Deploy a trained sub-model for inference

Configure replicas and input/output Kafka topics as usual. If the
sub-model you're deploying isn't the last one in the chain, you'll also
set an **upper data** topic and a confidence **limit** (0–1): predictions
below the limit get sent onward (as partial predictions) via the upper
topic for further processing; predictions above the limit go straight to
the output topic as final results.

![Deploy a distributed sub-model for inference](/img/docs/distributed-deploy-inference.png)

## 7. Stream data for inference

```sh
python examples/MNIST_RAW_format/mnist_dataset_inference_example.py
```
