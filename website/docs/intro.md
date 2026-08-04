---
sidebar_position: 1
---

# Introduction

Kafka-ML is a framework to manage the pipeline of TensorFlow/Keras and
PyTorch (Ignite) machine learning (ML) models on Kubernetes. The pipeline
allows the design, training, and inference of ML models. The training
and inference datasets for the ML models can be fed through Apache
Kafka, so they can be directly connected to data streams like the ones
provided by the IoT.

ML models can be easily defined in the Web UI with no need for external
libraries and executions, providing an accessible tool for both experts
and non-experts on ML/AI.

![Kafka-ML pipeline architecture](/img/docs/pipeline_.png)

## Citation

You can find more information about Kafka-ML and its architecture in the
open-access publication below:

> C. Martín, P. Langendoerfer, P. Zarrin, M. Díaz and B. Rubio.
> **Kafka-ML: connecting the data stream with ML/AI frameworks**.
> Future Generation Computer Systems, 2022, vol. 126, p. 15-33.
> [10.1016/j.future.2021.07.037](https://www.sciencedirect.com/science/article/pii/S0167739X21002995)

If you wish to reuse Kafka-ML, please properly cite the paper above.
Here's a BibTeX reference:

```bibtex
@article{martin2022kafka,
  title={Kafka-ML: connecting the data stream with ML/AI frameworks},
  author={Mart{\'\i}n, Cristian and Langendoerfer, Peter and Zarrin, Pouya Soltani and D{\'\i}az, Manuel and Rubio, Bartolom{\'e}},
  journal={Future Generation Computer Systems},
  volume={126},
  pages={15--33},
  year={2022},
  publisher={Elsevier}
}
```

The Kafka-ML article was selected as the [Spring 2022 Editor's Choice
Paper at Future Generation Computer
Systems](https://www.sciencedirect.com/journal/future-generation-computer-systems/about/editors-choice)!

## Where to go next

- [Getting Started](./getting-started) — deploy Kafka-ML in one command
- [Architecture](./architecture) — a tour of every component in the pipeline
- [Interactive Showcase](/showcase) — see all 9 training modes animated, no cluster required
- [SDK](/sdk/intro) — drive Kafka-ML from Python instead of the Web UI
