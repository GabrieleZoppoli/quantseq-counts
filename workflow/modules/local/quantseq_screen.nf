// A label-blind screen of each raw FASTQ: reads, mean length, reads with N in the UMI (bases 1-6), reads with the
// UMI spacer TATA exactly at bases 7-10, reads holding AAAAAAAA (poly(A)), reads holding AGATCGGAAGAG (adapter).
process QUANTSEQ_SCREEN {
    tag "$meta.id"
    label 'process_single'
    container 'community.wave.seqera.io/library/gawk:5.3.1--e09efb5dfc4b8156'

    input:
    tuple val(meta), path(reads)

    output:
    path "${meta.id}.screen.tsv", emit: tsv

    script:
    """
    gzip -cdf ${reads} | gawk -v id=${meta.id} 'NR % 4 == 2 {
        n++; L += length(\$0)
        if (substr(\$0, 1, 6) ~ /N/) un++
        if (substr(\$0, 7, 4) == "TATA") t++
        if (index(\$0, "AAAAAAAA")) a8++
        if (index(\$0, "AGATCGGAAGAG")) ad++ }
        END { printf "%s\\t%d\\t%.3f\\t%d\\t%d\\t%d\\t%d\\n", id, n, (n ? L / n : 0), un, t, a8, ad }' > ${meta.id}.screen.tsv
    """

    stub:
    """
    printf '%s\\t1000\\t75.0\\t0\\t950\\t100\\t10\\n' ${meta.id} > ${meta.id}.screen.tsv
    """
}
