from pathlib import Path

from cipher import brute_force_decrypt


def rank_candidate(item: tuple[str, str]) -> tuple[int, int]:
    """Lower score is better."""
    _, text = item
    score = 0
    if text.startswith("ddc{") and text.endswith("}"):
        score -= 100
    if "{" in text and "}" in text:
        score -= 20
    if "_" in text:
        score -= 5
    score += sum(1 for ch in text if ch.isprintable() and not ch.isspace())
    return score, len(text)


def main() -> None:
    base = Path(__file__).resolve().parent
    encrypted_path = base / "encryption.txt"
    output_path = base / "decryption_candidates.txt"

    ciphertext = encrypted_path.read_text(encoding="utf-8").strip()
    candidates = brute_force_decrypt(ciphertext)
    ordered = sorted(candidates.items(), key=rank_candidate)

    best_key, best_plaintext = ordered[0]
    print(f"Best guess key: {best_key}")
    print(f"Best guess plaintext: {best_plaintext}")

    lines = [f"{key}: {plaintext}" for key, plaintext in ordered]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved all candidates to {output_path.name}")


if __name__ == "__main__":
    main()
