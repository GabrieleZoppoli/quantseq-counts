// Keeps the prepared reference (genome FASTA, filtered GTF, BED, STAR index) in reference_dir/<reference id>/, so
// that later runs on the same reference reuse it. The manifest is written last: a folder without it, or with a file it
// lists missing, is incomplete and is rebuilt (storedReferenceComplete in main.nf). Runs on the machine that starts the run, without a container.
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
    # a folder of its own for this copy (a run that was killed may have left one; the old fixed name is removed)
    # (a copy killed outright leaves its folder: those older than a day are removed)
    rm -rf "${dest}.part"
    mkdir -p "\$(dirname "${dest}")"
    find "\$(dirname "${dest}")" -maxdepth 1 -name "\$(basename "${dest}").part.*" -mmin +1440 -exec rm -rf {} +
    part=\$(mktemp -d "${dest}.part.XXXXXX")
    trap 'rm -rf "\$part"' EXIT
    chmod "\$(printf '%o' \$(( 0777 & ~0\$(umask) )))" "\$part"  # mktemp makes it private; follow the umask
    cp -L ${fasta} "\$part/genome.fa"
    cp -L ${gtf} "\$part/genes.gtf"
    cp -L ${bed} "\$part/genes.bed"
    cp -rL star "\$part/star"
    ( cd "\$part" && find . -type f ! -name MANIFEST | LC_ALL=C sort | while read -r f; do
        if command -v sha256sum >/dev/null; then sha256sum "\$f"; else shasum -a 256 "\$f"; fi; done ) > manifest.tmp
    mv manifest.tmp "\$part/MANIFEST"
    rm -rf "${dest}"; mv "\$part" "${dest}"
    """

    stub:
    """
    rm -rf "${dest}.part"
    mkdir -p "${dest}/star"; touch "${dest}/genome.fa" "${dest}/genes.gtf" "${dest}/genes.bed" "${dest}/star/SA"
    printf 'stub  ./%s\n' genes.bed genes.gtf genome.fa star/SA > "${dest}/MANIFEST"
    """
}
