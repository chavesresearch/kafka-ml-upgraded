---
sidebar_position: 8
---

# Comparing Training Results

Every training result can be inspected on its own (the [Single
Models](./single-models) tutorial's step 5, "Model metrics
visualization") — but answering "did this hyperparameter change actually
help?" usually means looking at two or more results side by side. The
**Results** list's "Compare results" picker does exactly that: pick 2–5
finished results, and see their metric curves overlaid, one chart per
metric.

## Picking results to compare

In the **Results** tab, use the "Compare results" selector above the
table to pick 2 to 5 results, then hit **Compare**. This navigates to a
URL like `/results/compare?ids=3,7,9` — the id list lives in the URL, so
a comparison view can be bookmarked or shared directly.

The 5-result cap isn't arbitrary: each compared result gets one of the
app's 5 chart colors, and there's no 6th slot to assign.

## Reading the charts

Rather than one chart with every metric and every result overlaid (fast
to become unreadable — 3 results × 2 metrics × train/val is already 12
lines), each selected metric gets its own small chart:

- **Color** identifies which result a line belongs to.
- **Line style** identifies the split — solid for training, dashed for
  validation.

Pick which metrics to overlay with the metric selector above the charts
— every metric present in *any* of the compared results is available,
not just ones common to all of them. A result that trained for fewer
epochs than the others simply has its line stop early, rather than
flattening out artificially.

Below the charts, each compared result gets its own summary card with
its final train/validation/test metric values and training time — the
same numbers each result's own "Info" dialog in the Results list shows.

## Editing the comparison in place

A second picker lets you add or remove results from the current
comparison without leaving the page or losing your metric selection —
it just updates the URL's id list and re-fetches.

## Exporting

"Download comparison data" exports the same underlying chart data as
JSON, for building your own plots or reports outside Kafka-ML.
