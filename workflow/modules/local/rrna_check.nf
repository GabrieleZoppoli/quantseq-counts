// Per library: the trimmed reads aligned to the 45S pre-rRNA region (STAR, no splicing), then each read put in one
// class with the genome alignment of the same reads (primary records, NH tag): 45S rRNA (any hit on the 45S,
// whatever its genome alignment); the other reads aligned to one place; to several places. qc_table.py derives the
// reads not aligned from the STAR input. mt_rrna: reads whose primary genome alignment overlaps a mitochondrial rRNA
// gene (NA when the GTF has none). Sorting and joining in the C locale, so reruns give the same numbers.
process RRNA_CHECK {
    tag "$meta.id"
    label 'process_medium'
    container 'community.wave.seqera.io/library/htslib_samtools_star_gawk:ae438e9a604351a4'

    input:
    tuple val(meta), path(reads), path(bam)
    path index
    path mt_bed

    output:
    path "${meta.id}.rrna.tsv", emit: tsv
    tuple val("${task.process}"), val('star'), eval('STAR --version | sed "s/STAR_//"'), emit: versions_star, topic: versions
    tuple val("${task.process}"), val('samtools'), eval("samtools --version | sed -n '1s/samtools //p'"), emit: versions_samtools, topic: versions

    script:
    def args = task.ext.args ?: ''
    def mem = "${Math.max(1, (task.memory ? task.memory.toGiga() : 4) / 4 as int)}G"
    """
    export LC_ALL=C
    STAR --genomeDir ${index} --readFilesIn ${reads} --readFilesCommand zcat --runThreadN ${task.cpus} \\
        --outSAMtype BAM Unsorted --outSAMattributes NH --outFileNamePrefix rdna. ${args}
    input=\$(gawk -F'|' '/Number of input reads/ {gsub(/[ \\t]/, "", \$2); print \$2}' rdna.Log.final.out)
    samtools view -F 0x904 rdna.Aligned.out.bam | cut -f1 | sort -u -S ${mem} -T . > rrna.names
    samtools view -F 0x904 ${bam} \\
        | gawk -v OFS='\\t' '{nh = 1; for (i = 12; i <= NF; i++) if (\$i ~ /^NH:i:/) {nh = substr(\$i, 6); break}; print \$1, nh}' \\
        | sort -t \$'\\t' -k1,1 -S ${mem} -T . > genome.nh
    read uo mo < <(join -t \$'\\t' -v1 genome.nh rrna.names | gawk -F'\\t' '{if (\$2 == 1) u++; else m++} END {print u + 0, m + 0}')
    if [ -s ${mt_bed} ]; then mt=\$(samtools view -c -F 0x904 -L ${mt_bed} ${bam}); else mt=NA; fi
    printf 'library\\tinput\\trrna_45s\\tunique_other\\tmulti_other\\tmt_rrna\\n%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \\
        ${meta.id} "\$input" "\$(wc -l < rrna.names)" "\$uo" "\$mo" "\$mt" > ${meta.id}.rrna.tsv
    rm -f rdna.Aligned.out.bam rrna.names genome.nh
    """

    stub:
    """
    printf 'library\\tinput\\trrna_45s\\tunique_other\\tmulti_other\\tmt_rrna\\n%s\\t1000\\t300\\t500\\t100\\t20\\n' ${meta.id} > ${meta.id}.rrna.tsv
    """
}
