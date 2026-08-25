---
title: BM25 调优日志
tags: [检索]
description: "BM25 参数调优：停用词列表、字段权重（正文>标题）、K1/B 系数、min_score 阈值"
difficulty: "beginner"
---
BM25 参数调优：停用词列表、字段权重（正文>标题）、K1/B 系数、min_score 阈值。
# 调优记录
- 停用词：中文常用虚词
- 字段 boost：title 4, body 1