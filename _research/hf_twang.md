---
license: apache-2.0
dataset_info:
- config_name: default
  features:
  - name: publish_date
    dtype: timestamp[ns]
  - name: effective_date
    dtype: timestamp[ns]
  - name: type
    dtype: string
  - name: status
    dtype: string
  - name: title
    dtype: string
  - name: office
    dtype: string
  - name: office_level
    dtype: string
  - name: office_category
    dtype: string
  - name: effective_period
    dtype: string
  - name: content
    dtype: string
  splits:
  - name: train
    num_bytes: 363619544
    num_examples: 22552
  download_size: 159516785
  dataset_size: 363619544
- config_name: metadata
  features:
  - name: publish_date
    dtype: timestamp[ns]
  - name: effective_date
    dtype: timestamp[ns]
  - name: type
    dtype: string
  - name: status
    dtype: string
  - name: title
    dtype: string
  - name: office
    dtype: string
  - name: office_level
    dtype: string
  - name: office_category
    dtype: string
  - name: effective_period
    dtype: string
  splits:
  - name: train
    num_bytes: 4529871
    num_examples: 22552
  download_size: 740438
  dataset_size: 4529871
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
- config_name: metadata
  data_files:
  - split: train
    path: metadata/train-*
---


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
