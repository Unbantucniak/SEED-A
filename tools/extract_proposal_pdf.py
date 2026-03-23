#!/usr/bin/env python3
"""Extract text from the project proposal PDF for quick review."""
from __future__ import annotations

import argparse
from pathlib import Path

import pypdf


def extract_text(pdf_path: Path, max_chars: int = 0) -> str:
    reader = pypdf.PdfReader(str(pdf_path))
    parts = []
    for idx, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        parts.append(f"===== PAGE {idx} =====\n{text}")

    full_text = "\n\n".join(parts)
    if max_chars > 0:
        return full_text[:max_chars]
    return full_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from a PDF file.")
    parser.add_argument(
        "pdf",
        nargs="?",
        default="自学习自演化智能体的经验积累与演化方法研究.pdf",
        help="Path to PDF file",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=12000,
        help="Max characters to print; 0 means print all",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    text = extract_text(pdf_path, max_chars=args.max_chars)
    print(text)


if __name__ == "__main__":
    main()
