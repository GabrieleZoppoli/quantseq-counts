// Keeps the prepared reference (genome FASTA, filtered GTF, BED, STAR index) in reference_dir/<reference id>/, so
// that later runs on the same reference reuse it. The manifest is written last: a folder without it is incomplete
// and is rebuilt. Runs on the machine that starts the run, without a container.
process STORE_REFERENCE {
    executor 'local'

    input:
    tuple val(meta), path(fasta), path(gtf), path(bed), path(index, stageAs: 'star')
    val dest

    output:
    val dest, emit: dir

    script:
    """
    set -euo pipefail
    mkdir -p "${dest}.part"
    cp -L ${fasta} "${dest}.part/genome.fa"
    cp -L ${gtf} "${dest}.part/genes.gtf"
    cp -L ${bed} "${dest}.part/genes.bed"
    cp -rL star "${dest}.part/star"
    ( cd "${dest}.part" && find . -type f ! -name MANIFEST | LC_ALL=C sort | while read -r f; do
        if command -v sha256sum >/dev/null; then sha256sum "\$f"; else shasum -a 256 "\$f"; fi; done ) > manifest.tmp
    mv manifest.tmp "${dest}.part/MANIFEST"
    rm -rf "${dest}"; mv "${dest}.part" "${dest}"
    """

    stub:
    """
    mkdir -p "${dest}/star"; touch "${dest}/genome.fa" "${dest}/genes.gtf" "${dest}/genes.bed" "${dest}/MANIFEST"
    """
}
