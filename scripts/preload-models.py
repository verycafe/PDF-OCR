#!/usr/bin/env python3
"""
在 Docker 镜像构建阶段预下载 OCR / 结构化模型。

这样容器运行时就不会在首次调用 OCR 时临时联网拉模型。
"""

from paddleocr import PaddleOCR, PPStructureV3


def main() -> None:
    print("Preloading PaddleOCR models...", flush=True)
    PaddleOCR(
        use_textline_orientation=False,
        lang="ch",
        text_det_thresh=0.6,
        text_det_box_thresh=0.7,
        text_det_unclip_ratio=1.6,
        text_det_limit_side_len=960,
        text_det_limit_type="max",
    )

    print("Preloading PPStructureV3 models...", flush=True)
    PPStructureV3(
        use_table_recognition=True,
        use_formula_recognition=False,
        use_chart_recognition=False,
        lang="ch",
    )

    print("Model preloading complete.", flush=True)


if __name__ == "__main__":
    main()
