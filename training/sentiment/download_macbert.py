"""Download a local MacBERT checkpoint for WSL environments without Hugging Face access."""

from pathlib import Path

from modelscope_hub.compat import snapshot_download


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "models" / "pretrained" / "chinese-macbert-base"
FILES = [
    "config.json",
    "pytorch_model.bin",
    "vocab.txt",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
]


def main():
    path = snapshot_download(
        model_id="dienstag/chinese-macbert-base",
        revision="v1.0.0",
        local_dir=str(DESTINATION),
        allow_file_pattern=FILES,
    )
    required = ("config.json", "pytorch_model.bin", "vocab.txt")
    missing = [name for name in required if not (DESTINATION / name).is_file()]
    if missing:
        raise RuntimeError(f"Incomplete MacBERT download; missing: {', '.join(missing)}")
    print(f"MacBERT checkpoint ready: {path}")


if __name__ == "__main__":
    main()
