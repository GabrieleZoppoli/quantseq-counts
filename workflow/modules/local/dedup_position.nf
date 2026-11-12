// Deduplication by position only, for libraries without UMIs when dedup_without_umi is set (a warning is shown
// before the run: in a 3' library many reads at the same position are different molecules).
process DEDUP_POSITION {
    tag "$meta.id"
    label 'process_medium'
    container 'community.wave.seqera.io/library/htslib_samtools:1.23.1--5b6bb4ede7e612e5'

    input:
    tuple val(meta), path(bam), path(bai)

    output:
    tuple val(meta), path("${meta.id}.posdedup.sorted.bam"), path("${meta.id}.posdedup.sorted.bam.bai"), emit: bam_bai
    path "${meta.id}.markdup.txt", emit: stats
    tuple val("${task.process}"), val('samtools'), eval("samtools --version | sed -n '1s/samtools //p'"), emit: versions_samtools, topic: versions

    script:
    def t = task.cpus > 1 ? "-@ ${task.cpus - 1}" : ''
    """
    samtools sort -n --no-PG ${t} -o byname.bam ${bam}
    samtools fixmate -m --no-PG ${t} byname.bam fixed.bam
    samtools sort --no-PG ${t} -o fixed.sorted.bam fixed.bam
    samtools markdup -r --no-PG ${t} -f ${meta.id}.markdup.txt fixed.sorted.bam ${meta.id}.posdedup.sorted.bam
    samtools index ${t} ${meta.id}.posdedup.sorted.bam
    rm byname.bam fixed.bam fixed.sorted.bam
    """

    stub:
    """
    echo "samtools markdup -r (stub)" > ${meta.id}.posdedup.sorted.bam; touch ${meta.id}.posdedup.sorted.bam.bai ${meta.id}.markdup.txt
    """
}
