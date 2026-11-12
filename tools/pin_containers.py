#!/usr/bin/env python3
"""Pins every container image of the workflow to its registry digest. Reads `nextflow inspect` output (one JSON file
per library mode) and the include lines of workflow/main.nf (for process aliases); asks each registry for the
manifest of each tag; writes workflow/assets/containers.tsv (image, the digest the tag points to, and the linux/amd64
image's config and layer digests, which udocker's store is checked against) and workflow/conf/containers.config
(each process set to image@digest, used with Docker and Apptainer). Run by the maintainers when an image changes.
Usage: pin_containers.py --inspect A.json [B.json ...] --main workflow/main.nf --out-tsv T --out-config C"""
import argparse
import json
import re
import urllib.error
import urllib.request

ACCEPT = ", ".join(["application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"])


def split_image(img):
    first, _, rest = img.partition("/")
    if "." not in first:
        first, rest = "quay.io", img  # images named without a registry are on quay.io (nf-core's setting)
    repo, _, tag = rest.rpartition(":")
    return first, repo, tag


def _get(url, token=None, accept=ACCEPT):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "quantseq-counts"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return urllib.request.urlopen(req, timeout=60)


def fetch(registry, repo, ref):
    url = f"https://{registry}/v2/{repo}/manifests/{ref}"
    try:
        r = _get(url)
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise
        h = e.headers.get("WWW-Authenticate", "")
        p = dict(re.findall(r'(\w+)="([^"]*)"', h))
        q = f"{p['realm']}?service={p.get('service', '')}&scope=repository:{repo}:pull"
        token = json.loads(urllib.request.urlopen(q, timeout=60).read())
        token = token.get("token") or token.get("access_token")
        r = _get(url, token)
        r.token = token
    body = r.read()
    return r.headers.get("Docker-Content-Digest"), json.loads(body), getattr(r, "token", None)


def resolve(img):
    registry, repo, tag = split_image(img)
    digest, m, token = fetch(registry, repo, tag)
    if "manifests" in m:  # an index: the linux/amd64 image is what the servers run
        amd = next(x for x in m["manifests"] if x.get("platform", {}).get("architecture") == "amd64"
                   and x.get("platform", {}).get("os") == "linux")
        _, m, _ = fetch(registry, repo, amd["digest"])
    return {"image": img, "registry": registry, "repository": repo, "tag": tag, "digest": digest,
            "config_digest": m["config"]["digest"], "layer_digests": ";".join(l["digest"] for l in m["layers"])}


def aliases(main_nf):
    out = {}
    for base, alias in re.findall(r"include\s*\{\s*(\w+)(?:\s+as\s+(\w+))?\s*\}", open(main_nf).read()):
        out.setdefault(base, set()).add(alias or base)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", nargs="+", required=True); ap.add_argument("--main", required=True)
    ap.add_argument("--out-tsv", required=True); ap.add_argument("--out-config", required=True)
    a = ap.parse_args()
    procs = {}
    for f in a.inspect:
        for p in json.load(open(f))["processes"]:
            if p.get("container"):
                procs[p["name"]] = p["container"]
    al = aliases(a.main)
    images = sorted(set(procs.values()))
    rows = [resolve(i) for i in images]
    cols = ["image", "registry", "repository", "tag", "digest", "config_digest", "layer_digests"]
    with open(a.out_tsv, "w") as f:
        f.write("\t".join(cols) + "\n" + "".join("\t".join(r[c] for c in cols) + "\n" for r in rows))
    pin = {r["image"]: f"{r['registry']}/{r['repository']}@{r['digest']}" for r in rows}
    lines = ["// Every process's image pinned to its registry digest (tools/pin_containers.py; workflow/assets/containers.tsv).",
             "// Used with Docker and Apptainer; udocker pulls by tag and checks the digests (src/quantseq_counts/launch.py).",
             "process {"]
    for base in sorted(procs):
        names = sorted(al.get(base, set()) | {base})
        lines.append(f"    withName: '^({'|'.join(names)})$' {{ container = '{pin[procs[base]]}' }}")
    lines.append("}")
    open(a.out_config, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
