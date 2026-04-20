# Active Services

本文件描述当前 active 仓库中仍然保留的在线服务。

下面命令里的 `./annotation/batch_<YYYYMMDD>_vNN` 只是占位写法，请替换成你当前正在操作的 batch。

---

## Step 3 服务：`human_stage_1`

目录：

- [step3_human_stage_1/](/home/hrli/data_annotation/codes/application/step3_human_stage_1)

后端：

- [ui_human_stage_1_server.py](/home/hrli/data_annotation/codes/application/step3_human_stage_1/ui_human_stage_1_server.py)

前端：

- [web/index.html](/home/hrli/data_annotation/codes/application/step3_human_stage_1/web/index.html)
- [web/app.js](/home/hrli/data_annotation/codes/application/step3_human_stage_1/web/app.js)
- [web/styles.css](/home/hrli/data_annotation/codes/application/step3_human_stage_1/web/styles.css)

作用：

- 读取 `human_stage_1_prep/`
- 派发第一阶段粗标任务
- 保存 coarse labels

当前常用命令：

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python \
  codes/application/step3_human_stage_1/ui_human_stage_1_server.py \
  --batch-dir ./annotation/batch_<YYYYMMDD>_vNN \
  --host 127.0.0.1 \
  --port 10086
```

---

## Step 3 服务：`human_stage_1` admin

目录：

- [step3_human_stage_1/](/home/hrli/data_annotation/codes/application/step3_human_stage_1)

后端：

- [ui_human_stage_1_admin_server.py](/home/hrli/data_annotation/codes/application/step3_human_stage_1/ui_human_stage_1_admin_server.py)

前端：

- [admin_web/index.html](/home/hrli/data_annotation/codes/application/step3_human_stage_1/admin_web/index.html)
- [admin_web/app.js](/home/hrli/data_annotation/codes/application/step3_human_stage_1/admin_web/app.js)
- [admin_web/styles.css](/home/hrli/data_annotation/codes/application/step3_human_stage_1/admin_web/styles.css)

作用：

- 监控 `human_stage_1` 专属队列进度
- 查看 annotator 的 stage1 已提交帧数和进度
- 查看最近提交记录
- 查询指定 `segment_id` 的队列与提交明细

当前常用命令：

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python \
  codes/application/step3_human_stage_1/ui_human_stage_1_admin_server.py \
  --batch-dir ./annotation/batch_<YYYYMMDD>_vNN \
  --host 127.0.0.1 \
  --port 10087
```

---

## Step 5 服务：review

目录：

- [step5_stage2_review/](/home/hrli/data_annotation/codes/application/step5_stage2_review)

后端：

- [ui_review_server.py](/home/hrli/data_annotation/codes/application/step5_stage2_review/ui_review_server.py)

前端：

- [web/index.html](/home/hrli/data_annotation/codes/application/step5_stage2_review/web/index.html)
- [web/app.js](/home/hrli/data_annotation/codes/application/step5_stage2_review/web/app.js)
- [web/styles.css](/home/hrli/data_annotation/codes/application/step5_stage2_review/web/styles.css)

说明：

- 当前保留为第二阶段资源
- 但按主线口径，属于后续阶段，不是当前已完成主线

当前常用命令：

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python \
  codes/application/step5_stage2_review/ui_review_server.py \
  --batch-dir ./annotation/batch_<YYYYMMDD>_vNN \
  --host 127.0.0.1 \
  --port 10088
```

---

## Support 服务：admin

目录：

- [support/](/home/hrli/data_annotation/codes/application/support)

后端：

- [ui_admin_server.py](/home/hrli/data_annotation/codes/application/support/ui_admin_server.py)

前端：

- [admin_web/index.html](/home/hrli/data_annotation/codes/application/support/admin_web/index.html)
- [admin_web/app.js](/home/hrli/data_annotation/codes/application/support/admin_web/app.js)
- [admin_web/styles.css](/home/hrli/data_annotation/codes/application/support/admin_web/styles.css)

作用：

- 查看 batch 全局统计
- 查看段统计
- 查看 annotator 活跃度与提交结果

当前常用命令：

```bash
cd /home/hrli/data_annotation
PYTHONPATH=codes .venv/bin/python \
  codes/application/support/ui_admin_server.py \
  --batch-dir ./annotation/batch_<YYYYMMDD>_vNN \
  --host 127.0.0.1 \
  --port 10087
```
