"""The sample list (samples.csv) and the checks of the FASTQ folder against it."""

import csv
import gzip
import io
import re
from dataclasses import dataclass
from pathlib import Path

NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
FASTQ_SUFFIXES = (".fastq.gz", ".fq.gz", ".fastq", ".fq")
UMI_SHARE_THRESHOLD = 0.5


@dataclass(frozen=True)
class Sample:
    name: str
    fastq: str
    group: str | None


def read_samples(path: Path) -> list[Sample]:
    text = Path(path).read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    # tab (a paste from Excel), semicolon (CSV from Excel set to a comma-decimal language such as Italian), comma
    delim = "\t" if "\t" in lines[0] else ";" if ";" in lines[0] and "," not in lines[0] else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not rows:
        raise ValueError(f"{path}: empty sample list")
    header = [h.strip().lower() for h in rows[0]]
    if "sample" not in header or "fastq" not in header:
        raise ValueError(f"{path}: the first line must name the columns sample and fastq (and optionally group)")
    i_s, i_f = header.index("sample"), header.index("fastq")
    i_g = header.index("group") if "group" in header else None
    out = []
    for n, row in enumerate(rows[1:], start=2):
        cells = [c.strip() for c in row]
        if not any(cells):
            continue
        get = lambda i: cells[i] if i is not None and i < len(cells) else ""
        name, fq, group = get(i_s), get(i_f), get(i_g)
        if not NAME.match(name):
            raise ValueError(f"{path}, line {n}: sample name {name!r} may hold only letters, digits, '.', '-', '_'")
        if not name[0].isalnum():
            raise ValueError(f"{path}, line {n}: sample name {name!r} must start with a letter or digit")
        if not fq:
            raise ValueError(f"{path}, line {n}: no FASTQ file for sample {name}")
        out.append(Sample(name, fq, group or None))
    if not out:
        raise ValueError(f"{path}: no samples listed")
    return out


def check_folder(samples: list[Sample], fastq_dir: Path) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    fastq_dir = Path(fastq_dir)
    seen_names, seen_files = set(), {}
    for s in samples:
        if s.name in seen_names:
            errors.append(f"sample {s.name} is listed twice")
        seen_names.add(s.name)
        if s.fastq in seen_files:
            errors.append(f"{s.fastq} is in two rows ({seen_files[s.fastq]} and {s.name})")
        seen_files[s.fastq] = s.name
        if ".." in Path(s.fastq).parts or Path(s.fastq).is_absolute():
            errors.append(f"{s.name}: {s.fastq} must be a file inside the FASTQ folder (no '..', no absolute path)")
        elif not (fastq_dir / s.fastq).is_file():
            errors.append(f"{s.name}: {s.fastq} not found in {fastq_dir}")
    listed = {str(Path(f)) for f in seen_files}
    for p in sorted(fastq_dir.rglob("*")):
        rel = str(p.relative_to(fastq_dir))
        if p.is_file() and rel.endswith(FASTQ_SUFFIXES) and rel not in listed:
            warnings.append(f"{rel} is in the FASTQ folder but in no row of the sample list")
    return errors, warnings


def _open(path: Path):
    with open(path, "rb") as f:
        magic = f.read(2)
    return gzip.open(path, "rt") if magic == b"\x1f\x8b" else open(path, "rt")


def probe_umi(fastq: Path, n: int = 10000) -> float:
    """Share of the first n reads with the QuantSeq UMI spacer TATA at bases 7-10."""
    total = hits = 0
    with _open(fastq) as f:
        for i, line in enumerate(f):
            if i % 4 == 1:
                total += 1
                hits += line[6:10] == "TATA"
                if total >= n:
                    break
    return hits / total if total else 0.0


def umi_disagreement(library: str, share: float) -> str | None:
    pct = f"{100 * share:.0f}%"
    if library == "fwd_umi" and share < UMI_SHARE_THRESHOLD:
        return (f"only {pct} of the first reads carry the UMI spacer TATA at bases 7-10: "
                "these may be libraries without UMI (library: fwd_no_umi)")
    if library == "fwd_no_umi" and share > UMI_SHARE_THRESHOLD:
        return (f"{pct} of the first reads carry the UMI spacer TATA at bases 7-10: "
                "these look like libraries with UMI (library: fwd_umi)")
    return None
